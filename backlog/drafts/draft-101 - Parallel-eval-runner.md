---
id: DRAFT-101
title: Parallel eval runner
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M14
  - backlog (pre-pr-loop
  - never promoted)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
promote only with its own eval evidence. M12 resolved without amending ADR-002 D4 — it removed 11.3s of per-case browser launch and left the 42.2s of deliberate waiting (settle loops, bounded load/screenshot waits, one 10s click timeout) that only parallelism can hide. `fast` now typically sits under 59.5s against a local 60s ceiling with only a thin, inconsistent margin (a straddling band briefly pushed the ceiling to 70s, round-5 review could not reproduce it and withdrew it, then post-commit verification found the suite clears 60 in 20 of 21 further real runs, not all of them — ADR-013 Decision 4), so this lever is close to urgent: the next case `fast` gains, even a cheap one, is likely to turn the ceiling red on top of the residual noise already there.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
