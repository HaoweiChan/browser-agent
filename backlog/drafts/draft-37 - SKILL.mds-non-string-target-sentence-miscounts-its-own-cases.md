---
id: DRAFT-37
title: SKILL.md's non-string-target sentence miscounts its own cases
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-20-D14
  - 'PR #60 R23 (LOW'
  - routed to debt). Evidence
  - >-
    verbatim: `browser-domain/SKILL.md` says
    "`resolver-non-string-target-is-a-locate-failure` for `text`
  - in `fast`
  - and its three `invariant` siblings for `name`
  - a list-valued `name`
  - '`near` and `anchor` — four keys'
  - >-
    four cases". Measured: five files match
    `evals/adversarial/resolver-non-string-*.json`
  - four tagged `invariant` (`name`
  - '`name-is-a-list`'
  - '`near`'
  - >-
    `anchor`) and one `fast` (`text`). So "three siblings" is stale — it was
    written while three existed and the fourth landed in the same commit — and
    "four cases" counts keys
  - not files.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
say four `invariant` siblings and five cases across four keys, or — better, and the standing rule — name the keys and cite the case ids without a count at all. A count in prose is a scalar nothing derives.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SKILL.md carries no case count that a `glob` can falsify.
<!-- AC:END -->
