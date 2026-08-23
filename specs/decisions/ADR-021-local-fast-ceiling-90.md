# ADR-021: the local `fast` ceiling moves 80s -> 90s, on the number the grader derives

Date: 2026-08-23
Status: accepted

**Ruling**: `WALL_BUDGET_S["fast"]` becomes 90. The value is not chosen — it is what `published-band-matches-the-ledger` reports as `required_by_adr013_rule` from the committed ledger at 146 cases (slowest 74.8s, ADR-013's +15%-round-to-five rule). `invariant` stays 20 and CI's `EVAL_WALL_BUDGET_S_FAST` stays 90.
**Because**: the suite grew 131 -> 146 cases absorbing M31's, M36's and M32's coverage, and the ledger's slowest run moved with it; every non-ceiling case passes, so the gap is a ceiling derived against a smaller suite, not a threshold moved to hide a failure.
**Enforced by**: `published-band-matches-the-ledger` (derives the number), `fast-wall-clock-budget` (pins the committed ruling), `evals/run.py` `over_budget()`

**Amends**: ADR-019 Decision 2 (local `fast` 80 -> 90; the other three ceilings are unchanged)

---

## Context

`published-band-matches-the-ledger`, the grader M31 added in ADR-019, went red
on the merged tree and said exactly what was wrong:

```
suite fast · ceiling 80 · ledger_slowest 74.77 · required_by_adr013_rule 90
```

Nothing was breached. The runs of the merged tree measure **73.55 / 74.35 /
74.59 / 74.77s at 146 cases**, all comfortably inside the committed 80. What
exceeded 80 is ADR-013's own rule applied to that new maximum: 74.77 × 1.15 =
86.0, rounded up to a multiple of five → **90**.

Those are the numbers at the moment of the decision, quoted as the grader
reported them. The live band is in ADR-019 §2 and moves as runs accumulate —
it reads 74.81s over 12 runs as this lands, which derives the same 90. That is
by design: `published-band-matches-the-ledger` compares the ceiling the
published band DERIVES with the one the ledger derives, not the seconds
themselves, so ordinary run-to-run variance does not redden a doc.

## Decision

**`WALL_BUDGET_S["fast"] = 90`**, and nothing else moves:

- **`invariant` stays 20.** It grew 51 → 54 cases and still derives 20 from the
  same rule (slowest 13.43s → 15.4 → 20). CI's `invariant` step ran 16.79s
  against it.
- **CI's `EVAL_WALL_BUDGET_S_FAST` stays 90 in this decision.** When this was
  written CI had produced no `fast` measurement at all on this branch — its run
  died at the `invariant` step, on the two cases this ADR closes. One `fast`
  measurement has landed since, on the PARENT commit and not on this tree; the
  section below says exactly which tree that was, and it is not evidence enough
  to move a per-environment ceiling on its own.

**The number came from a grader, not from arithmetic in a commit message**, and
that is the whole difference between this decision and the one before it. The
band it reads is computed from `evals/report/history.jsonl`; the rule is
ADR-013's; the case fails when the committed ceiling is below what the rule
derives and stays failing until someone changes one of them. Nobody had to be
trusted to do the multiplication.

## Why this is not moving a threshold to make a red run green

- **Every non-ceiling case passes.** 144 of 146 on `fast`, and the two reds are
  this ceiling gap and the `docs-numbers-are-derived` cascade off it — no
  correctness failure anywhere in the suite.
- **The breach tracks case count, not per-case cost.** The suite went from
  main's ~131 to 146 by absorbing M31's plan-lint and `extract_all` cases,
  M36's judge cases and M32's drill-down cases. That is coverage.
- **The distinguishing test, stated so it can be applied against us later:** if
  a future gap comes from per-case cost RISING rather than case count rising,
  the answer is removing waste, not raising the number again. `T-M32-3` is the
  standing record of the part of this suite that is arguably waste — five
  act-failure cases paying a full `SETTLE_BUDGET_MS` each — with its corrected
  cost model (only a *postcondition* failure pays the settle loop; an act
  failure raised inside `execute` is free).

## The second ceiling decision in this PR, and why the first was withdrawn

PR #34 already tried this once. **ADR-020 raised CI's ceiling 80 → 92 and was
reverted** (`744b7a6`), and a reader should be able to see why that one was
withdrawn and this one was not:

| | ADR-020 (reverted) | ADR-021 (this) |
|---|---|---|
| where the number came from | arithmetic in a commit message, by hand | `published-band-matches-the-ledger`, from the committed ledger |
| what it answered | a CI failure that M31 had already fixed by raising CI to 90 | a gap no other change closes |
| the variable it set | `EVAL_WALL_BUDGET_S`, which M31 had renamed per-suite — so it would have applied no ceiling at all | `WALL_BUDGET_S["fast"]`, the ruling itself |
| rounding | dropped the round-to-five half by hand | the grader's rule, unmodified |

The first was a duplicate answer to a settled question, derived by the same
hand that wanted the answer. This one is the answer a committed case computed
and refused to stop reporting.

## What CI has measured — and which tree it was

Written before CI had run `fast` on this branch at all, this section said the
first green CI run would be the evidence and declined to predict it. A run
happened, and the first version of this section then headed itself "CI has now
measured this tree", which was not true and is the finding this paragraph
exists to correct (PR #34 R22). The numbers below all verify; the tree they
describe is the one to read carefully.

Run **32627229208** measured commit **`920218e`** — the PARENT of the R16
repair, at 146 `fast` cases and 54 `invariant`:

| | wall | ceiling | margin |
|---|---|---|---|
| CI `fast` on `920218e` | **88.39s**, 146/146 = 1.000 | 90 | **1.8%** |
| CI `invariant` on `920218e` | 16.79s, 54/54 = 1.000 | 20 | 16% |

**No CI run exists for any later commit on this branch.** `gh run list
--commit 8d38c52` and `--commit d60da88` both return nothing, because PR #34
went `CONFLICTING` against `main` and GitHub silently runs no checks on a dirty
PR — which is also why the R16 repair itself shipped with zero CI verification
until the merge that carries this correction. The tree this PR now ships is
larger again: the `origin/main` merge plus this round's own case take `fast`
past 146.

**1.8% is a coin flip on this runner, and the repo has twice ruled that a coin
flip is not a ceiling.** `fast-wall-clock-budget` records `ubuntu-latest`'s own
spread on byte-identical code as 6.8% — nearly four times the margin. The first
version of this section called a red CI `fast` run "predicted on the next case
anyone adds", as though that were a future event; the case it was predicting
against (`observe-drilldown-replan-is-linted`) was added by the same commit,
and this round adds another, so **the prediction is already due rather than
pending**. When it lands it should be read as this line coming due, not as a
regression in whatever change happens to be in flight.

That is stated, not acted on here. Raising CI's ceiling is a separate decision
and the human's to make — and unlike the local number this ADR moves, there is
no grader demanding a specific value: CI's evidence is one run, on the wrong
tree, and ADR-019's rule wants a band. `EVAL_WALL_BUDGET_S_FAST` stays 90 in
this ADR and `.github/workflows/eval.yml` is untouched by it.

## What this does not fix

The ceiling is per-environment, and CI's `fast` number is still the one M31
derived from CI runs of a smaller tree. The measurement above is one data
point, taken at 146 cases on a commit this branch has since moved past; one run
is not a band, which is exactly why it is recorded here as a warning rather
than used to re-derive anything. **CI has never measured the tree this PR
ships**, and nothing in this ADR should be read as saying otherwise.
