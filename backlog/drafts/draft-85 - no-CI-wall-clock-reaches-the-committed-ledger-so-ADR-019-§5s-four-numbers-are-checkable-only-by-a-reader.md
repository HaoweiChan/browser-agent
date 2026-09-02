---
id: DRAFT-85
title: >-
  no CI wall clock reaches the committed ledger, so ADR-019 §5's four numbers
  are checkable only by a reader
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R73
  - T-R44
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
T-R51 was closed on the labelling route, not the ledger route (ADR-019 §7): §5's four CI numbers now name eval-gate run 32561162459 attempts 1-4, which `gh run view 32561162459 --attempt N --log` reprints, and README's older unlabelled CI band (59.77 / 60.84 / 64.61 / 64.67s) is struck. What is still true is that `.github/workflows/eval.yml` runs the two suites and stops: no CI row is in `evals/report/history.jsonl`, so `published-band-matches- the-ledger` grades exactly one environment's bands here and §6 item 9 (environment) has one value to discriminate on. The mechanism to do better exists now — rows carry `env` and the band sentence names it — so a CI band would be gradeable the day a CI row lands.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either a workflow step that publishes CI's history row as an artifact the check can read (or commits it), plus `Band source — ci ...` sentences in §5 that item 9 grades, or a recorded decision that CI's numbers stay reader-verified and §5/§7 say so permanently.
<!-- AC:END -->
