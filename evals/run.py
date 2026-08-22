#!/usr/bin/env python3
"""Task-agnostic eval runner.

Case contract (one JSON file per case, under evals/golden/ or evals/adversarial/):

    {
      "id": "unique-case-id",
      "task": "sec10k",                  # -> src/<task>/eval_adapter.py
      "suites": ["fast", "invariant"],   # default ["fast"]
      "input": { ... },                  # task-defined
      "expect": { ... }                  # task-defined
    }

Each task implements src/<task>/eval_adapter.py with:

    def run_case(case: dict) -> dict    # {"passed": bool, ...anything else}

The runner owns: discovery, suite filtering, scoring, baseline gating,
report history. Adapters own: how to run a case and judge it.

Report policy (groundwork GW-008): every run appends ONE line to
evals/report/history.jsonl — that's the committed time series and it's cheap,
so it's unconditional. A full per-case report (evals/report/<ts>-<suite>.json)
is only written when it earns its ~KB-per-case cost: `--report` was passed,
the suite is `all`, or the run is RED (a case failed, or score < baseline).
Routine green gate runs (pre-commit, CI, the PostToolUse hook) leave no full
report, only the history line. `--no-report` still forces the full report off
regardless of the above, for callers that want the printout with zero disk
writes.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_DIRS = [ROOT / "evals" / "golden", ROOT / "evals" / "adversarial"]
BASELINE = ROOT / ".eval-baseline.json"
REPORT_DIR = ROOT / "evals" / "report"
HISTORY = REPORT_DIR / "history.jsonl"


def load_cases(suite):
    cases = []
    for d in CASE_DIRS:
        for f in sorted(d.rglob("*.json")):
            case = json.loads(f.read_text())
            case["_file"] = str(f.relative_to(ROOT))
            case["_kind"] = d.name  # golden | adversarial
            if suite == "all" or suite in case.get("suites", ["fast"]):
                cases.append(case)
    return cases


def run_case(case):
    t0 = time.monotonic()
    try:
        mod = importlib.import_module(f"src.{case['task']}.eval_adapter")
        result = mod.run_case(case)
    except Exception:
        result = {"passed": False, "error": traceback.format_exc(limit=3)}
    result.setdefault("passed", False)
    result["seconds"] = round(time.monotonic() - t0, 2)
    result["id"] = case.get("id", case["_file"])
    result["kind"] = case["_kind"]
    return result


# Wall-clock ceilings, by suite. Repo policy in the same sense as the
# invariant-100% rule below: `fast` is the pre-commit gate, and past 60s it
# stops being run honestly (specs/decisions/ADR-002-performance-thresholds.md
# Decision 4; the round-5 review of ADR-013 Decision 4's amendment to 70 could
# not reproduce the straddling band that justified it, so it was withdrawn).
# Pinned by the case `fast-wall-clock-budget`.
# Two suites, two numbers, both measured (ADR-017 amends ADR-013 Decision 4).
# `invariant` gets one because it stopped being free: M31 put fixture runs in it,
# and without a ceiling of its own the tag choice was an unbounded relief valve
# for the `fast` gate — which is exactly how it got used, and how the `fast`
# number stayed at 59.7s while ~4.9s of real cost moved sideways (PR #29 R13).
WALL_BUDGET_S = {"fast": 75, "invariant": 15}
# The same ruling on slower hardware. CI measured 89.62s on main and 64.61s here
# against a 60s ceiling nothing had ever checked there; one number cannot be both
# tight locally and true on a runner ~1.6x slower, so the environment sets its
# own and both are enforced (ADR-013 amendment). `.github/workflows/eval.yml`
# declares CI's, and `fast-wall-clock-budget` grades the value it declares.
# One prefix, one variable per suite: `EVAL_WALL_BUDGET_S_FAST`,
# `EVAL_WALL_BUDGET_S_INVARIANT`. It used to be a single unsuffixed variable for
# `fast` alone, which meant `invariant` — once it had a ceiling — could not have
# a per-environment number, and CI enforced a locally-measured 15s it had never
# run (PR #29 R15: CI red at 15.06s and 15.22s while every local run was 12.2s).
# ADR-013 Decision 3's ruling was that one number cannot be tight locally and
# true on CI; ADR-017 gives both suites the same treatment instead of one.
WALL_BUDGET_ENV = "EVAL_WALL_BUDGET_S"


def wall_budget_env(suite):
    return f"{WALL_BUDGET_ENV}_{suite.upper()}"


def wall_budget(suite):
    """The ceiling in force for `suite`, or None if it has none.

    Anything that is not a positive number — unset, empty, `banana`, `60s`, `0`,
    a negative — falls back to the committed ruling. An override that silently
    disabled the gate would be this PR's own defect for the fourth time, and the
    quiet direction is the one that has bitten every time."""
    base = WALL_BUDGET_S.get(suite)
    if base is None:
        return None
    # Each suite reads its own variable, so an environment raising one ceiling
    # cannot silently raise the other — that asymmetry is what let a tag choice
    # act as a relief valve for the `fast` gate (PR #29 R13).
    try:
        override = float(os.environ.get(wall_budget_env(suite), ""))
    except ValueError:
        return base
    return override if override > 0 else base


def over_budget(suite, wall_seconds):
    """The whole ruling, pure so a case can grade it. Applied to the run being
    measured — a report is written after the run and does not survive a CI
    workspace, so it can never gate the tree that produced it (PR #20 R1)."""
    ceiling = wall_budget(suite)
    return ceiling is not None and wall_seconds > ceiling


def pctl(values, p):
    """Nearest-rank percentile — no numpy for a list of a few dozen floats."""
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * len(s) + 0.5)) - 1)]


def sum_numeric(results, field):
    """Sum whatever numeric keys the adapters put under `field`. The runner
    stays task-agnostic: it does not know what a mutation or a recovery is."""
    totals: dict[str, float] = {}
    for r in results:
        for k, v in (r.get(field) or {}).items():
            if isinstance(v, (int, float)):
                totals[k] = round(totals.get(k, 0) + v, 6)
    return totals


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                               text=True, check=True, timeout=10).stdout.strip()
    except Exception:
        return None


def git_sha():
    return _git("rev-parse", "--short", "HEAD")


def git_dirty():
    """Working tree dirty, excluding history.jsonl itself.

    Every run writes a history line to a file the previous run also touched,
    so without this exclusion the repo would read 'dirty' forever after the
    first run — never reflecting a real uncommitted code change."""
    # ponytail: pathspec magic (git >=1.9) over a manual diff; one line either way.
    out = _git("status", "--porcelain", "--", ".", ":(exclude)evals/report/history.jsonl")
    return bool(out) if out is not None else False


def aggregate(results):
    """Cost and latency roll-up. Adapters report spend under `budgets`."""
    totals = sum_numeric(results, "budgets")
    secs = [r["seconds"] for r in results]
    totals["wall_seconds"] = round(sum(secs), 2)
    totals["latency_p50"] = pctl(secs, 50)
    totals["latency_p95"] = pctl(secs, 95)
    totals["cases_with_budgets"] = sum(1 for r in results if r.get("budgets"))
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="fast")
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--report", action="store_true",
                     help="force a full per-case report even on a green run")
    ap.add_argument("--no-report", action="store_true",
                     help="never write a full report, even on red or --suite all")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT))
    cases = load_cases(args.suite)
    if not cases:
        print(f"[eval] suite '{args.suite}': no cases yet — nothing to gate on. "
              "Add cases under evals/golden/ or evals/adversarial/.")
        return 0

    results = [run_case(c) for c in cases]
    passed = sum(r["passed"] for r in results)
    score = passed / len(results)
    totals = aggregate(results)
    metrics = sum_numeric(results, "metrics")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']} ({r['kind']}, {r['seconds']}s)")
        if not r["passed"] and "error" in r:
            print(f"       {r['error'].strip().splitlines()[-1]}")
    print(f"[eval] suite '{args.suite}': {passed}/{len(results)} = {score:.3f}")
    print(f"[eval] cost ${totals.get('llm_usd', 0):.4f} · {int(totals.get('llm_tokens', 0))} tok · "
          f"{int(totals.get('actions', 0))} actions · wall {totals['wall_seconds']}s · "
          f"p50 {totals['latency_p50']}s p95 {totals['latency_p95']}s")
    if metrics:
        # Ratios are printed as x/y, never as a bare rate: the denominator is
        # the number of cases that could have exercised the mechanism, and it is
        # small enough that hiding it would flatter the number.
        def ratio(num, den):
            return f"{int(metrics.get(num, 0))}/{int(metrics.get(den, 0))}"
        print(f"[eval] recovery {ratio('recovery_verified', 'recovery_expected')} verified "
              f"({int(metrics.get('recovery_rungs', 0))} rungs tried) · "
              f"mutation {ratio('mutation_passed', 'mutation_cases')} passed, "
              f"{int(metrics.get('mutation_recovered', 0))} recovered "
              f"({int(metrics.get('mutation_relocated', 0))} by relocating) · "
              f"diagnosis {ratio('diagnosis_correct', 'diagnosis_cases')} · "
              f"{int(metrics.get('replans', 0))} replans")

    baseline_path = Path(args.baseline)
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
    # Over budget counts as red for the report policy too. The two rules landed in
    # different branches and merged into a seam: a run can exit 1 on wall clock
    # while leaving no artifact behind, which is the one shape where the evidence
    # is the timing (ADR-012's write policy, ADR-013's ceiling).
    red = (passed < len(results)
           or (args.suite in baseline and score < baseline[args.suite])
           or over_budget(args.suite, totals["wall_seconds"]))
    write_report = (args.report or args.suite == "all" or red) and not args.no_report

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report_name = None
    if write_report:
        report_name = f"{stamp}-{args.suite}.json"
        (REPORT_DIR / report_name).write_text(json.dumps(
            {"suite": args.suite, "score": score, "totals": totals, "metrics": metrics,
             "results": results}, indent=2))

    history_line = {
        "ts": stamp, "suite": args.suite, "sha": git_sha(), "dirty": git_dirty(),
        "passed": passed, "total": len(results), "score": round(score, 6),
        "wall_s": totals.get("wall_seconds", 0.0), "cost_usd": totals.get("llm_usd"),
        "report": report_name,
    }
    # Repo-specific extras (this fork's recovery/mutation/cost/p50-p95 metrics)
    # — only when the suite actually produced them, so a plain suite's line
    # doesn't carry a wall of zeros.
    if "latency_p95" in totals:
        history_line["p95_s"] = totals["latency_p95"]
    if metrics.get("recovery_expected"):
        history_line["recovery"] = f"{int(metrics['recovery_verified'])}/{int(metrics['recovery_expected'])}"
    if metrics.get("mutation_cases"):
        history_line["mutation"] = f"{int(metrics['mutation_passed'])}/{int(metrics['mutation_cases'])}"
    with open(HISTORY, "a") as f:
        f.write(json.dumps(history_line) + "\n")

    if args.update_baseline:
        baseline[args.suite] = score
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
        print(f"[eval] baseline['{args.suite}'] = {score:.3f} (recorded)")
        return 0
    if args.suite == "invariant" and passed < len(results):
        print("[eval] INVARIANT VIOLATION: invariants are absolute, 100% required",
              file=sys.stderr)
        return 1
    if over_budget(args.suite, totals["wall_seconds"]):
        ceiling = wall_budget(args.suite)
        env = wall_budget_env(args.suite)
        source = (f"{env}={os.environ[env]}"
                  if ceiling != WALL_BUDGET_S[args.suite] else "ADR-002 Decision 4")
        print(f"[eval] OVER BUDGET: suite '{args.suite}' wall clock "
              f"{totals['wall_seconds']}s > {ceiling}s ({source})", file=sys.stderr)
        return 1
    if args.suite in baseline and score < baseline[args.suite]:
        print(f"[eval] REGRESSION: {score:.3f} < baseline {baseline[args.suite]:.3f}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
