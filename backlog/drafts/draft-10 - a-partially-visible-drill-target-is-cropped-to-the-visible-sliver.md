---
id: DRAFT-10
title: a partially visible drill target is cropped to the visible sliver
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D5
  - 'PR #70 R11 (LOW'
  - routed debt).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the drill crop is `page.screenshot(clip=<box ∩ viewport>)`, so an element that is only partly on screen yields only the part that is on screen — a model drilling into a region scrolled halfway off the bottom sees the top half and is told nothing about the rest. ADR-035 Decision 2 discloses it in words ("A partially visible element is cropped to the visible intersection"), it is strictly better than the behaviour it replaced (which scrolled, and on a lazy-load page changed what the run read next — PR #70 R1), and the ARIA half of the drill observation is unaffected and complete either way. So this is a rendering nicety, not a correctness hole, and it is filed rather than fixed.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the model is told the crop is partial (a field on the scoped observation, graded by a case that reddens when a partial crop is presented as whole), or Decision 2 states that a partial crop is presented as if complete and accepts it in those words. NOTE: the round-2 verbatim finding text for R11 never reached this session — this block is written from the orchestrator's summary plus the ADR clause it cites, and should be replaced with the reviewer's own bytes if they differ.
<!-- AC:END -->
