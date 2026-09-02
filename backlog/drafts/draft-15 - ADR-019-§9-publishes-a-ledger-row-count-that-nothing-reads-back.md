---
id: DRAFT-15
title: ADR-019 §9 publishes a ledger row count that nothing reads back
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-13-D2
  - 'PR #68 R19'
  - 2026-08-28. INHERITED FROM `origin/main`
  - >-
    not from this branch's diff — §9 is PR #72's section and the sentence
    arrived with it.
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
§9 states "The committed ledger holds 2162 rows, every one of them `local` or untagged and not one tagged `ci`". The count was true when written and is not now — `history.jsonl` grows by a row on every gate run, so the figure is stale within the hour and stale by ~150 rows already. The CLAIM the sentence exists to make is the `ci`-free one, which is stable and worth keeping; the row count is decoration that ages. Same class as item 12 (ledger-max)'s marker: a scalar of a growing file, stated in prose, read back by nothing.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the count is dropped and the `ci`-free claim kept on its own (preferred — it is the load-bearing half and it is checkable by grep), or it is graded against `history.jsonl` the way item 12 (ledger-max) grades a maximum, or it is marked as a dated snapshot in the §5 style so a reader knows not to trust it as current. NOT fixed in PR #68: it is not this branch's diff, and editing another PR's section during a breaker round is how the stale-sentence crop keeps growing.
<!-- AC:END -->
