---
id: DRAFT-58
title: 'an extraction answers with the LINE the value sits on, not the value'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M41-2
  - M41
  - '2026-08-26'
  - >-
    ADR-030's probe and its two offline twins. Both frozen probe tasks — `What
    is the doc_status of the aapl-2025 fixture?` and `How many items are
    extracted?` — are answered from one status line
  - >-
    `doc_status: success — 18 extracted · 5 incorporated_by_reference fixture:
    aapl-2025`. ADR-030 froze "an answer that carries the ground-truth value is
    correct" BEFORE the runs
  - >-
    so this is not a threshold moved after the fact and the probe's numbers
    stand; but a caller who asked how many items were extracted got a sentence
    containing 18
  - >-
    not 18. Every guard passes honestly: `not_a_dump` sees 79 characters against
    a page of thousands
  - '`grounded` and `identity_anchors` hold'
  - >-
    and the judge certifies. Pinned as published behaviour by
    `sec10k-item-count-is-in-the-named-status` and
    `live-sec10k-authored-wait-reaches-the-item-count`
  - both of which carry the whole line as `expect.answer`
  - and declared in `docs/support-matrix.md` D30.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decide whether answer granularity is this repo's problem at all, and record the decision either way. Two routes exist and one is a trap. The page-side route (an element per number) is not available in general and is not a capability of this agent. The executor-side route — a step that reduces an extracted string to the part the task asked for — is where the trap is: any pattern taken from the page is site-specific knowledge in the execution policy (rule 6), and any pattern taken from the task text is the `_AGGREGATE`/`SCOPE_BLOCK` ceiling D21 already names. A third possibility is that this is correctly the judge's business and not the executor's. No code until that is decided, and whatever is decided lands with its own red-first case.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
