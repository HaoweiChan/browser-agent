---
id: DRAFT-16
title: >-
  the PostToolUse invariant hook runs in `CLAUDE_PROJECT_DIR`, not in the
  worktree that was edited
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-13-D1
  - T-M39-13's own implementation session
  - '2026-08-28'
  - on worktree `.claude/worktrees/agent-ace9a347e9c59894c`.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`.claude/hooks/post-edit-invariant.sh` matches on `*/src/*` and then does `cd "$CLAUDE_PROJECT_DIR"` before running `--suite invariant`. In a worktree session that directory is a DIFFERENT tree, so every edit under `src/` in the worktree graded some other checkout: throughout this task the hook reported `invariant: 82/83` — a case count this branch had not had since the first commit — while the worktree itself was at 84/84. Two costs, and the second is the one that matters. The feedback is noise an implementer has to learn to ignore, which is how a real red gets ignored too; and the hook APPENDS a history row to the other tree's `evals/report/history.jsonl` on every edit, so a worktree session silently writes rows into a ledger it is not working in — rows nobody in that session will restore away, at whatever case count that tree happens to be at. That is the T-M38-5 stray-row problem arriving from outside the session entirely, and no `--no-history` opt-out reaches it. This is a CORRECTNESS dependency of ADR-019 §8, not tidiness, and PR #68 R6 (2026-08-28) is why. `stamp()` has one-second resolution, so two rows appended within the same second share a `ts`; item 2 (cited-run) resolves a citation by `ts`, and on a duplicate it used to take the first match, which made the citable maximum unreachable and reassembled the deadlock §8 exists to remove. The lookup was repaired in that round, but the row-manufacturing half is THIS block: a hook that appends to a shared checkout on every `src/` edit, while several worktree sessions edit concurrently, is the mechanism that produces same-second rows in one ledger. Whoever picks this up is not tidying a log, they are closing the input to a deadlock.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the hook resolves the tree from the edited file's path (its own `$file` is already absolute) rather than from `CLAUDE_PROJECT_DIR`, or refuses to run when the two disagree — with a case pinning whichever rule is chosen.
<!-- AC:END -->
