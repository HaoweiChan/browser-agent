---
id: DRAFT-133
title: >-
  a block's `[status: pr]` outlives its PR, so TODO.md asserts what `gh pr view`
  denies
status: Draft
assignee: []
created_date: '2026-09-02 17:49'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D10
  - 'PR #77'
  - 2026-08-28 — noticed while closing the fourth instance.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
a block is moved to `[status: pr]` when its PR opens and nothing moves it afterwards, so once that PR merges the block asserts a state the forge contradicts. Four instances in one evening, each needing its own follow-up PR to correct: M44-P1 twice (PRs #65 and #67), M43 once (corrected by #73), and M45-D6 (corrected by this PR). The falsehood is mechanically detectable — the block names its status, `gh pr view` names the PR's — which is what makes it debt rather than a habit to be more careful about. One clause of context and no more: this is the same thesis as T-M39-15's D2/D3 and M43-D4, that the machinery verifies trees well and verifies everything around trees poorly — here the tree is internally consistent while the claim it makes about the forge is false.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the check belongs at the pr-loop SPEC layer, NOT the eval layer — it needs the network, and the `invariant` suite is loopback-only by design, so a case here could not run it. Like T-M39-15's D2 and D3, the fix therefore lives in the groundwork plugin rather than in this repo, and closing this block means either that plugin change landing upstream or a recorded decision that status fields are corrected by hand at merge time.
<!-- AC:END -->
