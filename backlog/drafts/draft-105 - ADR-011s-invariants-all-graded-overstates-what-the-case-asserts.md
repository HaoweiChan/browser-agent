---
id: DRAFT-105
title: 'ADR-011''s "invariants, all graded" overstates what the case asserts'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M20
  - 'PR #21 R9'
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 3 lists five invariants as graded. Invariant 5 (starts nothing, spends nothing) is asserted nowhere, and every sample comes from a single submission — so moving `ACTIVE_RUN = run_id` out of `async with SEM` to submit-time leaves `readyz-tracks-the-run-slot` PASSING, i.e. `active_run_id` non-null while `busy` is false is undetectable. The reviewer confirmed the seven-ablation claim in Decision 5 does reproduce; this is the eighth mutation.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the ADR narrows "all graded" to what the case asserts, or the case adds a second in-flight submission so the state is detectable — watched red.
<!-- AC:END -->
