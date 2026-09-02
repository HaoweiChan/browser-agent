---
id: DRAFT-33
title: a resolution that used TWO relaxations discloses only one
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D10
  - 'PR #60 R14 (LOW'
  - >-
    routed to debt). Named as an open question in ADR-032's "What this does NOT
    settle". Evidence
  - 'verbatim: `resolver.py`''s `near` branch returns `loc.nth(i)'
  - '''structural'''
  - '((f''near-{how}'' if how in (''normalised'''
  - '''prefix'') else None) or fold)` — the `or` short-circuits'
  - >-
    so a truthy `near-normalised` hides `name-case-folded`. On a page with two
    links both named `SAVE FOR LATER` beside anchors `Ada's row` / `Bob row`
  - 'target `{''role'':''link'''
  - '''name'':''Save for later'''
  - >-
    'near':"Ada's row"}` resolves tier `structural` with note `near-normalised`
    — the case fold is not reported anywhere.
    `resolver-case-fold-is-recorded-in-the-trace` uses `index: 0`
  - which cannot reach this branch.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
join the non-None parts rather than picking one — the trace note is a list of what was relaxed, not a single label — and pin it with a case whose `trace_note_contains` requires `name-case-folded` on a `near-normalised` resolution. Cheap, but it changes the shape of a graded string, so every existing `trace_note_contains` expectation has to be re-read against it first; that is why it is not done in the round that found it.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 both labels appear when both relaxations were used, and no existing `trace_note_contains` case changes meaning.
<!-- AC:END -->
