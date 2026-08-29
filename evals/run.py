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

Report policy (ADR-012): every run appends ONE line to
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
# Where an `EVAL_PROBE=1` run's row goes instead. A sibling of the real ledger
# so a probe is still recorded and still readable, and `.gitignore`d so it never
# becomes a second source of truth (ADR-039 §4).
PROBE_HISTORY = REPORT_DIR / "history-probe.jsonl"
PROBE_ENV = "EVAL_PROBE"


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
# invariant-100% rule below: `fast` is the pre-commit gate, and a gate nobody
# will sit through stops being run honestly (ADR-002 Decision 4,
# specs/decisions/ADR-002-performance-thresholds.md). The number is not a
# taste: it is the ledger's band plus 15%, rounded up to a five, re-derived
# whenever the tree's cost moves — 60 through M30, 80 since ADR-019 §2. The one
# time it moved on a band nobody could reproduce, the round-5 review of ADR-013
# Decision 4's amendment to 70, it was withdrawn the same day.
# Pinned by the case `fast-wall-clock-budget`.
# Two suites, two numbers, both computed from `evals/report/history.jsonl` by
# ADR-013's rule and graded against it by `published-band-matches-the-ledger`
# (ADR-019 §2 amends ADR-013 Decision 4).
# `invariant` gets one because it stopped being free: M31 put fixture runs in it,
# and without a ceiling of its own the tag choice was an unbounded relief valve
# for the `fast` gate — which is exactly how it got used, and how the `fast`
# number stayed at 59.7s while ~4.9s of real cost moved sideways (PR #29 R13).
# `invariant` was 15 until PR #29 R21: that number was derived from five runs
# published as the band when the committed ledger held sixteen, the slowest at
# 13.57s — 13.57 x 1.15 = 15.6, so the rule had always said 20. Both bands are
# now graded against the ledger by `published-band-matches-the-ledger`.
# `fast` 105 -> 110 at M43 (ADR-035 Decision 7): nine cases entered the suite
# and the ledger's slowest run at the new count of 238 is 93.44s (ts
# `20260827-212200`), which ADR-013's rule derives 110 from. Case-COUNT growth,
# the condition ADR-021 named as the one a raise answers — the per-case cost did
# not move. The row is named because a reader re-deriving from a comment that
# still said 93.26s would be re-deriving from a SUPERSEDED row and getting the
# `fast` 110 -> 115 at ADR-039, published SEVEN times before it settled, which
# is the only part of this worth a reader's attention. Full record in ADR-019
# section 2. Every band taken from two to five samples was falsified by the next
# run, in both directions -- including a run taken specifically to CONFIRM a
# five-sample band. Across ~15 runs at 240-243 cases this suite's wall clock is a
# distribution roughly 2s wide, 94.8s to 97.0s, not a number; 115 covers what has
# been observed rather than its quietest corner, and section 6's own reasoning
# says that is the safe direction -- a ceiling loose by one step catches a
# regression a step later, where one derived from a quiet sample fails on the
# next busy machine. The old note follows because its account of WHY the suite
# got slower is what this ceiling covers: The settle took the suite
# 93.44 -> 96.02s at 240 cases, deriving 115. A third case then took the count
# to 241, the next two runs measured 94.95s and 94.92s, that derives 110, and
# 110 was published on the strength of "every run at this count says ~94.9".
# The very next run measured 96.99s (ts `20260828-083202`) -- a two-sample band
# presented as a settled one, falsified by the third sample, which is this
# repo's own recurring failure and the reason `published-band-matches-the-ledger`
# reads the ledger MAXIMUM rather than anyone's summary of it. 96.99 x 1.15 =
# 111.54 -> 115. ADR-021's waste removal was still done first and still
# mattered: counting every in-flight request cost 7.3s, most of it Chromium's
# own /favicon.ico 404, and narrowing the settle to fetch/xhr gave 4.8s back.
# right answer for the wrong reason: 236 cases derived 110 too, which is exactly
# why the stale copy survived a round (PR #70 R8). ADR-019 §2 is the band of
# record; this comment cites it and never leads it.
# `invariant` 20 -> 35 at T-M42-4 (ADR-036), in three steps and for two
# different reasons, which ADR-019 §3 is the band of record for: 20 -> 25 -> 30
# came from case-COUNT growth, six postcondition-scope cases of which four fail
# or refuse a postcondition BY DESIGN and burn the full settle budget each;
# 30 -> 35 came from a single contended outlier the ledger's maximum rule takes
# whether or not it is representative. Same ADR-013 rule throughout, and §3
# carries the disclosure rather than this comment.
# `fast` 110 -> 115 at M46 (ADR-037 Decision 9): eight cases entered that suite
# and the ledger's slowest run at the new count of 246 derives 115. The move was
# forecast one round earlier and filed as T-M46-2 — the 244-case band sat
# hundredths of a second inside the boundary — and it arrived exactly there, on
# a run of this branch's own gate. Case-COUNT growth again; ADR-019 §2 is the
# band of record and this comment cites it rather than leading it.
# `fast` 115 -> 120 and `invariant` 35 -> 40 at ADR-039, and this pair is NOT
# purely the case-count growth every previous move on these lines was. Four cases
# entered `fast` and two `invariant`; the rest is per-case cost from ADR-039 §1's
# post-`load` settle. ADR-021 answers per-case growth with waste removal first, so
# that was done first and both attempts are measured in ADR-019 §2: counting every
# in-flight request cost 7.3s and most of it was Chromium's own /favicon.ico 404,
# so the settle was narrowed to fetch/xhr and 4.8s came back; dropping the poll
# tick 20ms -> 5ms was tried next and returned 0.25s, falsifying the theory that
# rounding dominated. What is left is the page genuinely being waited on.
# ADR-019 §2/§3 are the bands of record; this comment cites them and never leads.
# `fast` 120 -> 125 at ADR-039's debt-clearing batch. Eleven runs at 257 cases
# span 103.10-105.44s and the maximum derives 125. Mixed growth and it is split
# rather than blurred: 17 cases entered the suite since the 240-case band (~0.2s
# each, ~3.4s), and the rest is per-case cost from ADR-039 §1's settle plus
# T-R38's per-row DOM hint, which costs one `evaluate` per enumerated row where
# the old code cost one per step. ADR-021's waste-removal step was taken first
# and is on the record in ADR-019 §2 (the favicon narrowing returned 4.8s of a
# 7.3s regression). The remaining per-case cost buys two things a case pins:
# a planner that can see a fetch-painted control, and an enumeration judged on
# the evidence each row was actually read from.
# ADR-040: the red-first run at the unchanged 109-case count measured 46.40s;
# the ledger maximum rule derives 55. No case was added.
WALL_BUDGET_S = {"fast": 125, "invariant": 55}
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
# true on CI; ADR-019 §4 gives both suites the same treatment instead of one.
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


# Which machine measured a row. A ceiling is per (suite, environment) — ADR-019's
# own Ruling — but until T-R44 the ledger had no environment dimension at all, so
# `published-band-matches-the-ledger` read whatever rows the process could see,
# and on CI that includes CI's own `invariant` row, appended by the step before.
#
# Two CI runs fired two different clauses, and this tag is the shared cause of
# both. On run 32626835735 (sha 434a98d, T-R44's origin) the row was SLOWER: 16.02s
# against a published 12.92s, deriving 20 against 15, red on item 3 (same-ceiling)
# — that tree had no dirty clause to fire, and no `ts` group in `_BAND_LINE`. On
# run 32637648447 (sha 11545a1, task/M32) the row was CLEAN and its naive-local
# `ts` sorted early, red on item 2 (cited-run)'s dirty allowance. ADR-019 §7 keeps
# the two apart. `stamp` is UTC now, which fixes the ordering key of the second;
# this tag keeps a foreign row out of the ledger entirely, which is the only thing
# that reaches the first — a foreign row is the wrong row to derive a ceiling from
# however it is stamped.
#
# NOT derived from the effective `EVAL_WALL_BUDGET_S_*`, which is the obvious
# guess and is wrong in exactly the case that produced the defect: CI's
# `invariant` ceiling is 20 and so is this laptop's, so the two environments
# would share a tag on the suite that broke.
#
# The `CI` fallback is what actually tags a runner — GitHub Actions sets `CI`
# unconditionally, as does essentially every other runner, so no workflow has to
# remember. `EVAL_ENV` is for a third environment that wants a name of its own,
# and for saying it out loud where a reader of the workflow will see it.
EVAL_ENV = "EVAL_ENV"


def env_tag():
    return os.environ.get(EVAL_ENV) or ("ci" if os.environ.get("CI") else "local")


def stamp(instant=None):
    """The ledger's `ts`, in UTC.

    Naive local time until T-M32-13. `_band_wrong` orders these strings as real
    time — item 2 (cited-run) refuses a dirty citation against any CLEAN row
    stamped earlier — and the ledger mixes zones, because a laptop writes local
    and a runner writes UTC. A CI row 25 minutes later in real time sorted eight
    hours earlier, was clean, and disqualified a citation it did not predate; on
    a tree that only reaches count N+1 while the new case is uncommitted, that
    made every case addition cost two commits. Graded by
    `ledger-ts-orders-real-time`, which sets both zones explicitly so it cannot
    pass by running on a UTC host.

    Rows written before the switch keep their local stamps: nothing records the
    zone a row was written in, so rewriting them would be invented precision.
    ADR-019 §7 states what that leaves."""
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(instant))


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
          f"p50 {totals['latency_p50']}s p95 {totals['latency_p95']}s · "
          f"judge ${totals.get('judge_usd', 0):.4f} · {int(totals.get('judge_tokens', 0))} tok · "
          f"{int(totals.get('judge_calls', 0))} boundary calls")
    if metrics:
        # Ratios are printed as x/y, never as a bare rate: the denominator is
        # the number of cases that could have exercised the mechanism, and it is
        # small enough that hiding it would flatter the number.
        def ratio(num, den):
            return f"{int(metrics.get(num, 0))}/{int(metrics.get(den, 0))}"
        # M36 per-stage hit-rate: of every run whose verdict was actually
        # evaluated, how many were rejected by the free L1 checks alone versus
        # how many reached the judge (the last, paid rung) and what it did.
        print(f"[eval] verdicts {ratio('l1_rejected_before_judge', 'verdict_evaluated')} rejected "
              f"by L1 alone · judge reached {ratio('judge_invoked', 'verdict_evaluated')} "
              f"({ratio('judge_certified', 'judge_invoked')} certified, "
              f"{ratio('judge_rejected', 'judge_invoked')} rejected, "
              f"{ratio('judge_unavailable', 'judge_invoked')} unavailable/failed-closed)")
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
    ts = stamp()
    # Read the tree BEFORE writing the report: the report is an untracked file
    # in the tree it is describing, so asking afterwards made every `--report`
    # run record `dirty: true` on account of its own artifact — and the bands
    # ADR-019 publishes are filtered out of exactly this field (PR #35 R5).
    sha, dirty = git_sha(), git_dirty()
    report_name = None
    if write_report:
        report_name = f"{ts}-{args.suite}.json"
        (REPORT_DIR / report_name).write_text(json.dumps(
            {"suite": args.suite, "score": score, "totals": totals, "metrics": metrics,
             "results": results}, indent=2))

    history_line = {
        "ts": ts, "suite": args.suite, "sha": sha, "dirty": dirty,
        "env": env_tag(),
        "passed": passed, "total": len(results), "score": round(score, 6),
        "wall_s": totals.get("wall_seconds", 0.0), "cost_usd": totals.get("llm_usd"),
        # T-M39-2's second symptom: judge spend was invisible outside this
        # runner's own stdout. `cost_usd` is planner spend and stays that, on
        # purpose — every committed row means that today, and redefining a
        # field in place makes old rows and new rows silently incomparable,
        # which is the drift this ledger exists to make impossible. So the
        # judge gets its own key. Absent on the ~2500 rows written before this,
        # which is the honest shape: `None` means "not recorded", not "zero".
        "judge_usd": totals.get("judge_usd"),
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
    # T-M38-5 / ADR-039 §4: an EXPLORATORY run must not reach the ledger the
    # band is derived from. The band is `max(wall_s)` over every row at the
    # current case count, so one measurement of a mechanism that was tried and
    # rejected raises the derived ceiling permanently, and the only remedies
    # left are re-typing a ceiling nothing measured or editing the committed
    # ledger by hand. Both of those happened before this line existed: ADR-039's
    # own first draft measured `networkidle` at 144.87s and a discarded
    # count-every-request variant at 100.86s, and both rows sat in the ledger
    # claiming to describe the tree that shipped.
    #
    # `EVAL_PROBE=1` sends the row to a sibling file instead. Deliberately NOT a
    # switch that drops the row: a probe that leaves no trace is a probe nobody
    # can audit, and the whole complaint T-M38-5 makes is about measurements
    # whose provenance went missing.
    ledger = HISTORY if not os.environ.get(PROBE_ENV) else PROBE_HISTORY
    with open(ledger, "a") as f:
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
        # ADR-002 Decision 4 set the first ceiling; ADR-019 (as amended by
        # ADR-021) is what rules on the numbers now, and naming the superseded
        # one sent a reader to a document that no longer holds them.
        source = (f"{env}={os.environ[env]}"
                  if ceiling != WALL_BUDGET_S[args.suite]
                  else "ADR-019 as amended by ADR-021")
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
