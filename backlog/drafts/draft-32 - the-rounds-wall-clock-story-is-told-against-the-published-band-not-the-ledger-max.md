---
id: DRAFT-32
title: >-
  the round's wall-clock story is told against the published band, not the
  ledger max
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D9
  - 'PR #60 R13 (LOW'
  - routed to debt). Two stale claims
  - one class. Evidence
  - verbatim. (1) `T-M42-20-D8`
  - added in the round-1 commit
  - >-
    says in the present tense that "`published-band-slack-is-declared`
    independently reports `headroom_s {fast: 1.05}`". Running that case on the
    round-2 tree gives `{'declared_slack_s': 4.35
  - '''headroom_s'': {''fast'': 1.86'
  - >-
    'invariant': 1.02}}` — the scalar is not one the grader produces any more.
    (2) Headroom there is measured against the PUBLISHED band
  - >-
    not the ledger's maximum. At 227 cases the committed ledger held four `fast`
    rows — 89.32
  - '89.44'
  - '90.46'
  - >-
    90.66 — so the real margin to the next rounding step is `91.30 - 90.66 =
    0.64s`
  - TIGHTER than the 0.81s `T-M42-20-D3` raised the debt for
  - >-
    while the round-1 entry summarises the round as "grew by six and got
    FASTER". Both statements were true of the numbers they cited and neither
    cited the number that binds. (3) It also inverts the stated reason for
    tagging the new 2s case `invariant`: the grader reports `invariant` headroom
    1.02s against `fast`'s 1.86s after the move
  - >-
    so the suite the case was moved INTO now has less published headroom than
    the one it was moved out of — the ledger-max picture still favours the move
  - which is why this is LOW
  - and ADR-019 §3 discloses the 13.76 -> 16.37 jump.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pick ONE number as the one the wall-clock story is told against — the ledger maximum, not the published band, since that is what item 3 (same-ceiling) actually grades — and state it wherever the story is told (D3, D8, ADR-019 §2).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 no debt block quotes a headroom scalar, and the margin figure that appears in D3/D8/ADR-019 §2 is derived from the same maximum `published-band-matches-the-ledger` item 3 uses.
<!-- AC:END -->
