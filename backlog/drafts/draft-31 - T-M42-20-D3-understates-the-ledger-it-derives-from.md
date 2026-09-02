---
id: DRAFT-31
title: T-M42-20-D3 understates the ledger it derives from
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D8
  - 'PR #60 R9 (LOW'
  - routed to debt — logged
  - >-
    deliberately not fixed in place). `T-M42-20-D3` says "The three runs
    recorded at this count measured 89.60 / 90.08 / 90.49s". At the commit the
    review read
  - the committed `history.jsonl` held FIVE rows at 222 cases
  - 'not three: `20260826-165306` 90.25'
  - '`20260826-165845` 90.08'
  - '`20260826-170244` 89.6'
  - '`20260826-170822` 90.49'
  - >-
    `20260826-171550` 90.27. The two omitted rows include the band source
    itself.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
a debt item that RESTATES a ledger will drift from it; make D3 cite the ledger (suite, env, count) instead of enumerating rows, or teach a check to read enumerated ledger rows out of TODO.md the way the band checks read the ADR.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 no debt block in this file restates ledger rows it does not derive.
<!-- AC:END -->
