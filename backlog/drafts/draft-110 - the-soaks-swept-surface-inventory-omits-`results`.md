---
id: DRAFT-110
title: the soak's swept-surface inventory omits `results`
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M26
  - 'PR #21 R17'
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`summarize` returns 13 keys; the round-2 inventory accounts for 12 and omits `results` — the per-row evidence body every committed soak report and D20's row-level recomputation rest on. Blanking it leaves the case green, and the retry probe's substring check still passes because `transport_retries` carries the string, so nothing reddens when the artifact loses all its evidence rows. The case's triage note also calls `transport_retries` "the remaining published field" when five are unasserted.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a `want` dict asserts `len(report["results"]) == len(rows)`, or the inventory and the triage sentence name `results` and the passthrough group so the sweep claim is honest about what it does not cover.
<!-- AC:END -->
