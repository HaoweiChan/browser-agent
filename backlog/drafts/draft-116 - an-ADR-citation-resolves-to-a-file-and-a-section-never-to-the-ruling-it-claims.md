---
id: DRAFT-116
title: >-
  an ADR citation resolves to a file and a section, never to the ruling it
  claims
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R57
  - T-R56 (the T-R52 half)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`adr-header-and-index` now resolves every `ADR-0NN` reference — canonical or in an identifier spelling like `adr019` — to a committed decision, and every sectioned reference to a section that decision actually has, across README.md, CLAUDE.md, tasks/TODO.md, tasks/DONE.md and `src/ evals/ specs/ .github/ docs/ prompts/`. What it cannot say is whether the cited section RULES on the subject of the citing sentence — the T-R52 defect was catchable only because the judge ADR has no numbered sections, so the repaired citations carry a section and a re-miscitation is red. A citation written without a section, to an ADR that happens to have one, still resolves. Three mechanisms for the semantic half were measured against this tree and each was unusable as a gate: rare-word overlap between the citing line and the cited Ruling (70 false positives), the cited ADR having to enforce a mechanism named on the same line (40 — INDEX lines legitimately name one ADR's enforcers beside references to others), and a file having to cite every ADR that uniquely owns an identifier it uses (8 files, every one legitimate — implementation files use ADR-ruled identifiers without citing them).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either citations carry a section reference by convention and the check requires one (so the resolution above is the whole property), or a subject test is found that is red on the five T-R52 citations and green on every other citation this tree carries. Watched red on both.
<!-- AC:END -->
