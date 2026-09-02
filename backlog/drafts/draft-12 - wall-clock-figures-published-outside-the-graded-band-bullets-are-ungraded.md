---
id: DRAFT-12
title: wall-clock figures published outside the graded band bullets are ungraded
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D7
  - 'PR #70 R13 (the residual class'
  - recorded rather than swept).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`published-band-matches-the-ledger` reads the Band-source bullet and nothing else, so a wall-clock figure quoted anywhere ELSE in the same documents — a narrative paragraph, an ablation aside, a README sentence, an ADR's consequences section — is published prose that no grader reads back against `evals/report/history.jsonl`. It can contradict the ledger committed beside it and stay green forever. R13 is the demonstrated instance, not a hypothetical: the R8 sweep re-typed the one stale number it was hunting and left three neighbouring clauses IN THE SAME PARAGRAPH contradicting the committed ledger — a published band that drops rows, PR #29 R21's class, found only because a reviewer happened to read that paragraph rather than because anything failed.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a grep for wall-clock figures (`\d+\.\d+s`, and bare seconds in band prose) across ADR-019, ADR-035, README.md and docs/analysis.md, with EVERY hit dispositioned — **(a) brought under a grader that reads the ledger, which is the PREFERRED disposition and the one to attempt first**, or (b) explicitly declared narrative — a figure whose job is to describe history rather than to state the tree's current band — **as the FALLBACK, for hits where grading is genuinely impossible rather than merely inconvenient.** An ungraded figure that reads as current is the defect either way. The ordering is not a preference, and PR #72 is why it changed: a disclosure paragraph on that branch reflowed so that `85.` began a line, markdown read it as list item 85, and `published-band-matches-the-ledger` reddened on ADR-019 §6's numbering rule. **Declared prose still drifts; it just drifts silently** — that drift had no author, no diff a reviewer would question, and no plausible path to being caught by reading, because the defect was a line wrap. It was caught by the gate. So (b) buys less than it appears to: declaring a figure narrative fixes how it READS today and does nothing about what edits it tomorrow, while (a) is the only disposition that survives a reflow, a rebase or a copy-paste. Prefer grading wherever the figure can be read back against `evals/report/history.jsonl` at all; reserve (b) for prose whose figure has no ledger row to be graded against.
<!-- AC:END -->
