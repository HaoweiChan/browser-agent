---
id: DRAFT-14
title: >-
  a guard credited with a claim it only half checks: the red-report guard covers
  the headline suite only
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-13-D3
  - 'PR #68 R15'
  - 2026-08-28.
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_run_doc_counts_case` recomputes README's "Where it stands" block from the reports `where_it_stands.reports` names, one per suite. The guard that refuses a RED report — `headline_report_is_red`, added by PR #34 R4 — is applied only to `ws["headline"]`, which is `fast`. Every other suite's report is parsed for its `passed/total` and published to README with no check that the run was green, so a red run can be cited as the repo's front-page baseline and the whole gate stays green. Not theoretical: this branch published `invariant  88/91` in that block — a pre-republish red-watch run whose three failures were `adr029-scope-matches-the-suites`, `docs-numbers-are-derived` and `published-band-matches-the-ledger` — while ADR-029 in the same tree said `locally invariant 91/91`. The instance is repaired (the band now cites a green 93/93 run); the CLASS is this block.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the red-report guard applies to every suite the case is tagged with, not just the headline — with the fixed point PR #34 R4 established preserved (this case's OWN row stays excluded, or the guard can never go green again once it has gone red). An adversarial case pins it, watched red on today's tree first: the `88/91` state above is a ready-made red fixture. NOT fixed in PR #68: found in the breaker round, and a guard change plus its case is real work rather than a prose repair.
<!-- AC:END -->
