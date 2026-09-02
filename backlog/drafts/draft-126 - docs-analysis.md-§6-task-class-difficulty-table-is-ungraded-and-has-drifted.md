---
id: DRAFT-126
title: docs/analysis.md §6 task-class / difficulty table is ungraded and has drifted
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R67
  - M28 implementer
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the §6 table says it is "refreshed from the case files' own `tc`/`level`/`domain` tags", but only the golden/adversarial split and the domain rows are graded (`docs-numbers-are-derived`, `analysis_coverage`). Tallying the tags at 148 cases gives TC1 35 / TC4 28 / TC3 13 / TC2 8 / TC5 6 and L1 46 / L2 26 / L4 16 / L3 15 / L5 8; the table carries TC1 32 and L1 36 (M28 bumped each by one for its own case; the rest of the gap predates it). The L3 cell is prose naming cases, which is why nobody regenerated it.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the TC/level counts join `analysis_coverage`'s graded set (derived from the tags, same as the split), or the table is cut down to the graded rows and says so.
<!-- AC:END -->
