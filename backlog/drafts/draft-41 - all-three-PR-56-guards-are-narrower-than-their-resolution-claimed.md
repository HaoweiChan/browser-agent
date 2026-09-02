---
id: DRAFT-41
title: 'all three PR #56 guards are narrower than their resolution claimed'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D7
  - 'PR #56 R10 and PR #56 R11'
  - 2026-08-26. Both routed to debt as LOW
  - >-
    and filed together because they are one defect with three instances: a guard
    written in a repair round is red-capable for the literal thing that round
    was about
  - >-
    and its resolution record then describes it as covering the CLASS. The loop
    hit this three times
  - >-
    which is the signal that guard-scope claims in this repo need pinning rather
    than more guards. It partially reopens round 1's R1
  - >-
    whose acceptance said the cost label "cannot drift from the data again" — it
    demonstrably still can
  - >-
    and `tasks/reviews/pr56-r1-resolution.json` has been corrected so its R1
    entry no longer reads a clean `fixed`.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
two clauses in `_run_doc_counts_case` (`src/browser/eval_adapter.py`) are red-capable for their literal targets but miss adjacent mutations, carried verbatim from R10. (1) `forbidden_claims` compares case-SENSITIVELY, so a forbidden phrase re-introduced at the start of a sentence — "Corrected after M45" — passes. The fix is `.lower()` on both sides; it is one word and was deliberately NOT taken in the round-2 repair, because R10 was severity-routed to debt and a repair round that quietly widens findings it was told to defer is how a review loop stops terminating. The clause carries a `ponytail:` comment saying exactly that. (2) `probe_cost_column` sums the published cells against the probe report's own total but never reads the column HEADER, which was the actual R1 defect: flipping it back to "Cost (planner only)" leaves the case green while re-creating the label/data disagreement R1 filed. (3) `block_must_contain` (PR #56 R11) never reads the pointers it exists to protect: it hardcodes the target heading, so it verifies that `### M45-D8` exists and carries "request frame"/"imperative", and verifies nothing about the four surfaces that point at it. Mutation carried verbatim from R11: `perl -pi -e 's/M45-D8/M45-D4/g' src/browser/agent.py docs/analysis.md docs/support-matrix.md evals/adversarial/screening-zh-term-inside-another-word.json` — the literal R8 state, all four pointers aimed at a block with no request-frame content — leaves `docs-numbers-are-derived` GREEN. Control, confirming coverage rather than vacuity: renaming the heading to `### M45-D10` yields `{'pointer_target_missing': '### M45-D8'}`. As with (1), R11's record-correction half was NOT deferred — `tasks/reviews/pr56-r2-resolution.json`'s R8 entry is annotated to say the guard pins the target's contents and not the pointers.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `forbidden_claims` lowercases both sides and the mutation "Corrected after M45" goes red; `probe_cost_column` gains the header literal to its checked set and the mutation "Cost (planner only)" goes red; `block_must_contain` resolves the debt id it actually finds at each pointer site (doc + surrounding literal) rather than taking the heading from its own config, so R11's four-pointer retarget goes red. All three watched red first, on those exact three mutations. Gate green.
<!-- AC:END -->
