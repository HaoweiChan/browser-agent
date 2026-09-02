---
id: DRAFT-86
title: >-
  the band ledger is filtered to the exact current case count, so a fresh band
  is a short sample
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R50
  - T-R34
  - >-
    restated after PR #35 R4 (renumbered from T-R39 during the M35 merge — main
    had allocated that id independently)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_band_wrong` filters `history.jsonl` to rows whose `total` equals the CURRENT case count, so adding one 0.0s pure-code case discards every earlier run. Observed: `invariant`'s runs at 51 cases reached 14.12s; the first two runs at 52 cases maxed at 12.78s, which derives **15** — the ceiling CI has been red against twice. PR #35 R4 correctly refused this as debt while ADR-019 §6 still claimed "no ceiling is ever justified by a maximum smaller than the truth"; that claim is gone, the residue is declared in §6 (a freshly republished band is a LOWER bound and a ceiling does not ratchet down on one), and the concrete failure — a derivation arguing 15 under a heading that says 20s — is now graded by `published-band-matches-the-ledger`. What remains here is only the option §6 names and does not take: widening the window (rows at nearby counts, or a floor at the previously published maximum) so a band re-measures from more than the two runs that happen to follow a case being added.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a widened window with the reasoning recorded, watched red against the 52-case sample above — or an ADR line closing the option deliberately.
<!-- AC:END -->
