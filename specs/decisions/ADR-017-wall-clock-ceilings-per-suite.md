# ADR-017: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: the local `fast` ceiling is re-measured from 60s to **75s** by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five), and `invariant` gets a measured ceiling of its own at **15s**; `EVAL_WALL_BUDGET_S` is scoped to `fast`, the only suite it was ever measured for.
**Because**: M31 added real cost and the first repair moved three browser cases to `invariant`-only tags instead of facing it — which took ~4.9s out of the measured number, left the published `fast` figure at 59.7s, and left the gate refusing a commit that changed nothing but JSON at 60.24s with every case passing.
**Enforced by**: `fast-wall-clock-budget` (both ceilings, the set of suites that have one, and the override's scope), `evals/run.py` `over_budget()`

**Amends**: ADR-013 Decision 4 (local `fast` ceiling 60 → 75) and ADR-002 Decision 4 (a second suite now has a ceiling)

---

## Context

ADR-013 Decision 4 has been to 70 and back to 60 already, and the record of why
is long (`fast-wall-clock-budget`'s provenance, points 5-7). What is different
this time is that nothing about the measurement is in dispute: the suite grew.

M31 added five cases that drive a real browser, three of them settle-bound —
each spends the full 2s postcondition budget on a postcondition that
deliberately never arrives. The first repair round put those three in
`invariant` only, on the argument that `fast` was at its ceiling. That was the
wrong instrument, and the reviewer's evidence is the proof:

- the pre-commit gate refused **a commit that changed nothing but JSON under
  `tasks/reviews/`** — `[eval] OVER BUDGET: suite 'fast' wall clock 60.24s > 60s`
  with `[eval] suite 'fast': 109/109 = 1.000`;
- four runs of that same tree: 59.68 / 59.70 / 59.80 / 60.24s — a coin flip;
- the cost did not go away, it moved: `invariant` went 7.26s → 12.20s while the
  published `fast` number stayed at 59.7s;
- and `invariant` had no ceiling at all, so the tag was an unbounded relief
  valve. `fast-wall-clock-budget` itself pinned `{suite: invariant,
  wall_seconds: 999.0, over: false}`.

## Decision

### 1. The three cases go back into `fast`

They are regression guards for three silent-success defects (PR #29 R1, R2, R3)
and the local pre-commit hook runs `fast` alone. A guard the hook does not run
is worth less than the 4.9s it costs.

### 2. The local `fast` ceiling is 75s, measured

Nine runs of the tree with everything in `fast`, eight here and one by the
reviewer: **64.48 / 64.58 / 64.59 / 64.63 / 64.66 / 64.68 / 64.75 / 64.81 /
64.98s** — a 0.50s spread. ADR-013 Decision 3's rule — slowest observed +15%,
rounded up to a multiple of five — gives 64.98 × 1.15 = 74.7 → **75**. The same
rule that set CI's 80, applied to a local band, not a number chosen to clear
the runs.

This is a real loosening and it is not disguised as anything else. The margin
against the observed band is ~10s where it used to be ~0.2s, and that is the
point: a ceiling whose whole job is to catch drift cannot also be the thing
that fails on drift-free commits. What has NOT changed is the mechanism — the
ceiling is still applied by `evals/run.py` to the run it just measured, still
exits non-zero, and is still graded by `fast-wall-clock-budget`.

`.eval-baseline.json` is untouched. This is a wall-clock ceiling, not a score
baseline, and `--update-baseline` was not run.

### 3. `invariant` gets a ceiling: 15s

Measured at **12.21 / 12.27s** with the cases back in both suites; the same
+15% round-up rule gives 12.27 × 1.15 = 14.1 → **15**. Two suites now have numbers, and
`fast-wall-clock-budget` grades the SET, so a third suite acquiring cost
without a ceiling turns it red.

The reason `invariant` needs one is not that it is slow. It is that without one,
"move the case to `invariant`" is a way to make the `fast` number go down while
the tree gets slower — which is exactly what happened, in this PR, one round ago.

### 4. `EVAL_WALL_BUDGET_S` is scoped to `fast`

It was introduced for the `fast` gate on CI and its value (80) was measured for
`fast`. Letting one env var raise every suite's ceiling would have closed the
valve locally and left it open on CI, where 80 is five times what `invariant`
costs. `wall_budget` now returns the committed number for any suite but `fast`,
pinned by `fast-wall-clock-budget`'s `invariant_override` rows.

Per-suite environment overrides are the upgrade path if a second environment
ever needs its own `invariant` number. Not built: nothing needs it, and one
unused knob per suite is the shape this repo keeps deleting.

## Consequences

- **CI's 80 is unchanged, and its margin is now thinner.** Nothing here measured
  CI, and inventing a CI number is the one thing `fast-wall-clock-budget`'s own
  `not_covered` section says this case cannot catch. CI ran `fast` at
  64.29-68.96s when the suite was ~60s locally; it is now ~65s locally, so the
  CI run of this branch is the measurement. If it lands over 80, the fix is an
  amendment carrying that run's number — not a guess made here.
- **The declared limitation stays declared.** Total wall clock is all that is
  graded: a case that gets 10s slower while another gets 10s faster is still
  invisible, and per-case timings still live in the committed reports.
- **README's wall-clock paragraph is rewritten**, because the numbers it
  published for the tag-shuffle justification were not reproducible: it said the
  suite ran 60.13s with "all of them" in `fast` when the real figure is ~64.6s,
  and called all three cases settle-bound when one of them costs 0.20s
  (PR #29 R10).
