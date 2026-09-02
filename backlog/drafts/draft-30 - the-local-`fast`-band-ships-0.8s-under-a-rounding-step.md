---
id: DRAFT-30
title: the local `fast` band ships 0.8s under a rounding step
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D3
  - T-M42-20
  - >-
    republishing ADR-019 §2 at 222 cases. The three runs recorded at this count
    measured 89.60 / 90.08 / 90.49s. `_band_rule` gives 105 for anything up to
    91.30s and 110 above it
  - >-
    so the ledger's maximum is 0.81s from the step that would make item 4
    (committed-ceiling) demand a ceiling this repo has not committed — and
    moving `WALL_BUDGET_S["fast"]` is an ADR
  - not an edit
  - >-
    so the first ordinary run that lands at 91.4s blocks a commit until someone
    writes one. This is not a T-M42-20 defect; it is the state the band was
    already in (the 220-case band sat at 88.81s
  - 2.5s of room) and two cases used a third of what was left.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decide before it bites — either take the ~2.3s of measured waste the next profile finds (ADR-021's own ruling that the answer to per-case growth is removing waste rather than another raise) or pre-commit a ceiling with an ADR that says which. `T-M42-19` (the CI half of the sweep) is adjacent and separate.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either a `fast` band whose maximum sits at least one full step under its ceiling, or an ADR that rules the current margin acceptable and says why.
<!-- AC:END -->
