---
id: DRAFT-120
title: the adapter's self-described line count is stale
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R65
  - 'PR #36 R24'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/eval_adapter.py:363`, reflowed by `ed23223`, still reads "not the whole 3,900-line adapter"; `wc -l` is 4,079. Rhetorical rather than a graded scalar — nothing reads it — but it is a stale number in a line that commit touched, and the same class this task was opened for.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 drop the figure ("the whole adapter") rather than round it, since any figure here goes stale by construction.
<!-- AC:END -->
