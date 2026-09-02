---
id: DRAFT-87
title: nothing requires the runs behind a band to be green or clean
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R53
  - T-R34
  - >-
    evidence from PR #35 R5 (renumbered from T-R42 during the M35 merge — main
    had allocated that id independently)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_band_wrong` filters `history.jsonl` on `suite` and `total` alone; `sha`, `dirty` and `passed` are recorded on every row and were read by nothing when this was filed. `dirty` is read now (as-of-the-cited-run cleanliness) and so is `passed` (T-R56: the citation states the row's result); `sha` is still read by nothing, and GREEN is still not required. Round 1 shipped both bands off red, dirty runs: at (invariant, 52) the 13.22s maximum was ts 20260823-023204 with `passed: 50, total: 52, dirty: true` while the other nine runs maxed at 12.88s, and at (fast, 133) the 66.38s maximum was ts 20260823-023406 with `passed: 132, total: 133, dirty: true`. Round 2 republishes both from committed green, clean `--report` runs of the shipped tree (ts 20260823-033320, `fast` 133/133, and ts 20260823-033200, `invariant` 52/52, both `dirty: false`) and `published-band-matches-the-ledger` now requires the published number to BE a clean row at that count. The GREEN half is still ungraded and cannot be graded the same way: this check is in both suites, so at a new case count every run is red until the band is republished, and no green row could ever exist to republish it from. Round 2 also had to fix `evals/run.py` before a clean row was even possible: `dirty` was read AFTER the report file was written, so every `--report` run recorded `dirty: true` on account of its own untracked artifact. Admitting non-green rows is argued in `_band_wrong`'s comment (a wall clock is a wall clock, and requiring green deadlocks: this check is itself in both suites). Admitting DIRTY rows is argued nowhere, and it is the weaker half — a band can be justified by a tree that was never committed. Round 3 correction: that bootstrap claim was false, and PR #35 R11 proved it. A tree only reaches case count N+1 while the new case file is UNCOMMITTED, so every row at N+1 is dirty until the commit the check was blocking — requiring `dirty: false` outright deadlocked the one operation CLAUDE.md rule 2 makes routine. What ships instead: the band cites its run by ledger timestamp and cleanliness is judged as of that run, so a dirty row is refused only when a clean one was already available when the band was published.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the remaining half is GREEN, which is neither required nor requirable the same way — this check is in both suites, so at a new count every run is red until the band is republished and no green row could exist to republish it from. Either a bootstrap that tolerates one red row and then requires green (the same as-of trick would work), or `_band_wrong`'s comment and ADR-019 §6 state that a band's source run may be red and say what that costs. Watched red with the two rows above.
<!-- AC:END -->
