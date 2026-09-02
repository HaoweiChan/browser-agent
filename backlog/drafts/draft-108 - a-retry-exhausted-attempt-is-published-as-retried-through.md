---
id: DRAFT-108
title: a retry-exhausted attempt is published as "retried through"
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M23
  - 'PR #21 R13'
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_http` appends the final attempt to the out-list before re-raising, with no success marker, so a connect failure that never succeeded appears in `transport_retries` with `count: 3` and prints under the banner "connect-phase failures that retried through". The same event is reported twice, once with the wrong label — on the exact distinction the ledger was added to make.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 only attempts followed by a success are recorded, or the entry carries `retried_through: bool` and the banner reflects it; a case pins that a fully-failed connect produces an empty ledger.
<!-- AC:END -->
