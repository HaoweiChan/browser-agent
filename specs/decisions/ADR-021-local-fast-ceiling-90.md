# ADR-021: the local `fast` ceiling moves 80s -> 90s, on the number the grader derives

Date: 2026-08-23
Status: accepted

**Ruling**: `WALL_BUDGET_S["fast"]` becomes 90. The value is not chosen — it is what `published-band-matches-the-ledger` reports as `required_by_adr013_rule` from the committed ledger at 146 cases (slowest 74.8s, ADR-013's +15%-round-to-five rule). `invariant` stays 20 and ~~CI's `EVAL_WALL_BUDGET_S_FAST` stays 90~~ — struck 2026-08-26, OVERTURNED by ADR-029 (see the Amended-by line above and the struck section below). Both CI ceilings were re-derived from a measurement of the tree M42 ships; the live values are in ADR-019 §5 and in the workflow, graded against each other. This line survived the first sweep of PR #57 R24 for a reason worth recording: the number ends the sentence, and the guard's lookahead was blind to that position.
**Because**: the suite grew 131 -> 146 cases absorbing M31's, M36's and M32's coverage, and the ledger's slowest run moved with it; every non-ceiling case passes, so the gap is a ceiling derived against a smaller suite, not a threshold moved to hide a failure.
**Enforced by**: `published-band-matches-the-ledger` (derives the number), `fast-wall-clock-budget` (pins the committed ruling), `evals/run.py` `over_budget()`

**Amends**: ADR-019 Decision 2 (local `fast` 80 -> 90; the other three ceilings are unchanged)

**Amended by**: ADR-029 (2026-08-26) — this ADR's CI ruling below is OVERTURNED. Both CI ceilings were re-derived from a measurement of the tree that ships and the workflow declares what they derive; the values live in ADR-019 §5 and are graded against the workflow by `ci-numbers-are-derived`. The local half of this ADR (`fast` 80 -> 90) stands as the step ADR-029 raises from. This header had no `Amended by` line at all for one round, so a reader following the chain reached a ruling the workflow no longer obeyed (PR #57 R25).

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
- **~~CI's `EVAL_WALL_BUDGET_S_FAST` stays 90.~~** (Overturned by ADR-029.) When this was written CI had
  produced no `fast` measurement at all on this branch — its run died at the
  `invariant` step, on the two cases this ADR closes — so this bullet originally
  left 90 in place for want of evidence. It no longer rests on that: CI has
  since measured the shipped tree at 74.25s, the rule applied to that derives 90,
  and the human ruled to leave it there. The CI section below is the account.

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

PR #34 already tried this once. **ADR-020 raised CI's ceiling 80 → 92 [historical] and was
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

## What CI has measured, and the ruling on CI's ceiling

This section has been wrong twice and the corrections are kept rather than
tidied, because the shape of the error is the point: both times it published an
absolute claim about CI that a later run falsified.

The first version headed itself "CI has now measured this tree" when the only
run was on the parent (PR #34 R22). The second version corrected that, and
over-corrected into "no CI run exists for any later commit on this branch" and
"CI has never measured the tree this PR ships" — true when written, false within
the hour, because the merge that carried the correction is what let CI run at
all (PR #34 R28).

**CI has now measured the tree this PR ships.** Run **32639577041** on
**`07e3d34`** — HEAD — conclusion success:

| | wall | ceiling | margin | rule gives |
|---|---|---|---|---|
| CI `fast` on `07e3d34` (152 cases) | **74.25s**, 152/152 = 1.000 | 90 | **17.5%** | 74.25 × 1.15 = 85.39 → **90** |
| CI `invariant` on `07e3d34` (58 cases) | **14.88s**, 58/58 = 1.000 | 20 | **25.6%** | 14.88 × 1.15 = 17.11 → **20** |

The earlier data point stands beside it, because it is real and it is why the
LOCAL ceiling moved. Run **32627229208** measured **`920218e`**, the parent of
the R16 repair, at 146 `fast` / 54 `invariant`: `fast` **88.39s** against 90 —
**1.8%** — and `invariant` 16.79s against 20.

### ~~The ceiling stays at 90, and that is a ruling~~ — OVERTURNED 2026-08-26

**Struck by ADR-029 (PR #57 R25).** Everything below was true of the tree it
measured and is kept for that reason: the reasoning — a ceiling is derived from a
measurement of the shipped tree, not from an absence of evidence — is exactly
what overturned it, applied to a later tree. What is no longer true is the
conclusion. CI has since measured the tree M42 ships, both CI ceilings were
re-derived from it, and the workflow declares those. ADR-019 §5 publishes them
and `ci-numbers-are-derived` grades them against the workflow; no number from
this section is live.

Three things, in order, because the ADR previously left 90 standing on an
absence of evidence and R28 deletes that reasoning:

1. **CI has measured the shipped tree** — 74.25s, above.
2. **ADR-013's rule applied to that measurement derives 90**, the number already
   committed. `74.25 × 1.15 = 85.39 → 90`. The rule asks for no change.
3. **The human was asked and ruled to leave it at 90.** Answered, not deferred.

A raise was asked for, and the honest account of why is that the request was
made against the `920218e` measurement — 88.39s, 1.8% of margin, on a runner
whose spread `fast-wall-clock-budget` records as 6.8%, nearly four times the
margin. On that number a raise looked overdue; applied as a band it would have
asked for 105. **The shipped tree's own measurement removed the premise.** CI
came in FASTER on a LARGER suite — 88.39s at 146 cases, 74.25s at 152 — so the
gap the raise was meant to close is not there on the tree that ships.

~~`EVAL_WALL_BUDGET_S_FAST` stays 90 and `_INVARIANT` stays 20. That is now the
ruled state rather than the untouched default.~~ (Overturned by ADR-029; see the
heading above.) Both values in
`.github/workflows/eval.yml` are unchanged from `origin/main`; the file itself is
not byte-identical any more, because T-R44 added `EVAL_ENV: ci` beside them
(2026-08-23 amendment below) — no ceiling moved.

### What this does NOT claim

Not that the margin question is closed. Ninety is the right number on today's
measurement of today's tree; that is a different claim from "this will not need
revisiting", and the two should not be blurred.

The live version of the question was `T-M32-13`'s second symptom: CI's own rows
enter `ledger max` mid-job — the `invariant` step appends before the `fast` step
grades — so a slow CI `invariant` run could demand a ceiling no local run
justifies, **ungreenable locally** because the local ledger holds no CI rows.
CI's `invariant` measured 16.03s in run 32637648447 and 14.88s here; the next
band starts at **17.39s**. That bound is item 4 (committed-ceiling)'s alone —
item 3 (same-ceiling) compares `rule(published)` with `rule(ledger max)` and had
already fired on a 16.02s CI row in run 32626835735, nowhere near 17.39s
(ADR-019 §7). **Neither is the number to watch any more, and this paragraph is
amended rather than left standing** — see below. This ADR's CI
figures are still hand-read off the workflow log and ungraded; they carry the
run ids that make them checkable by a reader (T-R51's resolution), and the
ledger route stays open as `T-R73`.

One run is still not a band. Two runs of two different trees are not a band
either. What has changed is that the ceiling now rests on a measurement of the
tree it guards plus a decision, instead of on the absence of one.

### (2026-08-23, T-R44) The mid-job CI row no longer reaches `ledger max`

The paragraph above named CI's rows entering `ledger max` as this ADR's live
margin risk. T-R44 removed the mechanism: every history row now carries an `env`
tag and ADR-019 §6 item 9 (environment) filters the ledger to the band's own
environment before any item reads a row, so CI's `invariant` row is not in a
`local` band's ledger at all. Item 3 (same-ceiling), which fired at 16.02s, and
item 4 (committed-ceiling)'s 17.39s threshold with its ungreenable-locally
property, are all unreachable from a mixed ledger, and the paragraph is corrected
above rather than deleted, because the reasoning is why the ceiling is watched at
all.

Two things this does NOT change, and the second is why the block was narrowed
rather than closed. First, nothing about the numbers: 90 still comes from
`required_by_adr013_rule` at 146 cases, CI's figures are still hand-read, and no
ceiling moved. Second, and this is the part to read carefully: `T-M32-13` named two symptoms
and they are two properties, so T-R44 shipped two fixes. Env scoping closed this
ADR's margin risk; `ts` stamped in UTC closed the ordering key that made a dirty
citation cost a second commit. Neither substitutes for the other and ADR-019 §7
keeps them apart on purpose. What is NOT converted is the ledger's history: rows
written before that commit keep their naive local stamps and are not rewritten,
so any figure in this ADR quoted with a `ts` older than it is a local-time
stamp.
