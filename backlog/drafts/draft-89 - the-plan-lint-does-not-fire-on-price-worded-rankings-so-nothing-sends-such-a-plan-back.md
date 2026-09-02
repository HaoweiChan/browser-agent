---
id: DRAFT-89
title: >-
  the plan lint does not fire on price-worded rankings, so nothing sends such a
  plan back
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-CHEAPEST-WORDING
  - 'PR #29 R4'
  - 'restated at PR #29 R9 and R12'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the plan lint does not fire on price-worded rankings, so nothing sends such a plan back

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either widen `_AGGREGATE`'s second half to the price vocabulary with a watched-red case — and prove it does not drag the fifteen shop-fixture cases whose task says "name the cheapest product" into a lint they have no reason to meet, which is why M31 did not widen it — or run `live-books-cheapest-travel` with a key and record what the planner does now that the verb exists.
<!-- AC:END -->
