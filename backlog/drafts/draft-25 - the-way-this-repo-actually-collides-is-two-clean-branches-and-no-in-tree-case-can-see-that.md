---
id: DRAFT-25
title: >-
  the way this repo actually collides is two clean branches, and no in-tree case
  can see that
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-15-D2
  - T-M39-15
  - cross-branch near-miss 2026-08-28 (decision number 034 double-claimed
  - arbitrated to 034/035).
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`task-and-adr-ids-are-unique` closes the in-tree half — duplicate ids inside `tasks/TODO.md`, `tasks/DONE.md`, `specs/decisions/` filenames and INDEX.md rows. It cannot close the half that actually produces the collisions. Minutes after that case went green, `task/M44-P1-derived` and `task/M43` both moved to claim decision number **034**; the orchestrator caught it only by holding the cross-branch view and arbitrated M43 to 035. The property that matters: the collision was undetectable from inside either worktree. 034 lived on an unmerged branch, so it was in neither tree's `specs/decisions/` listing nor either rebased INDEX.md; both trees were internally consistent and both passed every check that reads the working tree. PR #45's seven duplicate ids arrived the same way, each through a separately-clean branch. The only free moment to catch this is allocation time, before either branch has spent a round on the number. **Four instances on 2026-08-28 alone; PR #69's history carries the full set.**

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
