#!/usr/bin/env python3
"""Demo-readiness soak: 5 representative tasks, sequentially, against a deployment.

Not another ablation. The ablation asked "which model plans better" over 20 runs;
this asks the only question an interview actually poses:

    can this deployment reliably accept and complete a short sequence of
    interactive tasks, without infrastructure failures?

Correctness is recorded but is NOT the pass criterion. One of the five tasks has
a known capability limitation (support-matrix D17: `tc3`-shaped `near:` anchors
fail on every model), and forcing 5/5 would mean choosing tasks that flatter the
system. Infrastructure reliability is the criterion; task correctness is context.

Task set, one per path this system actually has:
  tc1-shop-price          fixture, single extract
  tc2-shop-search         fixture, fill + click + extract
  tc5-forms-submit        fixture, form submission with postcondition verification
  tc4-shop-sort-cheapest  fixture, multi-step; the cell the default model failed
                          at the VERIFIER during the ablation, so it exercises the
                          verification path rather than just the happy one
  live-books-travel-price live site, navigation, DOM nobody here wrote

Task text, start URL and ground truth are read from the committed golden cases,
never copied — the same rule the ablation driver follows.

Per task it records: /readyz before, submission outcome, /readyz and /healthz
while running, terminal status, answer, correctness, the run's own duration, the
client's wall clock, /readyz after, and every transport failure with the phase it
occurred in. Phases are recorded because D18's open question is WHERE the failure
happens, and "it timed out" does not answer that.

    python3 -m evals.soak                 # the live deployment
    python3 -m evals.soak --base https://... --repeat 2

Costs real money: every task plans with the live model on the deployment. Five
tasks is a few cents.
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

# `answers_match` and `is_measurement` come through the ablation deliberately:
# D20 and ADR-011 Decision 7 compare the two drivers' cells directly, so they
# have to be the same two rules, not two spellings of them (PR #21, R7).
from .ablation import ROOT, _http, answers_match, is_measurement

SOAK_CASES = ["tc1-shop-price", "tc2-shop-search", "tc5-forms-submit",
              "tc4-shop-sort-cheapest", "live-books-travel-price"]

# Where a transport failure happened. The point of the whole exercise: D18 could
# not say whether the client failed to connect, the server rejected, execution
# stalled, or the result was lost on the way back — and those have different fixes.
PHASE_CONNECT = "1-client-could-not-connect"
PHASE_REJECTED = "2-server-rejected-or-not-ready"
PHASE_STALLED = "3-accepted-but-execution-stalled"
PHASE_POLL = "4-poll-read-path-failed"
PHASE_LOST = "5-completed-but-result-lost"
# Between 2 and 3: the POST was delivered and its outcome is unreadable. Not the
# same event as "could not connect" — a run may be executing and billing right
# now — and not the same as "the server refused", which is an answer (PR #21, R2).
PHASE_SUBMIT_UNKNOWN = "2b-delivered-but-outcome-unknown"

POLL_SECONDS = 2   # gap between /tasks/<id> reads; a constant so a case can shrink it


def submit_phase(exc: BaseException) -> str:
    """Where a failed submission failed. The connect / post-delivery split is the
    one this repo already turns on (D18, `ablation._http`): urllib wraps a failure
    to establish the connection in `URLError` — nothing delivered, nothing billed —
    and raises a bare `TimeoutError` for a read timeout, which happens only after
    the request landed. A body that will not parse and a 200 with no `run_id` are
    post-delivery for the same reason. HTTPError is tested first: it subclasses
    URLError, and it is the one case where the server actually answered.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return PHASE_REJECTED
    if isinstance(exc, urllib.error.URLError):
        return PHASE_CONNECT
    return PHASE_SUBMIT_UNKNOWN


def probe(base: str, path: str) -> dict:
    """A health/readiness read that never raises: its failure IS the datum."""
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=15) as r:
            return {"ok": True, "seconds": round(time.monotonic() - t0, 3),
                    "body": json.load(r)}
    except urllib.error.HTTPError as e:
        # 404 is the honest answer on a build that predates /readyz.
        return {"ok": False, "seconds": round(time.monotonic() - t0, 3),
                "http": e.code, "body": None,
                "note": "endpoint not on this build" if e.code == 404 else "http error"}
    except Exception as e:
        return {"ok": False, "seconds": round(time.monotonic() - t0, 3),
                "error": f"{type(e).__name__}: {e}"}


def load_tasks() -> list[dict]:
    tasks = []
    for cid in SOAK_CASES:
        path = ROOT / "evals" / "golden" / f"{cid}.json"
        if not path.is_file():
            raise SystemExit(f"[soak] ABORTED: no such golden case: {path}")
        case = json.loads(path.read_text(encoding="utf-8"))
        inp, exp = case["input"], case.get("expect", {})
        if exp.get("answer_is_known_wrong"):
            raise SystemExit(f"[soak] ABORTED: {cid} pins a known-WRONG answer")
        tasks.append({"id": cid, "task": inp["task"], "fixture": inp.get("fixture"),
                      "url": inp.get("url"), "answer": exp.get("answer"),
                      "ground_truth": f"evals/golden/{cid}.json"})
    return tasks


def run_one(base: str, spec: dict, timeout: int) -> dict:
    url = spec["url"] or f"{base}/fixtures/{spec['fixture']}"
    # `_http` retries connect-phase failures, which is exactly the family this
    # soak exists to observe — so they are collected, not swallowed (PR #21, R3).
    retries: list[str] = []
    row = {"task_id": spec["id"], "url": url, "retries": retries,
           "readyz_before": probe(base, "/readyz")}
    t0 = time.monotonic()
    try:
        run_id = _http(f"{base}/tasks", {"task": spec["task"], "url": url},
                       retries=retries)["run_id"]
    except Exception as e:
        row.update(phase=submit_phase(e), transport_error=f"{type(e).__name__}: {e}")
        if isinstance(e, urllib.error.HTTPError):
            row["detail"] = e.read().decode()[:300]
        return row
    row["run_id"] = run_id

    mid, deadline = None, time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        if mid is None:  # one mid-run sample, taken while it is genuinely running
            mid = {"readyz": probe(base, "/readyz"), "healthz": probe(base, "/healthz")}
        try:
            rec = _http(f"{base}/tasks/{run_id}", retries=retries)
        except Exception as e:
            row.update(phase=PHASE_POLL, transport_error=f"{type(e).__name__}: {e}",
                       during=mid)
            return row
        if rec.get("status") != "running":
            break
    else:
        row.update(phase=PHASE_STALLED, during=mid,
                   transport_error=f"still 'running' after {timeout}s")
        return row

    if not isinstance(rec, dict) or "status" not in rec:
        row.update(phase=PHASE_LOST, during=mid, transport_error="terminal record unusable")
        return row

    answer = rec.get("answer")
    row.update(
        phase=None, transport_error=None, during=mid,
        status=rec.get("status"), answer=answer, reason=rec.get("reason"),
        verdict=(rec.get("verification") or {}).get("verdict"),
        expect_answer=spec["answer"], ground_truth=spec["ground_truth"],
        correct=bool(spec["answer"]) and rec.get("status") == "success"
                and answers_match(answer, spec["answer"]),
        measured=is_measurement(rec.get("status"), rec.get("reason") or ""),
        budgets=rec.get("budgets_spent") or {},
        client_seconds=round(time.monotonic() - t0, 2),
        readyz_after=probe(base, "/readyz"))
    return row


def summarize(rows: list[dict], base: str, sequences: int) -> dict:
    """The soak's whole arithmetic, in one place so a case can grade it."""
    infra = [r for r in rows if r.get("transport_error")]
    # A completion is a run that produced a real outcome. A terminal record that
    # `is_measurement` rejects — `failure:env` from a planner that could not
    # start, `failure:nav` from a page that never loaded — carries no transport
    # error and is still not a run this deployment completed. Counting it green
    # publishes demo-readiness for a deployment that never got off the ground
    # (PR #21, R1). Borrowing the ablation's allowlist means a live site's
    # `failure:nav` also stops counting: that direction understates readiness and
    # never overstates it, which is the only safe way to be wrong here.
    completed = [r for r in rows if r.get("measured")]
    unmeasured = [{"task_id": r["task_id"], "status": r.get("status"),
                   "reason": r.get("reason")}
                  for r in rows if not r.get("transport_error") and not r.get("measured")]
    return {
        "suite": "soak", "base": base, "task_set": SOAK_CASES, "sequences": sequences,
        "infrastructure_failures": len(infra),
        "completed": len(completed), "attempted": len(rows),
        "not_a_measurement": unmeasured,
        # Every retried attempt is connect-phase by construction: `_http` retries
        # `URLError` and nothing else. Each attempt carries the URL it failed on,
        # so the ledger says whether it was the submission or a poll.
        "transport_retries": [{"task_id": r["task_id"], "count": len(r["retries"]),
                               "phase": PHASE_CONNECT, "attempts": r["retries"]}
                              for r in rows if r.get("retries")],
        "correct": sum(1 for r in completed if r.get("correct")),
        "demo_ready": not infra and not unmeasured and len(completed) == len(rows),
        "phases_seen": sorted({r["phase"] for r in infra if r.get("phase")}),
        "results": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://whaleforce-browser-agent.zeabur.app")
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--repeat", type=int, default=1, help="whole sequences, back to back")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    tasks = load_tasks()

    print(f"[soak] {args.repeat} x {len(tasks)} sequential tasks against {base}")
    rows = []
    for sweep in range(args.repeat):
        for spec in tasks:
            row = run_one(base, spec, args.timeout)
            row["sequence"] = sweep + 1
            rows.append(row)
            mark = "TRANSPORT" if row.get("transport_error") else (
                "ok " if row.get("correct") else "X  ")
            print(f"[{mark}] {row['task_id']}: {row.get('status') or row.get('phase')} "
                  f"{str(row.get('answer'))[:40]!r} {row.get('client_seconds')}s "
                  f"readyz_before={_r(row['readyz_before'])} "
                  f"during={_r((row.get('during') or {}).get('readyz'))} "
                  f"after={_r(row.get('readyz_after'))}")

    report = summarize(rows, base, args.repeat)
    infra = [r for r in rows if r.get("transport_error")]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "evals" / "report" / f"{stamp}-soak.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[soak] {report['completed']}/{report['attempted']} completed without an "
          f"infrastructure failure · {report['correct']} correct "
          f"(correctness is context, not the criterion)")
    if report["not_a_measurement"]:
        print(f"[soak] NOT A MEASUREMENT (not counted as completed): "
              f"{report['not_a_measurement']}")
    if report["transport_retries"]:
        print(f"[soak] connect-phase failures that retried through: "
              f"{report['transport_retries']}")
    if infra:
        print(f"[soak] INFRASTRUCTURE FAILURES in phases: {report['phases_seen']}")
    print(f"[soak] report {out}")
    # Unlike the ablation, a partial soak IS the result — an infrastructure
    # failure is the finding, not a reason to discard the evidence around it.
    return 0


def _r(p) -> str:
    if not p:
        return "-"
    if not p.get("ok"):
        return f"n/a({p.get('http') or 'err'})"
    b = p.get("body") or {}
    return f"{'ready' if b.get('ready') else 'busy'}@{p['seconds']}s"


if __name__ == "__main__":
    raise SystemExit(main())
