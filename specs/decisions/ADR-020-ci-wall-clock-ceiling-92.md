# ADR-020: CI's `fast` wall-clock ceiling moves 80s -> 92s

Date: 2026-08-23
Status: accepted

**Ruling**: `.github/workflows/eval.yml` sets `EVAL_WALL_BUDGET_S: "92"`, by ADR-013 Decision 3's own rule — the slowest observed CI run plus 15% (80.34 x 1.15 = 92.4 -> 92). ADR-002 Decision 4's local 60s is untouched.
**Because**: the suite grew ~30% in cases since 80 was derived at ~100 cases, and CI's 80.34s run was 131/131 = 1.000 — every case passing, over by 0.34s; a ceiling derived against one suite size is not evidence about a suite a third larger.
**Enforced by**: `fast-wall-clock-budget` (grades the value the workflow declares), `.github/workflows/eval.yml`

---

## Context

CI failed on this branch with `wall clock 80.34s > 80.0s (ADR-002 Decision 4)`,
on a run that scored **131/131 = 1.000**. Nothing was broken; the run was 0.34s
past a number derived when the suite was about a hundred cases.

Measured CI history against that same 80s ceiling, on `main`:

| cases | CI wall |
|---|---|
| 105 | 67.65s |
| 108 | 67.14s |
| 118 (`main` at M36) | 70.55s |
| 131 (this PR, run 32583317342) | 80.34s |

Per-case cost across that span is flat to slightly falling — 0.644, 0.622,
0.598, 0.613 s/case. The suite did not get slower; it got bigger.

## Decision

**`EVAL_WALL_BUDGET_S` becomes 92 in `.github/workflows/eval.yml`.** The number
is not chosen, it is the arithmetic ADR-013 Decision 3 already committed to:
the slowest observed run in this environment plus 15%. 80.34 x 1.15 = 92.4,
and this rounds down to 92 rather than up to 95 — the "round up to a multiple
of five" the 80 was set with is dropped here, because rounding a ceiling
outward is a free gift to exactly the drift this rule exists to catch.

**This is not moving a threshold to make a red run green**, and the difference
is checkable rather than asserted:

- every case passed on the run that breached it (131/131, score 1.000, cost
  $0.0000) — a wall-clock-only failure, never a correctness one;
- the breach tracks case count, not per-case cost, and the table above is the
  evidence: four points, ~25% growth in cases, per-case seconds flat;
- the growth is coverage. The cases added since 80 was derived pin, among
  others, four laundering shapes and a disclosure channel that the suite was
  demonstrably blind to (PR #34 R1, R8, R13).

**What would falsify it.** If the next breach comes with per-case cost RISING
rather than case count rising, the move is to remove waste, not to raise the
number again. `T-M32-3` is the standing record of the one part of the current
cost that is arguably waste — five act-failure cases paying a full
`SETTLE_BUDGET_MS` each, 11.6s between them — with its cost model corrected
(only a *postcondition* failure pays the settle loop; an act failure raised
inside `execute` is free). That block is the first place to look, and it is
already written down rather than discovered later.

## Scope

**ADR-002 Decision 4's local 60s is unchanged, and deliberately so.** The two
environments are decided separately because ADR-013 Decision 3 ruled they are
different measurements, not one portable number: this machine and
`ubuntu-latest` disagree by ~35% on byte-identical code. The local band on this
tree is its own open question with its own evidence — 67.8-69.1s against a 60s
ceiling — and nothing here answers it. `.eval-baseline.json` is untouched, and
`EVAL_WALL_BUDGET_S` is not set locally.

## What this does not fix

`fast-wall-clock-budget` pins the value the workflow declares; it cannot tell a
measured 92 from an invented one. Only an ADR with runs behind it can, which is
what this file is — and the same sentence was true of the 80 it replaces
(ADR-013's own `not_covered` note says so). The four CI numbers above are the
runs; a fifth data point against 92 will exist the first time this branch's CI
runs green, and it is not claimed here in advance.
