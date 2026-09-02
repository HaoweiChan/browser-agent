---
id: DRAFT-80
title: >-
  the case's triage note names two read sources where its own item (1) names
  three
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R81
  - 'PR #41 R20'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`evals/adversarial/ci-numbers-are-derived.json` `triage.note` item (2) reads "Any CI figure published outside ADR-019 §5 and README", while item (1) of the same note, added in the same commit, reads "All three copies — §5's table, README's values, the workflow comment", and ADR-019 §5:263-266 states it correctly. The understatement is in the safe direction — it claims less coverage than exists, so no reader is misled about correctness — but this note is the artifact the loop keeps auditing for exactly this drift.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 item (2) reads "§5, README and the workflow comment", matching item (1) and §5.
<!-- AC:END -->
