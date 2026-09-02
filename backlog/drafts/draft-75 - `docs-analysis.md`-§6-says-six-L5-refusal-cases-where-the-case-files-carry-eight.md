---
id: DRAFT-75
title: >-
  `docs/analysis.md` §6 says "six L5 refusal cases" where the case files carry
  eight
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-2-3
  - T-M40-2 implementation
  - '2026-08-24'
  - >-
    noticed while updating the §6 counts that `docs-numbers-are-derived` DOES
    grade (the golden/adversarial split and the domain rows). Counting `level`
    over `evals/golden` + `evals/adversarial` gives L5 = 8; §6's prose says six.
    Pre-existing and unrelated to T-M40-2's case
  - which is L3.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the TC/level tables in §6 are hand-maintained beside a split line that is derived, which is the exact drift class `docs-numbers-are-derived` exists to close — the check simply does not reach them.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the tables are derived from the case files' own tags by that check, or the prose is corrected and the residue declared.
<!-- AC:END -->
