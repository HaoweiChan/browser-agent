---
id: DRAFT-69
title: the non-retryable justification for a wrapped certify is unsupported
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-9
  - 'PR #44 R10.'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/judge.py`'s embedded-certify guard raises a NON-retryable JudgeError and justifies it with "an identical second call reproduces that".

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the comment at the guard drops the "identical second call" argument for the anti-resample-bias one (prose only, no behaviour change), or a `full`-suite receipt records the pinned model's real verdict formatting across enough calls to turn the availability cost into a number. If the cache is what blocks the measurement, caching the raw completion beside the parsed verdict is the enabling change and belongs in this block.
<!-- AC:END -->
