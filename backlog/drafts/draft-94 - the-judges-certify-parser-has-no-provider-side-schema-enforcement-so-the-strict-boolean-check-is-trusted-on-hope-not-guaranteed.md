---
id: DRAFT-94
title: >-
  the judge's certify parser has no provider-side schema enforcement, so the
  strict boolean check is trusted on hope, not guaranteed
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R33
  - 'PR #33 R3 (MEDIUM'
  - routed debt)
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the judge's certify parser has no provider-side schema enforcement, so the strict boolean check is trusted on hope, not guaranteed

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 add `response_format` to the request (`json_object` is the safe, widely-supported floor; `json_schema` with a strict `{"certify": boolean}` schema is the real fix if `deepseek/deepseek-v4-flash-0731` supports it) and verify it against a live call before trusting it — an untested schema constraint added here would be exactly the kind of unwatched change PR #33 R3 warned against, just moved one layer down.
<!-- AC:END -->
