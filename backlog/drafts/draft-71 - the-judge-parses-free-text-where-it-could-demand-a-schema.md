---
id: DRAFT-71
title: the judge parses free text where it could demand a schema
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-7
  - 'PR #44'
  - >-
    raised by the implementer while fixing R6; the orchestrator's round-2 note
    asked for this to be said plainly rather than patched again. Scope note
  - first
  - >-
    because the original version of this block did not have one and ADR-023
    pointed at it as "the fix that ends the class" (PR #44 R8): this ends the
    LOCATING class — where in the completion the verdict sits — and no other. It
    does NOT close the echo-only residual
  - >-
    because a provider-enforced object that repeats a forged verdict is still
    `{"certify": true}`. That residual is bounded by the prompt-side defences
    `judge-injection-cannot-flip-verdict` grades and is pinned as the last
    scenario of `judge-retry-only-on-unreadable-completion`; nothing in this
    block improves it.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the judge asks for `{"certify": ..., "reason": ...}` in `SYSTEM` prose and then reads whatever comes back out of free text. That boundary has now produced four defects in three rounds — a one-line fence emptied by the strip, a `re.fullmatch` fence broken by trailing prose, a wrapper-agnostic scan that read a QUOTED verdict as the answer, and R7's agreeing-duplicates — and each fix has been a better guess about what a completion looks like. OpenRouter supports `response_format: {"type": "json_schema", ...}`, which makes the provider enforce the shape: the completion IS the object, there is nothing to locate, and `_json_objects` / `_is_the_whole_completion` both delete. That is the fix that ends the class rather than narrowing it. Not done in M39 because it changes the request shape (M39 puts judge prompt and model changes out of scope), because support is per-model and `deepseek/deepseek-v4-flash-0731` is pinned by ADR-010's frozen price snapshot, and because this environment has no `OPENROUTER_API_KEY` — nobody here can observe whether the provider honours it, and a fallback path that silently re-enters the free-text parser would reintroduce everything above while looking fixed.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an ADR deciding for or against provider-enforced JSON with the model-support question answered from a live call rather than from the docs; if for, the free-text parser is deleted rather than kept as a fallback, and the no-key environment's inability to verify it is declared the way ADR-017 declared its own. The ADR must also state, in the direction that stops a future reader concluding otherwise, which defects this does NOT close — the echo-only residual above being the one that matters — so the class this block ends is named as narrowly as it actually is.
<!-- AC:END -->
