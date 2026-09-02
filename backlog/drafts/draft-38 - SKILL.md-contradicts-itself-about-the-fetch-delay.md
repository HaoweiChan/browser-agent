---
id: DRAFT-38
title: SKILL.md contradicts itself about the fetch delay
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D15
  - 'PR #60 R24 (LOW'
  - routed to debt). Evidence
  - >-
    verbatim: `browser-domain/SKILL.md` says "an endpoint that sleeps
    `server.LATE_OPTIONS_DELAY_S` (1.0s)" seven lines above the clause round 3
    corrected to "(0.3s since PR #60's rounds put twelve more cases in the same
    suite...)"
  - >-
    while `server.py` has `LATE_OPTIONS_DELAY_S = 0.3`. The file contradicts
    itself and the constant. It also falsifies `T-M42-20-D11`'s own status line
  - >-
    which asserts "Round 3 repaired the SKILL.md half in passing ... so the
    drift is halved and not closed": the SKILL.md half is NOT repaired
  - only one of its two mentions is
  - >-
    so D11 understates the drift the next round inherits. Recorded here rather
    than edited into D11 because the routing said log.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
D11's fix closes this one too — the scalar has ONE home (`server.py`) and every other mention cites it rather than restating it. Doing it by hand a third time is how there came to be two mentions in one file disagreeing.

Depends (TODO.md ids): T-M42-20-D11

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `grep -rn LATE_OPTIONS_DELAY_S` shows exactly one number, in `server.py`.
<!-- AC:END -->
