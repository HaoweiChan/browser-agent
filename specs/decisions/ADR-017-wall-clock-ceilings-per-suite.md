# ADR-017: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: four ceilings, one per (suite, environment), each measured where it is enforced — local `fast` 60 → **75s**, local `invariant` **15s**, CI `fast` 80 → **90s**, CI `invariant` **20s** — by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five), read through one variable per suite (`EVAL_WALL_BUDGET_S_FAST`, `EVAL_WALL_BUDGET_S_INVARIANT`).
**Because**: M31 added real cost and the first repair moved three browser cases to `invariant`-only tags instead of facing it — which left the gate refusing a commit that changed nothing but JSON at 60.24s with every case passing — and the first version of this ADR then gave `invariant` a ceiling derived from local runs but enforced only on CI, where it had never been measured and immediately went red.
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

The band is every `fast` run `evals/report/history.jsonl` records for the
tree, not a selection from it. The first version of this decision published
nine of the fifteen runs at 114 cases and called the spread 0.50s when the
committed history showed 64.25-64.98 — the same selective presentation ADR-013
Decision 4 was withdrawn over, in the decision that amends it (PR #29 R18).

- **114 cases, 11 green runs**: 64.25 / 64.32 / 64.58 / 64.59 / 64.63 / 64.64 /
  64.64 / 64.68 / 64.75 / 64.95 / 64.98s. Four further runs scored 113/114
  (64.48 / 64.59 / 64.61 / 64.66s) — intermediate tree states while cases were
  being fixed, labelled rather than dropped.
- **116 cases, the tree this branch ships, 9 green runs**: 64.17 / 64.34 /
  64.53 / 64.54 / 64.55 / 64.56 / 64.63 / 64.68 / 64.71s, plus three
  partial-score intermediate runs (64.39 at 114/116, 64.43 at 113/116, 64.79 at
  115/116).

ADR-013 Decision 3's rule — slowest observed +15%, rounded up to a multiple of
five — gives 64.71 × 1.15 = 74.4 → **75** on the shipped tree (and 64.98 × 1.15
= 74.7 → 75 on the wider 114-case set, so the number does not depend on which
band is used). The same rule that set CI's 80, applied to a local band, not a
number chosen to clear the runs.

This is a real loosening and it is not disguised as anything else. The margin
against the observed band is ~10s where it used to be ~0.2s, and that is the
point: a ceiling whose whole job is to catch drift cannot also be the thing
that fails on drift-free commits. What has NOT changed is the mechanism — the
ceiling is still applied by `evals/run.py` to the run it just measured, still
exits non-zero, and is still graded by `fast-wall-clock-budget`.

`.eval-baseline.json` is untouched. This is a wall-clock ceiling, not a score
baseline, and `--update-baseline` was not run.

### 3. `invariant` gets a ceiling: 15s

Measured over five runs of the shipped 48-case tree: **12.44 / 12.48 / 12.50 /
12.58 / 12.96s**; the same +15% round-up rule gives 12.96 × 1.15 = 14.9 →
**15**. Two suites now have numbers, and
`fast-wall-clock-budget` grades the SET, so a third suite acquiring cost
without a ceiling turns it red.

The reason `invariant` needs one is not that it is slow. It is that without one,
"move the case to `invariant`" is a way to make the `fast` number go down while
the tree gets slower — which is exactly what happened, in this PR, one round ago.

### 4. One override variable per suite

The first version of this decision scoped the single `EVAL_WALL_BUDGET_S` to
`fast` — which stopped it raising `invariant`'s ceiling, and in the same stroke
made it impossible for `invariant` to have a per-environment number at all. CI
then enforced §3's locally-measured 15s having never run it, and went red at
15.06s and 15.22s with 46/46 passing. `.githooks/pre-commit` runs `fast` alone,
so nothing local could catch it (PR #29 R15).

`wall_budget(suite)` now reads `EVAL_WALL_BUDGET_S_{SUITE}`. Each suite has its
own variable, so raising one environment's `fast` ceiling cannot silently raise
its `invariant` ceiling — the relief-valve property §3 is about — and each suite
can be measured where it is enforced, which is what ADR-013 Decision 3 already
ruled `fast` needed. `fast-wall-clock-budget` pins both directions.

### 5. CI's two numbers, measured on CI: 90 and 20

Not projected from local runs, which is the mistake §3 made. Four attempts of
one commit (`d173340`, the tree this branch ships — 116 `fast`, 48 `invariant`):

| attempt | `invariant` | `fast` |
|---|---|---|
| 1 | 16.47s | 69.54s |
| 2 | 15.85s | 74.06s |
| 3 | 14.80s | 69.37s |
| 4 | 15.60s | 74.04s |

Same rule: 16.47 × 1.15 = 18.9 → **20**; 74.06 × 1.15 = 85.2 → **90**.

**CI's `fast` ceiling of 80 was the next coin flip, and this is the measurement
that says so** rather than the promise the first version of this ADR left in its
place. 74.06s against 80 is 8% of margin on a runner whose own spread across
these four attempts is 6.8% — the same ratio that produced the local 60.24s
refusal. The reviewer projected ~72s and the measurement came in at 74.06s
(PR #29 R19).

The runner is ~1.15x slower than this laptop on `fast` (74.06 vs 64.71) and
~1.27x on `invariant` (16.47 vs 12.96), which is why four numbers and not two.

## Consequences

- **CI's numbers are measured, not promised.** The first version of this ADR
  left "the CI run of this branch is the measurement" as a promise; it came due
  immediately and the answer was no, twice over — `invariant` red at 15.06s and
  `fast` at 74.06s against 80. Both are now set from CI runs of the shipped
  tree (§5). `fast-wall-clock-budget`'s own `not_covered` still says this case
  cannot tell a measured number from an invented one; the four attempts are in
  §5 and in the workflow comment so a reader can check rather than trust.
- **The declared limitation stays declared.** Total wall clock is all that is
  graded: a case that gets 10s slower while another gets 10s faster is still
  invisible, and per-case timings still live in the committed reports.
- **README's wall-clock paragraph is rewritten**, because the numbers it
  published for the tag-shuffle justification were not reproducible: it said the
  suite ran 60.13s with "all of them" in `fast` when the real figure is ~64.6s,
  and called all three cases settle-bound when one of them costs 0.20s
  (PR #29 R10).
