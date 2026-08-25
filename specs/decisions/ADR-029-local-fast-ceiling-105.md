# ADR-029: the local `fast` ceiling moves 90 → 105, because 26 cases moved the tree and the rule says so

Date: 2026-08-26
Status: accepted

**Ruling**: `WALL_BUDGET_S["fast"]` moves from 90s to **105s** for the LOCAL environment only, taken from ADR-013 Decision 3's rule applied to this tree's own committed ledger rather than chosen; CI's `EVAL_WALL_BUDGET_S_FAST` **stays at 90** because nothing in this change measured CI, and ADR-019 §5's four CI numbers are hand-read off a named workflow run — a number I cannot take from here is a number I may not write; `invariant` is untouched at 20s, which its own ledger rows still derive.
**Because**: M42 added 26 cases to `fast`, which is growth in CASE COUNT and not in per-case cost — the exact condition ADR-021 named when it said "if a future gap comes from per-case cost the answer is removing waste (T-M32-3), not another raise"; the tree measured 73.06s at 181 cases and the new cases cost ~7s of real browser work between them, so the band crosses a ceiling step and ADR-013's rule derives 105 from it.
**Enforced by**: `published-band-matches-the-ledger` (items 3, 4 and 5 are what force this file to exist rather than letting the band be re-typed), `fast-wall-clock-budget` (whose boundary rows move to 105.00/105.01 in the same change, watched red first), `evals/run.py`'s `over_budget()`.

---

## Context

ADR-019 gives each (suite, environment) its own ceiling, derived by ADR-013's
rule — slowest observed +15%, rounded up to a multiple of five — from a band
computed out of `evals/report/history.jsonl`. ADR-021 last moved the local
`fast` number, 80 → 90, on a band at 146 cases.

At 181 cases the tree measured 73.06s, which derives 85 and sat one step under
the committed 90. M42 adds 26 cases — twenty-one from the milestone itself, five
more from its review round — and every one of them that drives a browser costs
real wall clock. The band moves past the step boundary, and `published-band-
matches-the-ledger` items 3 and 4 refuse a band whose derived ceiling is above
the committed one. That refusal is the mechanism working: a suite that got
slower has to say so, in the document of record, before the gate goes green
again.

## Decision

### 1. Local `fast`: 105s, derived and not chosen

The number is `_band_rule(max)` over the local rows at the current case count,
which is the same function `published-band-matches-the-ledger` uses to grade it.
Nothing here is hand-arithmetic; ADR-019 §2's republished band bullet carries
the cited run and the arrow, and item 5 grades that the arrow is the rule's own
answer. It comes out at **105s**: 87.96s measured, × 1.15 = 101.15, rounded up
to a multiple of five.

Two steps, not one, and the second step is machine variance rather than case
count. The same tree measured 84.83s and 88.87s within the hour, and the 73.06s
this band replaces was recorded in a quieter session on the same laptop — which
is exactly the property ADR-013's rule is built around (SLOWEST observed, not
median) and exactly what T-M39-13 warns makes a band fragile. Publishing the
median would be choosing rather than deriving, and would leave the next honest
gate run red.

### 2. CI stays at 90, and that is a statement about evidence, not about speed

ADR-019 §5's four CI measurements are hand-read off the log of a named workflow
run, because no CI run appends to this repo's ledger (§7, T-R51, T-R73). I have
no CI measurement of this tree, so I have no number to derive one from, and
`_check_ci_numbers_are_derived` exists precisely to stop the two documents that
publish CI's ceiling from drifting apart on a number nobody measured.

**Stated rather than discovered later**: CI is likely to breach 90 on this
branch. It measured 74.25s at 152 cases; this tree is 207. Extrapolating is not
deriving, so no number is written on the strength of it — but a reader should
expect the PR's own CI run to be the measurement that settles CI's ceiling, and
should treat a red CI wall clock on this branch as the expected next step rather
than as a surprise. That is the ADR-021 pattern exactly: its CI figures came
from a run that had already happened, cited by id.

### 3. What was NOT done, and why the offer was refused

Trimming cases to stay under the old ceiling was available and is the wrong
trade. The three most expensive additions are the three that carry the most:
`action-wait-for-that-never-holds-is-loud` burns the full settle budget *because
that is the postcondition it grades*, and the two `wait_for` successes pay a
fixture's paint delay because the postmortem's S1/S4 shape is a page that paints
late. A ceiling that can only be met by deleting the cases that measure the
milestone is not a ceiling, it is a cap on evidence.

The other refused option was the quiet one: publishing a band the ledger does
not support, or keeping probe rows out of the committed ledger until a fast
enough run happened to appear. T-M39-13 already documents that treadmill; this
ADR pays the cost openly instead.

## Consequences

- The local gate has ~15% headroom again at 207 cases, where it had ~5% before
  this change and would have had none after it.
- A wider ceiling catches drift later. That is the real cost of every raise, and
  ADR-021 named it first: the answer to per-case cost growth is removing waste,
  not another raise. This raise is case-count growth, and the next one should
  have to prove the same thing.
- `fast-wall-clock-budget`'s boundary rows move with the number, so the case
  keeps testing the boundary rather than a number it used to be.
- Local and CI now publish different `fast` ceilings (105 vs 90). ADR-019 §4
  already rules that per-environment numbers are independent and read through
  one override variable per suite, so this is the design working; it is
  nonetheless the first time local has been the LOOSER of the two, which is a
  reason to re-derive CI's promptly rather than to leave it.
