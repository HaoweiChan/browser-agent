---
id: DRAFT-74
title: the planner system prompt says nothing about container targets
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-2-2
  - T-M40-2 implementation
  - >-
    2026-08-24. `src/browser/planner.py`'s system prompt tells a model to
    `observe` a container it can see but cannot read into; nothing tells it not
    to `extract` from one. The runtime correction exists (ADR-024's refusal is
    replanned with a note naming the offending role)
  - but it costs a planner round trip on every occurrence.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
a prompt line is a one-line diff and plausibly prevents the loop entirely. Held out of T-M40-2's PR for the same attribution reason as T-M40-2-1, and with the same ceiling: a prompt change is graded offline only by `_check_planner_prompt` (that the string is assembled), never by whether a model obeys it — the `full` suite is the only place that could measure obedience and it spends tokens.

Depends (TODO.md ids): T-M40-5

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 taken with T-M40-2-1 after T-M40-5's probe, or dropped if the probe shows the lint alone recovers the rows.
<!-- AC:END -->
