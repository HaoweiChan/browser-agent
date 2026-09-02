---
id: DRAFT-11
title: a viewport-sized drill target grades red while behaving correctly
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D6
  - 'PR #70 R10 (the half that is not a text fix).'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_shot_ok` in `src/browser/eval_adapter.py` defines an `element` frame as one whose pixel area is STRICTLY smaller than every viewport frame the run showed — the check that makes "a viewport shot relabelled `element`" red. For a drill target whose box COVERS the viewport in both axes the clip `<box ∩ viewport>` degenerates to the viewport itself, so a correct run writes a crop of exactly viewport area, labels it `element`, and any case asserting `"element"` for that turn goes red. Nothing fails today: every drill fixture in this repo targets a sub-viewport region, so the shape is unreachable from the committed cases. It is recorded because "no fixture shows this shape" is the sentence this repo keeps falsifying. ADR-035 Decision 2 declares the eval set authoritative here and says why the rule is not relaxed to `<=`: that would retire the relabelling guard, which is worth more than the degenerate shape — and the authority it is granted is one-directional, because `_shot_ok`'s `"viewport"` branch tests the LABEL alone and no area at all, so the strict inequality catches an element frame that is secretly a viewport shot and nothing catches a viewport frame that is secretly a crop (PR #70 R16, recorded rather than fixed: widening that branch is a grader change this round is not making).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `_shot_ok` distinguishes "smaller than the viewport" from "clipped to the viewport", with the fixture above as its case and the relabelling guard still red on a genuine viewport shot — or Decision 2's declaration is promoted into the grader's own docstring so the next reader of `_shot_ok` finds it there.
<!-- AC:END -->
