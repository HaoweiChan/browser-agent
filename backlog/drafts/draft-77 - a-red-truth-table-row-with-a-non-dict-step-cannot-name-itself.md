---
id: DRAFT-77
title: a red truth-table row with a non-dict step cannot name itself
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-2-8
  - 'PR #46 R9'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`plan-gap-truth-table`'s failure-report comprehension calls `s.get` on every step of a failing plan, so a future regression on one of the non-dict rows surfaces as a bare AttributeError with no row named. The gate still goes red — only the diagnostic is useless, which is the half that costs someone an hour at the point they most need the row's identity.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the report builder tolerates a non-dict step (e.g. `s.get("action") if isinstance(s, dict) else s`) so a red row names its plan.
<!-- AC:END -->
