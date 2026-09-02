---
id: DRAFT-63
title: the replan-path identity-anchor kill T-M40-2-4 predicted is now confirmed live
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-5-1
  - T-M40-5 probe
  - '2026-08-24'
  - '`run_id`s `110e9e8f` and `48b60ee3`'
  - build `8183dc2` (`docs/analysis.md` §8a-4
  - new failure shape 1).
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
not a new defect — `T-M40-2-4` already names this exact shape from a fixture repro (`hello.html`) and this block exists only to attach live evidence, not to duplicate the spec. On x-rates.com, ADR-024's plan lint fires correctly (the plan that would `extract` off `WebArea` is refused before execution), then the REPLAN dies on `StepError: identity anchor 'EUR to USD' absent from the page the answer was read from` — even though the correct value (`1.168062 USD` / `1.168190 USD` across the two runs) was present in the very extraction evidence the step recorded. 2 of 3 x-rates.com reps hit this in the T-M40-5 probe; the third (`591cf2dc`) resolved correctly. This confirms T-M40-2-4's fixture-predicted shape reproduces against a real deployed build and a real planner, not just the constructed `hello.html` repro.

Depends (TODO.md ids): T-M40-2-4

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 closed together with T-M40-2-4, not separately — see that block's own Acceptance (an adversarial case pinning the repro, watched red, closed by whichever lever T-M40-5's probe justifies). This block's own acceptance is narrower: T-M40-2-4 is updated to cite `110e9e8f` and `48b60ee3` as the live confirmation once that block is next touched, and this block is then closed as folded in.
<!-- AC:END -->
