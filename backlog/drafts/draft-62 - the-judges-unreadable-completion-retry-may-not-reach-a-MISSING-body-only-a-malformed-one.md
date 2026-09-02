---
id: DRAFT-62
title: >-
  the judge's unreadable-completion retry may not reach a MISSING body, only a
  malformed one
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-12
  - T-M40-5 probe
  - '2026-08-24'
  - '`run_id 97677d75`'
  - build `8183dc2` (`docs/analysis.md` §8a-4
  - new failure shape 2).
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
this is not a new defect — it is a second live instance of the class PR #44 (M39, not yet merged — its decision file is numbered 023 but that number does not resolve on this branch, per ADR-025's own collision check) is fixing, and a distinct sub-shape from the one M39 was built against. M39's retry is scoped to exactly one branch: `live_judge`'s `json.loads` of the completion body raising `JSONDecodeError` (`src/browser/judge.py`), because run `7787f9c9` (the case that motivated M39) recorded `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` — a body that parsed as empty string, i.e. a MALFORMED (present-but-unparseable) body. `run_id 97677d75` recorded a different exception entirely: `JudgeError: malformed judge response: AttributeError: 'NoneType' object has no attribute 'strip'` — a `.strip()` (or similar) call on a body that is `None`, i.e. a MISSING body, one level up from where `json.loads` ever runs. The extraction this run tried to grade was correct (`"Market cap: $4.514 Trillion USD"`, matching the `curl`-re-verified ground truth) and ADR-017's fail-closed rule held — the run correctly did not certify a verdict it never received — but if M39's retry guard (`retryable=True` set only at the `JSONDecodeError` site) does not also fire on a `None`/absent body, this exact shape survives PR #44 unfixed: one more malformed-completion class costing a correct run, exactly the harm M39 exists to prevent, just arriving one processing step earlier.

Depends (TODO.md ids): M39

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 read PR #44's merged `src/browser/judge.py` once it lands — if the missing-body path already sets `retryable=True` (e.g. a `None`-body guard ahead of or alongside the `json.loads` try) this block closes as already covered, cited by line. If it does not, an adversarial case pinning a `None`/absent judge completion body (not an empty-string/malformed JSON body — M39's own cases already cover that one) is added and watched red against M39's shipped fix before either the guard is widened or this is declared a deliberately separate, un-widened scope.
<!-- AC:END -->
