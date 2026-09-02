---
id: DRAFT-27
title: the fence fix closed the instance and not the class
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-15-D6
  - T-M39-15
  - 'PR #69 R19 (round 3'
  - circuit breaker).
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
R8's repair stopped `tasks/TODO.md`'s one prose line from acting as a fence opener. It **closed the instance and not the class**. `_FENCE` still treats a bare whole-line ``` as a valid opener, so a stray one pairs with a later block's delimiter and swallows the headings between them. Verified repro (orchestrator's, not the reviewer's): two `### B1 — ` headings separated by a stray bare whole-line ``` , with a ```bash block below, yield `['B1']` — the duplicate is silently missed. **Latent, not live.** Neither `tasks/TODO.md` nor `tasks/DONE.md` contains a bare whole-line ``` today, and TODO.md's only fence line carries trailing text so it no longer parses as an opener. The probe is NOT blinded on this tree, which is why this is debt rather than a blocker. **What is NOT broken, recorded because it was claimed to be:** the reviewer's second variant — an info string outside the opener char class, ```js {hl} — reports the duplicate CORRECTLY (`['B2', 'B2']`), because it never parses as an opener at all. Falsified by the orchestrator before it reached this block. A block that records what is not broken is more useful than one that overstates.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a fixture with a stray bare whole-line ``` above a genuine duplicate, watched red first, plus either a fence state machine or a stripper that discards nothing when delimiters fail to balance. The info-string variant needs no fix. Also in scope, and the part worth doing first: `src/browser/eval_adapter.py`'s shipped `ponytail:` comment asserts the fix leaves "at worst a loud false red, never a silent miss". That is **not true** — the repro above is exactly a silent miss. The comment overstates its own guarantee and must be corrected with the fix; a comment that promises a safety property the code does not have is worse than no comment, because the next reader stops looking.
<!-- AC:END -->
