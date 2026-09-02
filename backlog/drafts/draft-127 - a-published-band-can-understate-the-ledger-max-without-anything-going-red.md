---
id: DRAFT-127
title: a published band can understate the ledger max without anything going red
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R85
  - 'PR #45 R2 (the class behind the finding'
  - not the finding — the prose is repaired in that PR)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_band_wrong` item 3 (same-ceiling) is `rule(published) == rule(ledger max)`, so a band published from any row whose derived ceiling matches the maximum's is green. That is deliberate — ADR-019 §6 "What it lets through" declares the slack and `published-band-slack-is-declared` bounds it at one ceiling step — but it means §6's own residue rule ("republish the maximum") is unenforced, and PR #45 R2 is what that costs: §3 published 14.08s where the ledger held 14.16s at the same count and asserted the count held a single row, and both halves had to be caught by a human reading the file. The strict form — published == ledger max — is REFUSED, and the reason is in §6: a later, slower row at the same count would retroactively redden an already-published band, which is exactly the treadmill the as-of-the-cited-run rule exists to prevent. **No graded form is currently known, and one candidate is already dead.** This block first proposed `published >= max(wall_s of rows at this count with ts <= the cited ts)` and claimed it would have caught PR #45 R2. It would not (PR #45 R5). The arithmetic, against the ledger at `32cb549`, rows at invariant/59 being 002326 14.02, 002424 14.08, 002824 13.17, 003025 14.16, 003411 13.18, 081958 13.2: cited 20260824-002424, published 14.08 -> as-of max 14.08 -> 14.08 >= 14.08 -> GREEN cited 20260824-003025, published 14.16 -> as-of max 14.16 -> 14.16 >= 14.16 -> GREEN It passes the defect and the repair alike, and it does so structurally, not by luck: the R2 defect was citing 002424 while the slower 003025 stood at a LATER ts, which an as-of-the-cited-ts bound cannot see by construction. An author satisfies it by citing an early row, which is precisely what happened. Do not re-propose it.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a form that is demonstrably **red on `002424`/14.08 and green on `003025`/14.16 against the committed ledger**, with the arithmetic run and shown before it is published anywhere — the candidate above is what happens otherwise. As-of the band's own publication (rather than as-of the cited row's ts) is the obvious next candidate and is unchecked; note that it needs a publication instant the grader can derive, and the ledger alone does not carry one. Whatever the form, it is watched red against a synthetic ledger (`_band_wrong` is already callable over values for exactly this reason), and only then does §6 gain an item and "What it lets through" narrow. Until then ADR-019 §3 says plainly that no graded form exists, and that sentence is the honest state of this class.
<!-- AC:END -->
