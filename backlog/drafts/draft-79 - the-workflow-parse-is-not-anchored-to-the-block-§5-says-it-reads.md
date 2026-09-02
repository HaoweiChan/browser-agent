---
id: DRAFT-79
title: the workflow parse is not anchored to the block §5 says it reads
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R79
  - 'PR #41 R18'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/eval_adapter.py`:1114-1117 matches `^\s*#\s+(invariant|fast) ...` over the whole of `.github/workflows/eval.yml`, while ADR-019 §5:242-243 says the comparison is against the copy in that file's **comment block**. Moving the two measurement lines out of the env comment block to the end of the file leaves the check green. Same shape as the §5-scoping defect PR #41 R12 closed for the run id (`five = adr[adr.index("### 5."):]`); the workflow side got no equivalent scope. No wrong value escapes — only the stated location does.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the parse is scoped to the comment region preceding the `EVAL_WALL_BUDGET_S_*` env block, watched red by relocating the copy, or §5 says "a comment in `.github/workflows/eval.yml`" rather than "comment block".
<!-- AC:END -->
