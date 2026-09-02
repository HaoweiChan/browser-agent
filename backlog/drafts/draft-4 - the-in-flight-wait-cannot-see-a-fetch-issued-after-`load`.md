---
id: DRAFT-4
title: the in-flight wait cannot see a fetch issued after `load`
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-A39-1
  - ADR-039 §2
  - '2026-08-28'
  - declared by the ruling rather than found after it.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`navigate`'s settle asks one question — were any requests in flight when `load` fired? — and a page whose script schedules its `fetch` from a `setTimeout` (or an `IntersectionObserver`, or a `requestIdleCallback`) after `load` answers "no" truthfully and is read early exactly as it was before ADR-039. The fix for THAT shape is a quiescence window, which is the mechanism ADR-039 rejected on measured cost, so this is a deliberate ceiling and not an oversight. No fixture in this repo has the shape: `late-options.html` issues its fetch from an inline script during parse, which is precisely why it is in flight at `load` and why the accepted mechanism catches it.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a fixture whose control is painted from a post-`load` timer, and an adversarial case over it watched RED first per CLAUDE.md rule 2 — the case must be red against ADR-039's mechanism, which is the whole point of writing it. Only then is the quiescence-window question re-opened, and only with the fast-suite wall clock measured before and after, because that is the number that decided ADR-039 §1.
<!-- AC:END -->
