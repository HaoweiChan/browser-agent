---
id: DRAFT-98
title: '`--update-baseline` records a baseline over the wall-clock ceiling, silently'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R12
  - 'PR #20 R12 (LOW'
  - routed debt — what should happen there is a repo-owner call)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`evals/run.py:157-161` writes the baseline and `return 0` at line 161; the `over_budget` check is at line 166. A `fast` run measuring 79.02s therefore exits 0 with only `[eval] baseline['fast'] = 1.000 (recorded)` on stdout and no `OVER BUDGET` line anywhere, even though the same run without the flag exits 1. So the one command CLAUDE.md sanctions for a deliberate baseline move records it on a tree that is over the ceiling and says nothing. ADR-013 Decision 2 describes the ceiling as "the same shape as the invariant-100% rule beside it" — which sits at line 162 and is bypassed by the same early return, so the shape does match, but the resulting silence is undocumented. Repro: the 0.25s-per-case injection used for R8, run with `--suite fast --update-baseline --baseline /tmp/b.json` → exit 0, no OVER BUDGET line; drop `--update-baseline` → `OVER BUDGET: suite 'fast' wall clock 79.02s > 60s`, exit 1. Acceptance: either the over-budget line is printed (as a warning) on the `--update-baseline` path too, or ADR-013 Decision 2 names `--update-baseline` as a path where the ceiling is not reported.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
