---
id: DRAFT-73
title: >-
  the SSRF case for `/view` is `fast`-only because the invariant suite cannot
  carry it on CI
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-3
  - 'PR #43 (M40)'
  - CI run 32651052282
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`view-proxy-refuses-private-and-redirects` guards a public SSRF surface and belongs in `invariant` beside `url-guard-literal-ips`, which guards the task path's twin. Tagged that way it is ungreenable on CI: the invariant suite ran **17.58s at 59 cases** on CI against 13.12s locally, and 17.58 derives a ceiling of 25 where the committed one is 20, so item 3 (same-ceiling) reddens every CI run while every local run is green. That is T-M32-13's second symptom, which its own block already records at 17.39s — before this case existed. CI's invariant row was 14.88s at 58 cases (ADR-021), so the gap was already there.

Depends (TODO.md ids): T-M32-13

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either T-M32-13 lands (so a locally-derived band is not structurally red against CI rows) and the tag is restored, or the CI invariant ceiling is re-derived from CI's own measurement under an ADR with an owner ruling — ADR-021's precedent, and its own text says the margin question is not closed. Restoring the tag without one of those puts the branch back to red-on-CI. Merge note (T-R44, 2026-08-24): **the first branch of that acceptance has landed.** Every ledger row now carries an `env` tag and ADR-019 §6 item 9 (environment) filters a band's ledger to its own environment, so a CI `invariant` row cannot enter a `local` band's `ledger_slowest` at all. Replayed at this block's own numbers — a local band of 13.12s at 59 cases beside CI's 17.58s row — `_band_wrong` returns `[{published_slowest: 13.12, derives_ceiling: 20, ledger_slowest: 17.58, ledger_derives: 25}, {ceiling: 20, required_by_adr013_rule: 25}]` untagged and `[]` tagged. Two things this note deliberately does NOT do. It does not restore the tag: that is this block's owner's call, and it needs its own watched-red, not an inference from someone else's merge. And it does not claim CI will now be green — the demonstration above is a constructed ledger on a laptop, and that CI tags its rows `ci` at all is still asserted rather than graded (T-R74). The second branch of the acceptance is therefore still available and may still be the better one.
<!-- AC:END -->
