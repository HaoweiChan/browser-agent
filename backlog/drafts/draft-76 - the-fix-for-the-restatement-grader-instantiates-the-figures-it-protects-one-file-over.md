---
id: DRAFT-76
title: >-
  the fix for the restatement grader instantiates the figures it protects, one
  file over
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-2-7
  - 'PR #46 R8'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_BAND_RESTATE`'s explanatory comment quotes a band bullet's real numbers in source, where item 9's check never looks — it scans the ADR text only. So on the next case-count move the ADR bullet, the ADR restatement and README all go red together while this comment silently keeps the old figures. This is the exact trap the implementer declared and avoided in ADR-019 §6 item 9 ("the form is described rather than shown, because a literal example here would be a third copy"), reintroduced one file over — which is the strongest evidence yet that "describe the form, never show it" needs to be enforced rather than remembered.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the comment describes the form without the figures (as §6 item 9 does), or `_BAND_RESTATE` is also run over `region` so the illustration is graded. Not a merge blocker: a source comment, not a published band.
<!-- AC:END -->
