---
id: DRAFT-117
title: >-
  CI's ceilings were measured on a tree two milestones smaller than the one that
  ships
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R58
  - T-R56 (sweep
  - beyond the eight folded blocks)
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-019 §5 and README both introduced their CI numbers as "four attempts of the shipped tree" / "measured on CI at the shipped case count". The four attempts are of `d173340`, which had 116 `fast` and 48 `invariant` cases; this branch ships 136 and 53. The description is repaired (both now name the commit and say it is the smaller tree), so what is left is the measurement gap: CI's 90/20 derive from a band 20 `fast` cases old, and nothing reddens when the local tree grows past the tree CI's ceiling was measured on. The local half has exactly this guard — §6 item 1 (count), published case count == current case count — and the CI half has no equivalent because no CI wall clock reaches the ledger (T-R51).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CI's band carries the case count it was measured at, and something reddens when the current count leaves it behind — the natural form is T-R51's environment dimension on `_BAND_LINE` plus item 1 (count) applied to it. Watched red by growing the suite against a stale count.
<!-- AC:END -->
