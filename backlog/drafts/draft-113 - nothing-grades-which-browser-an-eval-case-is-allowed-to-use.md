---
id: DRAFT-113
title: nothing grades which browser an eval case is allowed to use
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R24
  - 'PR #23 R7 (LOW'
  - routed debt by the reviewer)
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
nothing grades which browser an eval case is allowed to use

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a case grades the invariant suite's purity so the retag cannot silently reverse. The R3 resolution's `green` text was narrowed in the R4 repair, which is the honesty half; this block is the graded half. Same family, same gap, found in the same round: ADR-013 Decision 1 says the suite shares one Chromium, and `ui-rendered-narrow` owned its own for a whole review round with nothing red (PR #23 R5). `agent-launches-its-own-browser` did NOT miss it — that case grades `run_task(browser=None)`, the production launch branch, and `ui-rendered-narrow` never routes through `run_task`. Do not widen that case: what is missing is a check on the eval harness's own renderers, not on the agent.
<!-- AC:END -->
