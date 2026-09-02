---
id: DRAFT-67
title: >-
  a published band makes every open PR re-derive its numbers whenever any PR
  changes the case count
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-11
  - >-
    observed twice in one delivery while merging `origin/main` into `task/M39`
    (PR #44). Recorded as cost
  - >-
    not as a proposal — the fix is a design decision and this block deliberately
    does not make it.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-019 §2/§3 publish a band as authored prose — a case COUNT, a ledger `ts`, a wall clock and a `passed/total` — and `published-band-matches-the-ledger` grades all four against the committed ledger, item 1 (count) first. So the band is only valid at the exact case count it was written for. Any PR that changes the count invalidates the published band of every OTHER open PR the moment it merges, and each of those must then re-run both suites, re-read the ledger, re-derive two bands, and republish the same numbers in `ADR-019` (two band lines, two derivation sentences), `README.md` (the band table plus the status block), `docs/analysis.md` (the coverage split and section 1) and `docs-numbers-are-derived.json` (both report citations). What it cost here, measured rather than estimated: - Pass 1, merging PR #41 (T-R44/T-R51) and PR #43 (M40): `fast` 156 -> 161, `invariant` 59 -> 62. Full re-derivation, then THREE commits — the merge itself, plus two more to re-cite clean rows, because a clean row cannot exist at a new count until the commit that creates the count has landed (T-M32-13's two-commit price, paid once per band). - Pass 2, merging PR #45 (T-M40-1), one task and one case: `fast` 161 -> 162, `invariant` 62 -> 63. The same full re-derivation again, for a single case. - Pass 3, merging PR #46 (T-M40-2), two cases: `fast` 162 -> 164, `invariant` 63 -> 65. Full re-derivation a third time. The third instance is the one that shows the shape rather than the size, and it is why this block says "quadratic" rather than "repeated": **PR #46 and this branch each re-derived the SAME two bands, independently, against the SAME committed ledger, for the same reason** — #46's own history carries `Merge origin/main … and re-derive every number`, and this branch carries three of them. Neither re-derivation could reuse the other's work, because each is authored prose about a count the other branch does not have yet. That is observed, not predicted: two branches, one ledger, the same arithmetic done twice and thrown away once.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a decision, recorded as an ADR, on whether the published band stays authored-at-a-count or becomes something a count change does not invalidate — the options worth pricing are a band citing something count-independent, and a band computed at merge time rather than authored — including what each costs in the reviewability the current form buys (a human can read the four numbers and check them against the ledger by hand, which is why they are prose today). Whichever way it goes, ADR-019 §6's item 1 (count) is the clause that changes, and the decision must say what happens to the two-commit dance, which is a consequence of the same design and not a separate problem.
<!-- AC:END -->
