#!/usr/bin/env python3
"""M9 cost/model ablation driver — the only thing in this repo that spends money.

Submits one fixed task set to a **deployed** instance once per model, polls each
run to completion, and writes a committed report to `evals/report/`. It does not
run the agent in-process and it never touches `OPENROUTER_API_KEY`: the key lives
only in the deployment's environment (CLAUDE.md rule 8), so the ablation is driven
over HTTP from a machine that has no key at all.

    python3 -m evals.ablation                       # the live deployment, all 4 models
    python3 -m evals.ablation --models tencent/hy3

`--base` exists for a second *deployed* instance, not for localhost: the fixture
URLs are built against it and the deployment's own URL guard refuses loopback in
every spelling, so a local run aborts on task 1 by design.

Rationale, task set and decision rule: `specs/decisions/ADR-010-m9-model-ablation.md`.

Loud, never partial (CLAUDE.md rule 4): a non-2xx, an unknown model, or a run that
never leaves `running` aborts the driver and **writes no report**. The rows already
collected are dumped to stderr instead, because that spend really happened and
losing the record of it would be its own dishonesty — but a dump on stderr is not
a result, and nothing downstream reads it.

`markdown_table` is the single formatter for the tradeoff table in
`docs/analysis.md`: the driver emits it, and the eval case
`analysis-ablation-table-not-estimated` re-derives it from the same report and
refuses any row that does not match. One formatter, two callers — the pattern the
verifier already uses.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run import aggregate, pctl  # noqa: E402
from src.browser.planner import ABLATION_MODELS, DEFAULT_MODEL  # noqa: E402
from src.browser.verifier import answers_match  # noqa: E402

LIVE_BASE = "https://whaleforce-browser-agent.zeabur.app"
REPORT_DIR = ROOT / "evals" / "report"

# The task set: five committed golden cases, named by id and read from disk.
# Deliberately five, not a benchmark suite — this is a tradeoff table, and every
# extra row is spend on a question already answered.
#
# Four of the five are fixtures the deployment serves itself, so the page is
# byte-identical for every model and the only variable is the plan. The fifth is
# live, for external validity — a fixture this repo wrote cannot show that a model
# copes with a DOM nobody here authored.
#
# Task text, start URL and ground-truth answer are READ FROM the case files, never
# copied into this list. A copy makes "reuses the hand label already committed" a
# claim nothing checks: a fixture edit that correctly updates the golden case
# would leave the driver grading against a stale label, every model scoring 0/5 on
# that row with no case red (cold review, M9).
#
# Correct means the run reported `success` AND its answer matches ground truth
# under the production comparison (`verifier.answers_match` — the same function
# the eval adapter grades `expect.answer` with), so a confident wrong answer
# scores zero, exactly as it should.
TASK_CASES = [
    "tc1-shop-price", "tc2-shop-search", "tc3-shop-detail-nav",
    "tc4-shop-sort-cheapest", "live-books-travel-price",
]


def load_tasks() -> list[dict]:
    """The task set, resolved from the golden cases. Loud on anything missing."""
    tasks = []
    for cid in TASK_CASES:
        path = ROOT / "evals" / "golden" / f"{cid}.json"
        if not path.is_file():
            raise SystemExit(f"[ablation] ABORTED: no such golden case: {path}")
        case = json.loads(path.read_text(encoding="utf-8"))
        inp, exp = case["input"], case.get("expect", {})
        if "answer" not in exp:
            raise SystemExit(f"[ablation] ABORTED: {cid} pins no expect.answer, so it "
                             "cannot supply ground truth for the ablation")
        if exp.get("answer_is_known_wrong"):
            # This repo deliberately commits wrong-answer pins (support-matrix D5).
            # Grading a model against one would score the CORRECT answer as wrong.
            raise SystemExit(f"[ablation] ABORTED: {cid} pins a known-WRONG answer")
        tasks.append({"id": cid, "task": inp["task"], "fixture": inp.get("fixture"),
                      "url": inp.get("url"), "answer": exp["answer"],
                      "ground_truth": f"evals/golden/{cid}.json"})
    return tasks


# --- the tradeoff table ----------------------------------------------------

HEADER = ["Model", "Correct", "LLM cost", "Cost/run", "Tokens", "p50 s", "p95 s"]


def markdown_rows(report: dict) -> list[list[str]]:
    """One row per model.

    The latency columns are percentiles over each run's OWN recorded duration
    (`run_p50_s`/`run_p95_s`, from `budgets_spent.ms`, which `run_task` times
    from inside the gateway's semaphore) — never over the driver's client-side
    wall clock. The client clock carries the 2s poll granularity, and on a public
    deployment serialised by `asyncio.Semaphore(1)` it also carries however long
    the run sat queued behind a stranger clicking "Run task" on the demo page. A
    per-model latency column built from that would attribute a bystander's run to
    a model (cold review, M9). Client wall time is still recorded per row and
    rolled up as `latency_p50/p95` in `totals`; it is just not this column.

    With five runs per model, p95 is the slowest of the five. Stated wherever the
    table is published (ADR-010).
    """
    rows = []
    for m in report["models"]:
        e = report["by_model"][m]
        t, n = e["totals"], e["n"]
        usd = t.get("llm_usd", 0.0)
        rows.append([
            f"`{m}`",
            f"{e['correct']}/{n}",
            f"${usd:.6f}",
            f"${(usd / n if n else 0.0):.6f}",
            str(int(t.get("llm_tokens", 0))),
            f"{e['run_p50_s']:.2f}",
            f"{e['run_p95_s']:.2f}",
        ])
    return rows


def markdown_table(report: dict) -> str:
    lines = ["| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)]
    lines += ["| " + " | ".join(r) + " |" for r in markdown_rows(report)]
    return "\n".join(lines)


# --- HTTP ------------------------------------------------------------------


def _fatal(msg: str, rows: list) -> None:
    """Abort without writing a report. The spend is echoed, never recorded."""
    if rows:
        print("[ablation] runs completed before the abort (NOT a result, not committed):",
              file=sys.stderr)
        print(json.dumps(rows, indent=2, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(f"[ablation] ABORTED: {msg}")


def _http(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# Which runs count as a measurement of a MODEL. An allowlist, default-deny —
# and that inversion is the round-3 correction (PR #15, R14).
#
# The first three rounds argued about which `failure:env` reasons were the
# model's fault and never noticed that a whole different class was unexamined:
# `failure:nav` from the pre-plan navigation, written before the planner is ever
# called and always at $0.00, was published as a model scoring 0/5. Task 5 of the
# set is live and gets hit once per model, and this repo has been bitten twice by
# a live site's `failure:nav` already (tasks/TODO.md, M6 and the post-M6 fix).
#
# A denylist extended three times, each time by a reviewer rather than by the
# code, is a rule that will be extended a fourth time. So a status must be NAMED
# here to be published: anything unrecognised — including a class a later
# milestone adds — aborts the sweep rather than quietly becoming a zero.
#
# The five statuses below all require a plan to exist and to have been executed,
# so each one is planning quality. The two exceptions are reason-scoped, and both
# are agent-authored prefixes rather than guesses at somebody else's message:
#   failure:env  -> `planner rejected:` / `replanner rejected:` (the call worked,
#                   the answer was not a plan) and `budget exhausted:`.
#   failure:task -> everything EXCEPT `blocked URL:`, which is our own guard
#                   refusing the start URL before anything runs. An unknown
#                   target key IS the model inventing schema, and is measured.
#
# `failure:nav` is excluded entirely, not just its pre-plan spelling. A page that
# will not load is reachability, not planning, and a plan-issued `navigate` that
# times out cannot be told apart from a site being slow. That under-measures in
# the safe direction: it aborts a sweep it could have scored, never publishes a
# cell it should not have (support-matrix D15).
MEASURED_STATUSES = ("success", "failure:locate", "failure:act", "failure:extract",
                     "failure:semantic")
MODEL_FAULT_REASONS = ("planner rejected:", "replanner rejected:", "budget exhausted:")
OUR_OWN_REFUSAL = "blocked URL:"


def is_measurement(status: str | None, reason: str | None) -> bool:
    """True when this run says something about the MODEL's planning quality."""
    reason = str(reason or "")
    if status in MEASURED_STATUSES:
        return True
    if status == "failure:env":
        return reason.startswith(MODEL_FAULT_REASONS)
    if status == "failure:task":
        return not reason.startswith(OUR_OWN_REFUSAL)
    return False  # nav, unsupported, and anything nobody has thought about yet


def preflight(base: str) -> None:
    """Refuse to spend against a deployment that predates the `model` parameter.

    This is the failure that would be invisible and fatal. Zeabur keeps serving
    the previous build until the deploy flips, and the app exposes no `/version`
    (`.github/workflows/deploy-smoke.yml` states the same ceiling for the same
    reason) — so "is the model parameter live here?" cannot be read off the
    deployment. Worse, a build without it answers 200 and a run_id to a `model`
    field it silently drops, which is indistinguishable from success: the
    ablation would come back as four rows that are all the default model wearing
    four names, and nothing in the table would say so. `gateway-model-reaches-
    planner` pins that in-process; this is the deployed twin, and it is the only
    check here that runs before money does.

    Read off the guard rather than the happy path: an old build ignores the
    unknown field, a new one refuses it 422 before a browser opens. The probe
    task trips the scope screen, which `run_task` applies before it plans, so
    even on an old build that accepts the field the run ends `unsupported` at
    $0.00 rather than planning something.
    """
    probe = {"task": "log in to the admin account — preflight probe, must not run",
             "model": "definitely/not-an-allowlisted-model"}
    try:
        _http(f"{base}/tasks", probe)
    except urllib.error.HTTPError as e:
        if e.code == 422:
            return  # the guard is live: this build has the model parameter
        raise SystemExit(f"[ablation] ABORTED: preflight to {base} -> HTTP {e.code}, "
                         f"expected 422 {e.read()[:200]!r}")
    except urllib.error.URLError as e:
        raise SystemExit(f"[ablation] ABORTED: {base} unreachable: {e}") from e
    raise SystemExit(
        f"[ablation] ABORTED: {base} ACCEPTED a model that is not on the allowlist, so it is "
        "serving a build without the model parameter. Every run would silently use the "
        "default and the table would be one model wearing four names. Wait for the redeploy "
        "(deploy-smoke sleeps 240s after a push to main) and re-run.")


def run_one(base: str, model: str, spec: dict, timeout: int, rows: list) -> dict:
    url = spec.get("url") or f"{base}/fixtures/{spec['fixture']}"
    t0 = time.monotonic()
    try:
        run_id = _http(f"{base}/tasks", {"task": spec["task"], "url": url, "model": model})["run_id"]
    except urllib.error.HTTPError as e:
        _fatal(f"{model} / {spec['id']}: POST /tasks -> HTTP {e.code} {e.read()[:300]!r}", rows)
    except urllib.error.URLError as e:
        _fatal(f"{model} / {spec['id']}: POST /tasks unreachable: {e}", rows)

    # Backoff, not a flat 2s: a completion poll that sleeps longer than the runs it
    # waits on measures the poll instead of the run. Flat 2s cost the `fast` gate
    # 8.03s on one case whose four loopback runs each finish in well under a
    # second, which is what pushed the merged suite over ADR-002's ceiling
    # (PR #20). A real sweep is unaffected: its runs take tens of seconds, so the
    # interval reaches the 2s cap within the first few polls. `deadline` is still
    # the only thing that ends a run that never finishes.
    deadline, poll = time.monotonic() + timeout, 0.1
    while True:
        try:
            rec = _http(f"{base}/tasks/{run_id}")
        except urllib.error.HTTPError as e:
            _fatal(f"{model} / {spec['id']}: GET /tasks/{run_id} -> HTTP {e.code}", rows)
        if rec.get("status") != "running":
            break
        if time.monotonic() > deadline:
            # A run still in flight is not a slow result, it is no result. Recording
            # it with the numbers spent so far would be the fabrication rule 4 bans.
            _fatal(f"{model} / {spec['id']}: run {run_id} still 'running' after {timeout}s", rows)
        time.sleep(poll)
        poll = min(poll * 2, 2.0)

    # Publish only what measures the model. Everything else — a site that would
    # not load, our own URL guard, a provider outage, a class nobody has
    # classified yet — aborts rather than becoming a `0/5` at `$0.000000`.
    if not is_measurement(rec.get("status"), rec.get("reason")):
        _fatal(f"{model} / {spec['id']}: run {run_id} ended {rec.get('status')} "
               f"({rec.get('reason')!r}), which is not a measurement of this model. "
               "Publishing it would read as one. A model that failed to plan, or "
               "flailed through its budget, IS scored — this is not that", rows)

    # The gateway echoes the model its planner was actually built with. A run that
    # names a different one — or names none, which is a deployment predating the
    # parameter — cannot be attributed, and an unattributable row is the artifact
    # the preflight exists to prevent, arriving mid-sweep instead (PR #15, R4).
    if rec.get("model") != model:
        _fatal(f"{model} / {spec['id']}: run {run_id} reports model "
               f"{rec.get('model')!r}, not the one submitted. The deployment changed "
               "under the sweep (Zeabur auto-deploys from main); every row after the "
               "change would be attributed to a model that never ran", rows)

    answer = rec.get("answer")
    return {
        "model": model, "task_id": spec["id"], "task": spec["task"], "url": url,
        "run_id": run_id, "status": rec.get("status"), "answer": answer,
        "reason": rec.get("reason"),
        "verdict": (rec.get("verdict") or {}).get("verdict"),
        "expect_answer": spec["answer"], "ground_truth": spec["ground_truth"],
        "correct": bool(rec.get("status") == "success" and answers_match(answer, spec["answer"])),
        "budgets": rec.get("budgets_spent") or {},
        "seconds": round(time.monotonic() - t0, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=LIVE_BASE, help="deployed instance to drive")
    ap.add_argument("--models", nargs="+", default=ABLATION_MODELS)
    ap.add_argument("--timeout", type=int, default=180, help="seconds to wait per run")
    args = ap.parse_args()

    # Before a cent is spent: an id the deployment would refuse is a typo, and a
    # typo found after 15 paid runs is 15 paid runs wasted. Checked against
    # ABLATION_MODELS, not the endpoint's wider ALLOWED_MODELS: the incumbent
    # default is accepted by the gateway and is deliberately NOT in the
    # comparison (it is over the owner's price ceiling — ADR-010 Decision 6), so
    # ablating it here would spend on a cell the table has no column for.
    unknown = [m for m in args.models if m not in ABLATION_MODELS]
    if unknown:
        raise SystemExit(f"[ablation] ABORTED: not in the ablation set: {unknown}\n"
                         f"  ablated: {ABLATION_MODELS}\n"
                         f"  (the gateway also accepts {DEFAULT_MODEL}, which is over the "
                         f"owner's price ceiling and is not part of this comparison)")
    # A repeated id is a typo that doubles the spend and lands as two identical
    # table rows; `by_model` is keyed on the id and cannot represent two of them.
    if len(set(args.models)) != len(args.models):
        raise SystemExit(f"[ablation] ABORTED: --models repeats an id: {args.models}")

    tasks = load_tasks()
    base = args.base.rstrip("/")
    preflight(base)
    print(f"[ablation] {len(args.models)} models x {len(tasks)} tasks against {base} "
          "(preflight ok: the model guard is live on this build)")
    rows: list[dict] = []
    for model in args.models:
        for spec in tasks:
            # Outer net: `run_one` names the faults it expects, but anything that
            # escapes it — a dropped connection mid-poll, a malformed body — must
            # still land in `_fatal`, or the completed rows are lost along with
            # the record of what they cost (cold review, M9).
            try:
                row = run_one(base, model, spec, args.timeout, rows)
            except SystemExit:
                raise
            except Exception as e:
                _fatal(f"{model} / {spec['id']}: {type(e).__name__}: {e}", rows)
            rows.append(row)
            print(f"[{'OK ' if row['correct'] else 'X  '}] {model} / {row['task_id']}: "
                  f"{row['status']} {row['answer']!r} "
                  f"${row['budgets'].get('llm_usd', 0):.6f} {row['seconds']}s ({row['run_id']})")

    by_model = {}
    for model in args.models:
        mine = [r for r in rows if r["model"] == model]
        # Two latency views, kept apart on purpose. `totals.latency_*` is the
        # driver's client wall clock (queue wait + 2s poll granularity included);
        # `run_p*_s` is each run's own recorded duration, and it is the only one
        # the published table may use — see markdown_rows.
        run_s = sorted(r["budgets"].get("ms", 0) / 1000 for r in mine)
        by_model[model] = {"n": len(mine), "correct": sum(r["correct"] for r in mine),
                           "run_p50_s": pctl(run_s, 50), "run_p95_s": pctl(run_s, 95),
                           "totals": aggregate(mine)}
    report = {
        "suite": "ablation", "base": base,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "models": list(args.models),
        "task_set": [{k: v for k, v in t.items() if k != "fixture"} for t in tasks],
        "score": round(sum(r["correct"] for r in rows) / len(rows), 4),
        "totals": aggregate(rows), "by_model": by_model, "results": rows,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-ablation.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    # Plain path, not relative_to(ROOT): a print that can raise sits between a
    # report that is already written and the table the operator came for, and
    # this is the one code path where everything above it has cost real money.
    print(f"\n[ablation] report {out}\n")
    print(markdown_table(report))
    print("\n[ablation] paste the table above into docs/analysis.md under the "
          "<!-- ablation-table --> marker and name this report in that section; "
          "analysis-ablation-table-not-estimated re-derives every cell from it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
