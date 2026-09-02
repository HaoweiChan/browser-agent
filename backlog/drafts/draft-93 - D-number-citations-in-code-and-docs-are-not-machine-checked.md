---
id: DRAFT-93
title: D-number citations in code and docs are not machine-checked
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R32
  - 'PR #25 R5'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`support-matrix-cites-real-cases` resolves backticked case-id tokens against `evals/`, but not bare `D21`/`D22`-style numeric references against the `docs/support-matrix.md` table. `src/browser/agent.py:64`, `docs/analysis.md` §8a-2 and `src/browser/verifier.py` now all cite D-numbers, so a future renumbering or row deletion leaves those citations dangling with nothing red. This is PR #25 R1's defect in its general form — R1 was one uncited claim; this is the mechanism that lets the next one through.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a case resolves bare D-number citations against the support-matrix table and is watched red against a deliberately broken D-number first.
<!-- AC:END -->
