---
id: DRAFT-130
title: >-
  §6 does not say who wins when item 2's cleanliness rule and the residue rule
  pick different rows
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R88
  - 'PR #45'
  - >-
    found while re-deriving bands after the f813af5 merge; the headroom half of
    the original block was wrong and is corrected by T-R90 (PR #45 R9) — read
    that first
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
at a case count that is NOT new, a clean row can already stand in the ledger, and then item 2 (cited-run) forces the citation to be it: a dirty row is red once a clean one stood by its ts. ADR-019 §6's residue rule independently says republish the maximum. When the maximum is dirty and a clean row is not, the two rules select different rows and nothing states which wins. It happened on this branch at `invariant`/59: item 2 forced `20260824-000935` (13.12s, clean) while the maximum was 14.62s and dirty. Cleanliness won because item 2 is graded and the residue rule is prose — but that is an accident of enforcement, not a decision anyone recorded.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 §6 states which rule wins and why, in one sentence, and `_band_wrong` either enforces it or §6 records that it does not — the same "what is graded vs what is asserted" split §6 already makes elsewhere.
<!-- AC:END -->
