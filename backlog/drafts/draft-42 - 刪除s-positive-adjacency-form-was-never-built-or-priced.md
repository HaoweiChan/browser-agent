---
id: DRAFT-42
title: 刪除's positive-adjacency form was never built or priced
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D4
  - M45 spec-drift audit
  - '2026-08-26'
  - >-
    finding 5. M45's own spec asked for this and M45 shipped something else; the
    departure is recorded but the alternative was never measured
  - which is the part worth closing.
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`tasks/TODO.md` M45 asked that 刪除 get "an adjacent object the way `delete` requires a determiner" — i.e. the POSITIVE-adjacency shape the English clause uses, `\bdelet(?:e|es|ed|ing)\s+(?:my|the|this|these|those|all|every|any|our)\b` (`src/browser/agent.py`). M45 tried the NEGATIVE form instead, `[刪删]除(?!的)`, cold review broke it on three genuine destructive asks, and the screen was left fail-closed with no condition at all. Every document then recorded the conclusion as "no regex separates those" — which is true of the negative form that was tried and NOT established for the positive one, which was never written. A Chinese quantifier/possessive list (所有, 全部, 我的, 這些, 那些, 每一, 任何, 我們的, 帳號, …) adjacent to 刪除 is the direct mirror, and the two existing true-positive cases suggest it is not obviously hopeless — 刪除所有郵件 has 所有 immediately after the verb, though 刪除購物車裡的所有商品 does not, which is exactly the measurement this block is for.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the positive-adjacency form is written and measured against the full row set of `screening-zh-term-inside-another-word` plus `l5-refuse-destructive-zh`; either it beats bare 刪除 on the false-positive rows without losing a true positive — in which case it ships, red-first, and D31's 刪除 residuals shrink — or it does not, in which case the "no regex separates those" sentence in `src/browser/agent.py`, the case provenance and `docs/support-matrix.md` D31 is upgraded from an assertion to a measured claim citing this block. Either outcome closes it. Gate green.
<!-- AC:END -->
