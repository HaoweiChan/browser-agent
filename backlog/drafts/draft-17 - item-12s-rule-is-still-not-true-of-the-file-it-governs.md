---
id: DRAFT-17
title: item 12's rule is still not true of the file it governs
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D4
  - 'PR #65 R9 (LOW'
  - routed debt).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
item 12's opening states a rule about its own file — a ledger MAXIMUM stated here carries the marker — and §2's ablation paragraph states two without one: "one of them (74.29s, 162/165) its maximum at this case count" and "one of them again the maximum (75.02s, 162/168)". `_BAND_LEDGER_MAX.finditer(adr)` returns exactly one match, the 230-case one. Unlike R5 there is no staleness exposure — both rows were deleted by `820d807`, `fast` is 229 and counts grow monotonically, and item 12 declares an unmarked maximum invisible. The committed ledger's fast@165 max is 73.36, not 74.29, reconcilable only via the deletion table the same paragraph provides.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 M44-P1-D3's Spec names these two as the concrete surviving instances (they are the only ones), or item 12's opening is phrased as the rule for a LIVE maximum rather than for every maximum the file narrates.
<!-- AC:END -->
