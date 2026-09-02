---
id: DRAFT-122
title: >-
  `capture.py` reconstructs the executor's claim from extractions, which
  diverges from what verify() judged for extract_all + rank plans
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R70
  - 'PR #38 R3 (LOW)'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
capture.py's reconstruction of the executor's claim from `extractions` diverges from what verify() actually judged for an `extract_all` + `rank: true` plan (verify saw the ranked scalar; the label would record the flat value list). Evidence: evals/labels/capture.py:250-253 (`vals[0] if len(vals)==1 else vals`) vs src/browser/agent.py:712-735 + rank() at agent.py:951-955. No current RECORDS entry uses extract_all, so not triggered today.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A comment naming the ceiling (ponytail:) or reconstruct via the same rank() path.
<!-- AC:END -->
