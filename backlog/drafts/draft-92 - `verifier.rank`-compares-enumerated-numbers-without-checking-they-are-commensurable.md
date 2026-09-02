---
id: DRAFT-92
title: >-
  `verifier.rank` compares enumerated numbers without checking they are
  commensurable
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-RANK-UNITS
  - M31 implementation (`specs/decisions/ADR-018-m31-plan-lint.md` Decision 2)
  - found while writing the reduction
  - out of that milestone's scope.
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`verifier.rank` compares enumerated numbers without checking they are commensurable

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a mixed-currency / mixed-unit enumeration is refused the way a tie already is (`ValueError` -> `failure:semantic`), watched red first. Deliberately NOT done in M31: no enumeration in this repo produces one — every `extract_all` in the eval set reads one column of one page — and the ponytail comment on `rank` names the ceiling and this upgrade path.
<!-- AC:END -->
