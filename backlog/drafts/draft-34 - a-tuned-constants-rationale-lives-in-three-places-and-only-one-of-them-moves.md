---
id: DRAFT-34
title: a tuned constant's rationale lives in three places and only one of them moves
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D11
  - 'PR #60 R18 (LOW'
  - routed to debt). Evidence
  - >-
    verbatim: `server.py` `LATE_OPTIONS_DELAY_S = 0.3`;
    `action-select-option-waits-for-fetch-painted-options.json` "still says 0.5s
    and '~5x margin' (this file is not in `git diff fb84a88..HEAD`)";
    `browser-domain/SKILL.md` "still says 1.0s
  - two rounds stale". The margin is now 3x
  - >-
    not 5x and not 10x. Round 3 repaired the SKILL.md half in passing (it was
    one clause in a sentence that had to move anyway) and left the case
    provenance
  - so the drift is halved and not closed. Also from the same finding
  - >-
    and worth keeping because it is the reassuring half: the case is NOT
    weakened by the tuning. Ablating the wait (timeout -> 1ms) turns it red 3/3;
    unablated it runs 452/453/453ms; and
    `action-select-option-never-filled-fails-loud` runs 1144-1161ms against
    `max_ms` 2500 while still emitting the loud `StepError`.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the scalar has one home (`server.py`) and every other mention should cite it rather than restate it, the way the band bullets cite the ledger. That is the standing rule this repo keeps re-learning; a derived margin ("~3x the measured first read") is a second scalar with the same problem and should be a relation, not a number.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 no document outside `server.py` states the delay as a number, or a check reads the restatements back against the constant.
<!-- AC:END -->
