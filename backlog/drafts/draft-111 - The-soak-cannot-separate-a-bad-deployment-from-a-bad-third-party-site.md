---
id: DRAFT-111
title: The soak cannot separate a bad deployment from a bad third-party site
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md M27
  - >-
    PR #21 R1 (logged there as M18; renumbered on the PR #23 merge — both
    branches allocated M18 by "next free"
  - the T-ADR-NUM failure mode applied to task ids)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`summarize` now borrows `ablation.is_measurement` to decide what a completion is, so a live task ending `failure:nav` because the site itself was down drops `demo_ready` to false and reads as if the deployment failed. That is the safe direction to be wrong in and it is why it shipped, but it is still a conflation: "we could not measure this run" and "this deployment could not complete it" are different verdicts. Acceptance: a case injects a terminal `failure:nav` on the live task and pins that the report distinguishes it from a deployment fault without ever letting it count as a clean completion.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
