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
"""
import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_DIRS = [ROOT / "evals" / "golden", ROOT / "evals" / "adversarial"]
BASELINE = ROOT / ".eval-baseline.json"
REPORT_DIR = ROOT / "evals" / "report"


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
    ap.add_argument("--no-report", action="store_true")
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

    if not args.no_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (REPORT_DIR / f"{stamp}-{args.suite}.json").write_text(json.dumps(
            {"suite": args.suite, "score": score, "totals": totals, "metrics": metrics,
             "results": results}, indent=2))

    baseline_path = Path(args.baseline)
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
    if args.update_baseline:
        baseline[args.suite] = score
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
        print(f"[eval] baseline['{args.suite}'] = {score:.3f} (recorded)")
        return 0
    if args.suite == "invariant" and passed < len(results):
        print("[eval] INVARIANT VIOLATION: invariants are absolute, 100% required",
              file=sys.stderr)
        return 1
    if args.suite in baseline and score < baseline[args.suite]:
        print(f"[eval] REGRESSION: {score:.3f} < baseline {baseline[args.suite]:.3f}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
