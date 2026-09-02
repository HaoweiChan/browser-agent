---
id: DRAFT-28
title: the observe→resolve round trip is pinned on one page and one role
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D1
  - T-M42-20
  - >-
    while writing case (a). The defect it caught — two different accessible-name
    engines disagreeing — was invisible to 213 green cases for a whole milestone
    because every case grades ONE end: `observe` cases assert what the
    observation says
  - resolver cases resolve targets an author typed by hand
  - >-
    and nothing ever handed the observation's own output back to the resolver.
    `resolve_advertised` (new `observe`-case key) closes that loop
  - >-
    but it is declared on exactly one fixture (`sec10k-inspector.html`) for
    exactly one role (`combobox`)
  - >-
    so the same class of disagreement on any other page or role is still
    uncovered. Two known widenings and one known hazard
  - >-
    none taken here: `text-transform: capitalize`/`lowercase` are the same
    defect with different casing; `::before`/`::after` content is also folded
    into Chromium's snapshot name and NOT into the locator engine's
  - >-
    which the case-fold fix does not touch at all; and turning the key on across
    every existing `observe` case would be a gate-wide claim ("no observation
    anywhere advertises an unusable name") that should be watched red before it
    is asserted
  - not switched on and assumed.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
widen deliberately, one page/role at a time, each with its own red-first run — or, if the sweep comes back clean, promote it to a property over the fixture set with the cost measured against the `fast` band first.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 at least the `::before` content case pinned red, and a stated ruling on whether the round trip is per-case or a suite-wide property.
<!-- AC:END -->
