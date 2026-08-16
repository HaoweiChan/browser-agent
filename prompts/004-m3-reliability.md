# 004 — M3: recovery ladders, and the metrics that refused to flatter them

**Date**: 2026-08-16 · **Milestone**: M3 · **Outcome**: 49/49 fast, 10/10
invariant, $0.00; classifier + two ladders + budgets; ADR-003 sets what can
honestly be measured and what stays unset.

## Context

The scope checkpoint (`docs/evals/scope-checkpoint.md`) was written before any
M3 code, precisely so the mechanism choice would follow the *observed* failure
distribution rather than the interesting-sounding one. Twelve real failures:
`locate` 4, `act` 4, silent-semantic 3, `env` 1.

The instruction that shaped the milestone was to build **two** families and
refuse a third. The checkpoint's most useful paragraph is the one arguing
*against* work: six of the twelve failures were not recovery problems at all —
they were a parser, a fixture, an accumulator, a truth value, a control-flow
chain and a number format. A ladder for any of them would have been machinery
wrapped around a bug.

## Assumption → Eval contradiction → Correction

- Assumed: passing the DOM-mutation suite is evidence of self-maintenance, so
  "4/4 mutations passed" is the number to report.
  Eval said: only `button-text-renamed` breaks a tier a plan was actually
  standing on. `ids-renamed` and `wrapper-nesting` pass **without relocating
  anything**, because no plan depended on the tiers they break.
  Corrected: the adapter counts `mutation_recovered` separately from
  `mutation_passed`, so the honest line reads "4/4 passed, **2 by relocating**"
  and cannot be quietly rounded up. ADR-002 had predicted this exact flattery
  in advance, which is the only reason it was caught.

- Assumed: a bounded loop that gives up is safe as long as it stops.
  Eval said: a replan loop ran until the *action* budget tripped and reported
  `failure:env` — an environment class for a run that died of an unfixable
  `act`. That corrupts the very failure distribution the next scope checkpoint
  would read.
  Corrected: ladder budgets exhaust as the class the ladder was fixing;
  run-level budgets exhaust as `env`. INV-3 makes every one of them loud, with
  `inv3-budget-exhaustion-loud` plus the end-to-end `budget-replans-exhausted`.

- Assumed: a replanner that returns the same plan is harmless — it just fails
  again.
  Eval said: it loops until an unrelated budget trips, then reports the wrong
  cause.
  Corrected: an identical replacement plan is refused as no-progress *before*
  it costs a budget unit.

- Assumed: recovery deserves a headline rate.
  Eval said: three injected cases is not a population.
  Corrected: it is printed as `3/3 verified (6 rungs tried)` — the denominator
  and the attempt count visible — and ADR-003 records that recovery-as-a-rate
  stays unset until a live suite gives it one.

## What the AI got wrong here, kept for the record

The first instinct was to build a *third* family (a `semantic` ladder) because
it was the most intellectually interesting. The checkpoint document existed
specifically to make that refusable, and it did: the silent-semantic failures
were all fixed by correcting code, not by adding recovery. The lesson worth
carrying is that the guard has to be written down *before* the implementation
session, when refusing is still cheap.
