---
id: DRAFT-39
title: >-
  the front-page baseline cites a run that failed, and the rule set makes it
  unfixable in place
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-14
  - 'found on merged `main` (`7e0b662`) by the session that had driven PR #52'
  - immediately after M39 merged. Reproduced and diagnosed here; NOT fixed
  - because fixing it needs a decision
  - not an edit.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
README's "Where it stands" block publishes `fast  180/181    invariant  65/66` as the latest offline baseline, citing `evals/report/20260824-052304-fast.json` (score 0.994) and `20260824-052134-invariant.json` (score 0.985). Both are RED runs — the failing case in each is `docs-numbers-are-derived` itself. ADR-019's band bullets have the same shape: the `fast` band cites ts `20260824-051337` at `179/181` and the `invariant` band cites `20260824-051159` at `64/66`. So the repo's front page and its ceiling ADR both advertise numbers taken from failing runs, while the tree itself passes 181/181 and 66/66.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the front-page block and both ADR-019 band bullets cite runs that PASSED, with the sequencing that makes that reachable written down (commit first so the tree is clean, then `--report`, then cite) — or an ADR amending whichever of the three rules deadlocks, saying which and why. Plus a case that reddens when a cited baseline report has any failure other than the excluded self-reference, so this class stops being invisible.
<!-- AC:END -->
