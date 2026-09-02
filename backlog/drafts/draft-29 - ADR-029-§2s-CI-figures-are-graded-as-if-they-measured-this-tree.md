---
id: DRAFT-29
title: ADR-029 §2's CI figures are graded as if they measured this tree
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D2
  - T-M42-20
  - >-
    adding two cases. `adr029-scope-matches-the-suites` reads every `` `fast`
    N/N `` and `` `invariant` N/N `` in ADR-029 §2 back against the CURRENT
    suite sizes. Two of those figures belong to CI run `32937020758` on commit
    `14a6a7b`
  - >-
    which measured a 220-case tree and always will; the local pair legitimately
    moves with every case addition. Following the convention (git history:
    213→219→220
  - >-
    all three restated together) would have had this branch publish "on CI
    `fast` 222/222"
  - >-
    a number no run produced — CLAUDE.md rule 4. This branch instead spells the
    CI counts out in words so the grader does not read them as this tree's
  - and says so in the ADR.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decide which of the two the repo wants — either §2 stops restating CI counts at all and defers to ADR-019 §5, the one publisher (`ci-numbers-are-derived` already grades that), or the guard learns to scope a figure to the commit it names. The current state is honest but relies on prose staying in a form the regex ignores, which is a guard by accident.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the CI half of §2 either gone or graded against its own run id, and a case that reddens if a CI figure is restated in the local pair's form.
<!-- AC:END -->
