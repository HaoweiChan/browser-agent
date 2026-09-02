---
id: DRAFT-2
title: 'the residual after the state-change guard: effects outside `STATE_CHANGING`'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M46-3
  - M46 implementation
  - >-
    cold review finding 1; guard built at PR #78 R1 and broadened at R8 (ADR-037
    Decision 2a).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
escalation now refuses to re-run a task whose plan leg holds ANY `verifier.STATE_CHANGING` step — `click`, `press`, `go_back`, `click_at` — whatever its `postcondition_ok` and whether or not it succeeded. What that does

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a fixture that COUNTS submissions rather than keeping the last one, plus an adversarial case driving a plan leg that commits through `fill` (or a mutating `navigate`) and dies after — asserting whichever policy is then decided, watched red against the other. M52's live campaign reports whether any retrying run committed a side effect twice.
<!-- AC:END -->
