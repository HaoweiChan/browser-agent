---
id: DRAFT-82
title: act-failure coverage costs 4.6s of a suite that already straddles its ceiling
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M32-3
  - 'PR #34 R1 (the fix'
  - 'not the finding); cost model corrected per PR #34 R11.'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
an act failure is only expensive when it is a POSTCONDITION failure. Those run `check_state`'s whole settle loop (10 x 200ms) before returning False, so they cost a full `SETTLE_BUDGET_MS` each: `observe-cannot-launder-noop-action` 2.29s, `observe-drilldown-cannot-launder-noop-action` 2.35s, and the three that predate this PR (`recovery-replan-postcondition` 2.33s, `recovery-label-requires-strategy-change` 2.32s, `replan-cannot-launder-noop-action` 2.29s). An act failure raised INSIDE `execute` never reaches `check_state` at all and is free — a fill readback mismatch is instant, a click timeout is 10s for a different reason. The first version of this block claimed the settle loop was the price of every act failure; that was wrong, and `observe-drilldown-cannot-launder-unchecked-action` now uses the cheap shape (~0.15s, a fill past the search box's `maxlength`). The two 2.3s cases keep the postcondition shape because it is the only one that produces `page_changed: false` — the cheap shape produces `null`, and PR #34 R8 is precisely what happens when those two values are not both pinned.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either a cheaper way for a case to declare "this postcondition will not hold" (a per-case settle bound is the obvious one, and it must not weaken the production budget), or an explicit ruling that act-failure coverage is worth its share of the ceiling — recorded wherever the open wall-clock decision lands (PR #29 R21). Do NOT fix it by shortening SETTLE_TRIES: that is a production budget with `nav-load-event-never-fires` behind it.
<!-- AC:END -->
