---
id: DRAFT-121
title: 'the band region''s guard pins a named set, not everything band-shaped'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R63
  - 'T-R56 round 4 (PR #36 R19/R20)'
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`published-band-matches-the-ledger` requires every name matching `_band…`, `_check_published_band…`, `_BAND…`, `_SIX…`, `_SLACK_MARK` or `_REGION` to sit between the two region markers, by byte offset, and both markers to start their own line with the closing one outside any body. Eight mutations are red against it (each of the five definitions moved out, band code appended after the end marker, either marker moved into a body, either edge moved inward). What it does not pin is the module-level names outside that set — `_ADR019`, `_README`, `_INDEX`, `_DECIMAL_TOKEN`, `_README_BAND_ROW`, `_ADR_CEILING` — and any band code added later under a name the pattern does not match. None of those carries a §6 reference today. The residue is NOT empty, though, and PR #36's confirming review found why (R22): the 19 lines between the begin marker and the first pinned name are unpinned comment carrying two graded references (`§6 item 8 (references)` and `item 2 (cited-run)`). Moving the begin marker to sit immediately above `_BAND_LINE` leaves `marker_counts == [1, 1]`, `outside_the_region == []` and `markers_off_a_top_level_boundary == False` — green — while the region loses those 19 lines, and a reference corrupted inside them goes from red to green.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the region's contents are pinned positively (the band block is delimited by what it contains rather than by markers — e.g. the check reads its own `__code__` sources), or the pattern is derived from the module namespace rather than written out. Watched red by moving an unpinned constant that carries a §6 reference out of the region.
<!-- AC:END -->
