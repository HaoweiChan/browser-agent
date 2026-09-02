---
id: DRAFT-6
title: '`trace_values` does not discriminate on its own'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D1
  - M43 implementation
  - the red-first reconstruction (docs/evals/m43-red-first-ledger.md).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`loop-click-at-resolves-and-records-coordinates` asserts four conjuncts, and `trace_values` — the one that grades "the coordinates were RECORDED" — was GREEN against the tree with no `click_at` at all. The coordinate string rides in the trace's existing `value` field (ADR-035 Decision 4, deliberately: no schema change), and a refused step records `value` the same way an executed one does, so the conjunct cannot tell the two apart. The case as a whole is carried by `status` / `verdict` / `trace_postconditions`, which are red without the implementation, so nothing is unguarded today — the conjunct is weaker than it reads, not absent.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the conjunct asserts the value on a step that cannot exist without `click_at` (so it is red on the same ablation the other three are), or `opt-in-expect-keys-declared`'s entry for `trace_values` states in words that it grades recording and never acting, and the case's provenance stops implying otherwise. Watched red on the ablation above before it is called fixed.
<!-- AC:END -->
