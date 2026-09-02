---
id: DRAFT-8
title: the malformed-coordinate ruling is pinned by no case
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D3
  - 'PR #70 R5 (LOW'
  - routed debt).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
specs/001-browser-contract.md's `click_at` bullet rules that "Malformed coordinates are `failure:task`". The two refusal cases this milestone ships (`click-at-without-a-screenshot-is-refused`, `loop-click-at-from-a-drill-observation-is-refused`) both pin the ARMING gate and both carry well-formed `"x,y"` values, so nothing in the suite sends a `click_at` whose `value` cannot be parsed. A probe confirms the executor does refuse one, with the note ``click_at needs `value` as "x,y" viewport CSS pixels; got ...`` raised as `StepError("task", ...)`; the ruling is therefore true and ungraded, which is the state this repo treats as one bad refactor from false.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an adversarial case sending `click_at` with an unparseable `value` from a properly armed observation, expecting `failure:task` and the refusal note, watched red with the parse guard removed.
<!-- AC:END -->
