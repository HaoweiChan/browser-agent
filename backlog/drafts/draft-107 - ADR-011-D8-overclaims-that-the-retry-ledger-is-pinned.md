---
id: DRAFT-107
title: ADR-011 D8 overclaims that the retry ledger is pinned
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M22
  - 'PR #21 R12'
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the retry probe asserts `"URLError" not in json.dumps(report)`, a substring search the per-row `retries` list already satisfies — so `summarize` can drop `transport_retries` entirely and the case stays green. R3's acceptance is met at the row level; the count and phase live only in the unasserted ledger field.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the probe asserts `transport_retries` content (count + phase at least) so emptying the ledger reddens, or ADR-011 D8 narrows its wording.
<!-- AC:END -->
