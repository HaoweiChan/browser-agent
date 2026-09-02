---
id: DRAFT-5
title: a live case is green for a reason its provenance does not give
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-A39-2
  - ADR-039 §2
  - 2026-08-28.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`live-sec10k-authored-wait-reaches-the-doc-status` asserts `planner_saw.lacks: ["18 extracted"]` and its provenance explains the absence as claim (1): "the deep link removes the click, not the race" — the observation is taken before the page's own extraction round trip lands. After ADR-039 that explanation is false and the assertion still holds. Measured 2026-08-28 against the deployed inspector: the observation now CONTAINS the per-item sidebar buttons (`button — '1 Business EXTRACTED CONF 0.95 HEADING_STRICT 16,053 CH'`), which only exist after the round trip lands, so the race the provenance describes is over by observation time. `18 extracted` is absent because `observe.TEXT_HEAD` caps the rendered page text at 300 characters, hundreds of characters before the status line — a claim about a text cap wearing a provenance about a network race. This is the shape `evals/labels`-adjacent review keeps finding and CLAUDE.md rule 2's cousin: a green whose stated claim it can no longer falsify.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either (a) the case is re-pointed at something the S1 fix genuinely leaves absent and its provenance rewritten to say what it now grades, or (b) the `lacks` clause is dropped and the S1 claim moves to a case that can falsify it — decided by running the case with `TEXT_HEAD` raised, which is the one-line probe that separates the two explanations. Not closed by editing the provenance alone: the prose was never the defect.
<!-- AC:END -->
