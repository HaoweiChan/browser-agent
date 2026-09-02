---
id: DRAFT-125
title: >-
  M28 half (b): isolate the asked cell before giving up on a container
  extraction
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R66
  - M28 implementer
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
M28 shipped half (a) — a verifier-rejected run now carries `answer: null`, the rejected extraction stays in `evidence.extractions`, and `verify()` cites offending values by a bounded preview (`CITE_CHARS`) rather than quoting the dump back into `reason` (`extract-container-dump-is-not-the-answer`). Half (b), trying ONE narrower isolation before failing, was not built: on the live run (4bade630) the plan's `near` was the table CAPTION ("Tokyo 東京都"), not the label of the asked value, so re-resolving descendant cells near that anchor cannot pick "Population" — any site-agnostic isolation has to read the TASK text for a label word, and a keyword heuristic over the task is the regex-over-English ceiling this repo has already paid for three times (SCOPE_BLOCK, `_AGGREGATE`, D23). The cell-targeted plan already works on the same page shape (`{role: cell, near: "Motto"}`, runs 735cf2da / a5b9b065), so the honest upgrade is planner targeting (M32's half) or a replan note that names the shape ("the container you extracted holds N cells; target the one the question asks for") — not an executor heuristic.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a replan-after-dump path or a planner prompt rule, pinned by the same fixture (`city-infobox.html`) with the container plan as the FIRST stub plan and the cell plan as the second; plus a negative twin where the label is absent and the run must still end `answer: null`, never a guessed cell.
<!-- AC:END -->
