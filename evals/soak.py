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

from .ablation import ROOT, _http, is_measurement

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
    row = {"task_id": spec["id"], "url": url,
           "readyz_before": probe(base, "/readyz")}
    t0 = time.monotonic()
    try:
        run_id = _http(f"{base}/tasks", {"task": spec["task"], "url": url})["run_id"]
    except urllib.error.HTTPError as e:
        row.update(phase=PHASE_REJECTED, transport_error=f"HTTP {e.code}",
                   detail=e.read().decode()[:300])
        return row
    except Exception as e:
        row.update(phase=PHASE_CONNECT, transport_error=f"{type(e).__name__}: {e}")
        return row
    row["run_id"] = run_id

    mid, deadline = None, time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        if mid is None:  # one mid-run sample, taken while it is genuinely running
            mid = {"readyz": probe(base, "/readyz"), "healthz": probe(base, "/healthz")}
        try:
            rec = _http(f"{base}/tasks/{run_id}")
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
        correct=bool(spec["answer"]) and str(answer).strip() == str(spec["answer"]).strip(),
        measured=is_measurement(rec.get("status"), rec.get("reason") or ""),
        budgets=rec.get("budgets_spent") or {},
        client_seconds=round(time.monotonic() - t0, 2),
        readyz_after=probe(base, "/readyz"))
    return row


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

    infra = [r for r in rows if r.get("transport_error")]
    completed = [r for r in rows if not r.get("transport_error")]
    report = {
        "suite": "soak", "base": base, "task_set": SOAK_CASES, "sequences": args.repeat,
        "infrastructure_failures": len(infra),
        "completed": len(completed), "attempted": len(rows),
        "correct": sum(1 for r in completed if r.get("correct")),
        "demo_ready": not infra and len(completed) == len(rows),
        "phases_seen": sorted({r["phase"] for r in infra if r.get("phase")}),
        "results": rows,
    }
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "evals" / "report" / f"{stamp}-soak.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[soak] {report['completed']}/{report['attempted']} completed without an "
          f"infrastructure failure · {report['correct']} correct "
          f"(correctness is context, not the criterion)")
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
