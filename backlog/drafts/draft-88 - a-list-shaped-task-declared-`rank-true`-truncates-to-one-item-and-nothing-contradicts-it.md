---
id: DRAFT-88
title: >-
  a list-shaped task declared `rank: true` truncates to one item, and nothing
  contradicts it
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-RANK-MIRROR
  - 'PR #29 R20 (the mirror half; the aggregate half is fixed)'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
a list-shaped task declared `rank: true` truncates to one item, and nothing contradicts it

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a signal that is not a wording regex over `list`/`every`/`each` — that mechanism decided this call three times and was backwards each time (PR #29 R2, R9, R16), so reintroducing it as a decider is explicitly out of scope. Candidates worth a red-first case: a second declaration the executor can cross-check against the evidence (e.g. an expected cardinality the enumeration must satisfy), or an L3 evidence-only check that asks whether one row answers the question. Until then the residual is that the planner's declaration is trusted wherever code has no opinion — which is most tasks.
<!-- AC:END -->
