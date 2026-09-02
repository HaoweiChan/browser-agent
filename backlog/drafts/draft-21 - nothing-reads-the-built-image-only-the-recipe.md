---
id: DRAFT-21
title: 'nothing reads the built image, only the recipe'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D8
  - >-
    PR #67 R12 (first filed from R10 in round 3; re-filed here as the Option A
    decision
  - with the third evasion class that settled it)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`build-sha-is-derived-not-supplied` is a text scan of the Dockerfile's `COPY`/`ADD` instructions. It catches an accidental context copy across every spelling its parser reads, and it does NOT establish that `.git` cannot reach the image — which is a property of admitting `.git` to the build context at all (ADR-034, "What the `.git`-in-the-context tradeoff costs"), not a defect in the check. Three evasion classes are demonstrated, each deeper than the last, and whoever picks this up has the case already made: 1. Instruction SPELLING — `copy`, indented, `ADD`, flagged, continued. Closed in PR #67 round 3 and pinned by thirteen self-test rows. 2. Instruction CLASS — verbatim, run against the shipped Dockerfile with the final stage's `COPY src/ /app/src/` replaced by `RUN --mount=type=bind,source=.git,target=/tmp/g cp -r /tmp/g /app/.git` -> `{'passed': True, 'wrong': {}}`, with the whole history in the image. 3. PARSER level — `# x \` + newline + `COPY . /app/` parses to no instructions at all and ships the whole context, green, where the retired substring regex caught it. Introduced by round 3's own repair: joining continuations closed class 1, and Docker strips comments before joining, which this parser does not.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a CI step builds the image and fails if `/app/.git` exists (`test ! -e`), run on the same trigger as the eval gate or on a schedule if the build cost cannot ride there; ADR-034's two-sentence framing then moves from "an accidental context copy is caught" to the stronger one, and this block says which run demonstrated it.
<!-- AC:END -->
