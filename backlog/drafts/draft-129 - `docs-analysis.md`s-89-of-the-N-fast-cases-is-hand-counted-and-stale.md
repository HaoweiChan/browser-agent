---
id: DRAFT-129
title: '`docs/analysis.md`''s "89 of the N fast cases" is hand-counted and stale'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R87
  - 'PR #45'
  - found while merging `origin/main` (f813af5) into task/T-M40-1
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`docs/analysis.md` publishes "**89 of the 153** `fast` cases drive a real Chromium end to end". Both halves are hand-maintained and nothing recomputes either: `docs-numbers-are-derived` grades the three README count strings and the analysis "N distinct cases" string, not this one. The denominator was already wrong on `origin/main` before this merge — main's README said 155 `fast` while this line said 153 — and the merge takes the suite to 156, so it is now wrong by three. NOT fixed here on purpose: correcting 153 -> 156 without recomputing 89 publishes a second unverified number beside the first, and 89 is exactly the kind of tally that needs deriving, not retyping. Pre-existing drift on main, so it is logged rather than swept (CLAUDE.md debt rule).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the sentence derives both numbers, the way the counts beside it already do — the denominator from `evals.run.load_cases('fast')` and the numerator from a predicate over the case files (a `fast` case whose adapter path launches Chromium) — added to `docs-numbers-are-derived` and watched red against the current text.
<!-- AC:END -->
