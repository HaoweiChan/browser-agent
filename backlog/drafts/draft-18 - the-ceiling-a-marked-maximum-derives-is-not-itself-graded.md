---
id: DRAFT-18
title: the ceiling a marked maximum derives is not itself graded
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D5
  - 'PR #65 R10 (LOW'
  - routed debt).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
§2 writes "(ledger max — `fast` at 230 cases: **91.76s**) — derives **110**" and "while the marked maximum above still derives 110". `_BAND_DERIVATION` only matches the `x × 1.15 = y → **N**` form and only for published bands, so neither 110 is read back. If `fast` returns to 230 and a 95.7s row lands, the marker goes red and is repaired to 95.70 — whose rule value is 115 — and both "110" sentences stay green. Repairing the graded scalar leaves the ungraded one beside it wrong, which is the shape M44-P1 spent three rounds on.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the derived ceiling either travels inside the marker (one edit moves both scalars) or is dropped from the prose, matching item 5's rule for band derivations.
<!-- AC:END -->
