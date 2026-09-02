---
id: DRAFT-83
title: the post-edit invariant hook runs in the wrong worktree
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M32-2
  - M32
  - found while implementing.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`.claude/hooks/post-edit-invariant.sh` cds to `$CLAUDE_PROJECT_DIR` and prefers `.venv/bin/python` there. When the session is working inside a `.claude/worktrees/` sibling, that variable still points at the ORIGINATING worktree, so the hook grades a different checkout than the one being edited, and with a bare `python3` if that checkout has no `.venv` — which reports `ModuleNotFoundError: No module named 'fastapi'` for 14 of 38 invariant cases on every single edit under `src/`. Loud, so nothing was silently wrong, but the feedback it gives is about neither the edit nor the tree.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the hook resolves the tree from the edited file's path (or from `git rev-parse --show-toplevel` on it) rather than from `$CLAUDE_PROJECT_DIR`.
<!-- AC:END -->
