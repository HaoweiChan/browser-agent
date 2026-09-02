---
id: DRAFT-106
title: 'the soak''s mid-run readiness probe is one instant, not a series'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M21
  - 'PR #21 R10'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`soak.py` captures `mid` once, ~2s after submission, in runs lasting 4.7-13.7s — and at ~2s the run is provably inside an await (playwright launch, navigate, observe, the awaited planner call). D20 and ADR-011 D7 say "measured ten times", which is ten single instants, not ten runs observed throughout. Both documents already hedge ("narrowed, not eliminated"), which is why this is LOW.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the probe samples repeatedly across the run and the report carries the series, or both documents say "one probe per run, taken ~2s in".
<!-- AC:END -->
