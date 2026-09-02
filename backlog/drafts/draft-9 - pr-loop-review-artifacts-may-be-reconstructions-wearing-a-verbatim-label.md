---
id: DRAFT-9
title: pr-loop review artifacts may be reconstructions wearing a verbatim label
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D4
  - 'PR #70'
  - found while committing `tasks/reviews/pr70-r1.json`.
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the `groundwork:pr-reviewer` subagent type has tools Read/Grep/Glob/Bash and NO message tool, so it cannot return its findings array to the orchestrator that spawned it — its output reaches the parent only as its terminal message, which in PR #70's case surfaced to the coordinating session rather than to the orchestrator. The orchestrator requested the raw array twice and never received it in-context, so `tasks/reviews/pr70-r1.json` carries a `text_provenance` field declaring its finding text as a RELAY rather than the reviewer's own bytes.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 NOT fixable in this repo — the fix belongs in the groundwork plugin (give the reviewer agent a message tool, or have the orchestrator write the artifact from a file the reviewer produces). Same cross-repo constraint T-M39-15 recorded for its own two pr-loop-layer blocks. Closing this block means either the plugin change landing upstream, or a recorded decision that review artifacts declare their provenance permanently.
<!-- AC:END -->
