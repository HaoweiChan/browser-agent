---
id: DRAFT-36
title: the suite-move justification carries two false clauses
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D13
  - 'PR #60 R22 (LOW'
  - routed to debt — logged
  - >-
    deliberately not edited). The load-bearing half of that disclosure was
    judged honest: the three 230-case rows (90.65
  - '91.06'
  - >-
    91.76) ARE in the committed ledger and ADR-019 §2 names them accurately. The
    justifying sentence is where it goes wrong. Evidence
  - >-
    verbatim: `ADR-019:102` says `fast` "is byte-for-byte the 229-case tree
    those five rows measured". HEAD's `history.jsonl` holds EIGHT local `fast`
    rows at `total=229` — 90.02
  - '91.04'
  - '90.76'
  - '90.99'
  - '90.38'
  - '90.73'
  - '91.03'
  - >-
    90.72 — five from 0826 and three recorded after round 3. And the tree is not
    byte-for-byte: `resolver.py`
  - '`server.py` and `eval_adapter.py` all changed since those rows'
  - >-
    which §2 itself says ten lines earlier when it records round 3 changing
    `LATE_OPTIONS_DELAY_S` and the select budget. §2 also says
  - fourteen lines later
  - >-
    that how many rows sit at a count "are deliberately not written here" — so
    the sentence breaks that rule in the act of breaking two others.
    `tasks/TODO.md` carries the same pair
  - >-
    and this file already records a PRIOR finding about four sentences claiming
    byte-for-byte behaviour while it was false.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
rewrite `ADR-019:102` and its TODO twin to that form, and retire "byte-for-byte" from this repo's vocabulary for anything but a literal file comparison.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 no document claims a tree is unchanged when `git diff` says otherwise, and no band prose states a row count §2 says it does not state.
<!-- AC:END -->
