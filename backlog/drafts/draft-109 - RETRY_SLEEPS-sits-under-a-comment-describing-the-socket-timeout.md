---
id: DRAFT-109
title: RETRY_SLEEPS sits under a comment describing the socket timeout
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M25
  - 'PR #21 R15'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`evals/ablation.py` — the "30s was too tight ... raised to ~4x the worst observed stall" block documents `timeout: int = 120`, and `RETRY_SLEEPS = (5, 10)` was inserted between the comment and the `def`, so the comment now reads as describing the backoff tuple.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the constant sits above its own one-line comment, or the existing block names the timeout it describes.
<!-- AC:END -->
