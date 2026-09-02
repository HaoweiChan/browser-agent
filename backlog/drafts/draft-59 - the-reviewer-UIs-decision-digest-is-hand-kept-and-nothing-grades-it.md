---
id: DRAFT-59
title: the reviewer UI's decision digest is hand-kept and nothing grades it
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M41-6
  - M41 spec-drift audit
  - >-
    2026-08-26. `src/browser/server.py`'s `ADRS` array renders "N architecture
    decisions" to every visitor and had gone two decisions stale — no 023 (on
    `main` since M39)
  - >-
    no 027 (merged) — while a comment beside it asserted the numbering had
    exactly one gap. M41 added the three missing lines and deleted the false
    claim
  - 'which fixes today and not tomorrow: the next ADR reddens nothing.'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
grade the digest the way `ui-examples-cover-matrix` grades the demo cards — the set of numbers in `ADRS` must equal the set of `specs/decisions/ADR-*.md` files, in both directions. One `parse`-free check, no browser. Watched red by deleting a line from the array. Deliberately does NOT grade the one-liner's

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
