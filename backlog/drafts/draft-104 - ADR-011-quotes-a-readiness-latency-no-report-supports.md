---
id: DRAFT-104
title: ADR-011 quotes a readiness latency no report supports
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M19
  - 'PR #21 R8'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-011 Decision 4 says "Measured in the case: 5 ms, mid-run". The eight committed reports carrying `readyz-tracks-the-run-slot` record `during_latency_s` of 0.001-0.007 and never 0.005. The substance holds (all <=7ms); the figure is unsourced.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the ADR quotes a value that appears in a named committed report, or states it as a range.
<!-- AC:END -->
