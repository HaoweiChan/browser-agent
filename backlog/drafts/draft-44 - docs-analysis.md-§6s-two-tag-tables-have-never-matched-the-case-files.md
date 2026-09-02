---
id: DRAFT-44
title: docs/analysis.md §6's two tag tables have never matched the case files
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D1
  - M45
  - >-
    2026-08-26. Found while refreshing §6's total for the one case M45 adds; not
    caused by M45
  - and not repaired by it under the debt rule.
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`## 6. Coverage` publishes a task-class table and a difficulty table whose cells are described as "refreshed from the case files' own `tc`/`level`/`domain` tags rather than recounted by hand". They are not. Measured 2026-08-26 (`for f in evals/{golden,adversarial}/*.json`, counting `tc` and `level`): TC1 57 published 54, TC2 8 ✓, TC3 13 ✓, TC4 36 ✓, TC5 6 ✓, untagged 73 published 72; L1 58 published 57, L2 48 ✓, L3 19 published 17, L4 16 ✓, L5 9 published 8, untagged 43 ✓. The published cells have never summed to the published total (189 vs 193). The drift predates this branch — the same recount at the parent commit gave TC1 56, L1 58, L3 19 against identical published cells — and it survived because `docs-numbers-are-derived` grades the golden/adversarial split quote and the domain rows and NOT these two tables, while the paragraph above them advertises that it does. M45 declared the drift in place (§6, with the measured numbers) rather than half-repairing a table whose other cells it had not put into error. This is the third time §6 has drifted under a preamble claiming it does not: T-M39-5 (closed) was the same defect on the section's OTHER pair of numbers, and its own closing note states the rule this block re-earns — "a number no check recomputes is a number that goes stale again". T-M39-5 widened the grader to cover the pair it found and stopped there; these two tables were the part it did not reach.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `docs-numbers-are-derived` grows a clause that recomputes both tag tables from the case files the way it already recomputes the domain rows, the cells are refreshed to match, the §6 paragraph's claim becomes true, and the declaration M45 left in §6 is deleted in the same commit. Watched red first by publishing one cell off by one. Also in scope for this block, found by M45's spec-drift audit: `docs/analysis.md` §1 says "The **six** L5 refusal cases" and §7 says "**6** refusal cases", while L5 measures 9 and the table publishes 8. Same defect, same section's blast radius, and M45's own case is one of the three the sentence is short by — so it is repaired by the same recount rather than left to drift a fourth time.
<!-- AC:END -->
