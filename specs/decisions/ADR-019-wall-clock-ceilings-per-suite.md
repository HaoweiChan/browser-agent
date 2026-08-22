# ADR-019: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: four ceilings, one per (suite, environment), each derived by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five) from a band computed from `evals/report/history.jsonl` and graded against it — local `fast` 60 → **80s**, local `invariant` **20s**, CI `fast` 80 → **90s**, CI `invariant` **20s** — read through one variable per suite (`EVAL_WALL_BUDGET_S_FAST`, `EVAL_WALL_BUDGET_S_INVARIANT`).
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

### 2. The local `fast` ceiling is 80s, computed from the ledger

Every published band here is computed from `evals/report/history.jsonl` — the
ledger committed in this repo — and `published-band-matches-the-ledger` grades
that property on every run. It has to, because three bands in this PR did not
match the ledger beside them: nine of fifteen runs published as "every run the
ledger records", four values that appear in no recorded run, the two slowest
`invariant` runs dropped unlabelled, and a maximum (64.71s) the ceiling was
derived from that was never measured (PR #29 R18, R21). That is the same
selective presentation ADR-013 Decision 4 was withdrawn over, repeated in the
decision that amends it.

**The ledger's numbers, at the case count this branch ships:**

- Slowest recorded `fast` run at 132 cases: **66.33s** — 6 runs:
  65.72 / 65.83 / 65.84 / 66.13 / 66.25 / 66.33s.

ADR-013 Decision 3's rule — slowest observed +15%, rounded up to a multiple of
five — gives 66.33 × 1.15 = 76.3 → **80**. The band published for the earlier
114-, 116- and 122-case trees is superseded rather than corrected in place: it was
derived by hand from a subset, and the point of the grader is that nobody has
to trust a hand-derived band again. The rule is unchanged; only the reading of
it was wrong.

Margin against the observed band is ~14s where before M31 it was ~0.2s. That is
a real loosening, and it is the point: a ceiling whose job is to catch drift
cannot also be the thing that fails on drift-free commits — this one refused a
commit that changed nothing but JSON.

### 3. `invariant` gets a ceiling: 20s

- Slowest recorded `invariant` run at 51 cases: **14.12s** — 32 runs:
  11.17 / 12.4 / 12.67 / 12.68 / 12.72 / 12.73 / 12.74 / 12.74 / 12.75 / 12.79 / 12.79 / 12.85 / 12.85 / 12.87 / 12.87 / 12.87 / 12.9 / 12.93 / 12.95 / 12.98 / 12.99 / 13 / 13.01 / 13.02 / 13.05 / 13.18 / 13.21 / 13.25 / 13.28 / 13.45 / 13.73 / 14.12s.

The same rule gives 14.12 × 1.15 = 16.2 → **20**.

This number was **15** until PR #29 R21, and that was a reading error, not a
rule change: the band behind it published five runs of a ledger holding
sixteen, dropping the two slowest (13.06 and 13.57s) without labelling them.
13.57 × 1.15 = 15.6, so the rule had said 20 all along — and CI, which enforced
the locally-derived 15 having never measured it, went red at 15.06s and 15.22s
proving it. Two suites now have numbers, and
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
