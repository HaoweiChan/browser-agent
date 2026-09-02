---
id: DRAFT-3
title: five of the seven trigger classes reach the escalation with no case
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M46-4
  - M46 implementation
  - cold review finding 3.
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-037 Decision 2 admits all seven failure classes. The six cases exercise `locate` and `semantic`; `nav`, `act`, `extract`, `task` and `env` reach the policy through the same unbranched `status.startswith("failure:")`, so nothing today distinguishes them — which is why this is coverage and not a defect. Two of the five are worth cases in their own right rather than for symmetry: a `nav` trigger makes the loop leg's first act byte-identical to the plan leg's failed one (the pre-plan navigation runs before either cadence is consulted), so what looks like a cadence recovery is a network retry; and the url-guard `task` refusal is static, so the second leg refuses identically and the run pays a browser launch to learn nothing.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a case per class the policy could plausibly treat differently — starting with `nav` (a first-request-fails fixture, asserting the two legs' first steps are identical) and the url-guard `task` refusal (asserting two legs with the same status and no wasted claim of recovery). M50 explicitly retires or replaces the legacy two-leg `judge_calls: 2` path with a canonical retry call-budget case; M52 reports canonical retry rate BY trigger class, so a `nav` retry is never counted as evidence that the canonical graph helped.
<!-- AC:END -->
