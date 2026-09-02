---
id: DRAFT-24
title: deploy-smoke still cannot prove it tested the new build
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D1
  - M44-P1
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`.github/workflows/deploy-smoke.yml` names its own fix in a comment — "a /version endpoint compared against GITHUB_SHA is the honest fix" — and the endpoint now exists (ADR-033), but the workflow is unchanged: it still sleeps a fixed 240s on `push` and then tests whatever build answers. Out of M44-P1's scope on purpose (one route plus its case), and it belongs with the milestone that consumes the sha rather than the one that produces it. The change is a step that polls `$BASE/version` until `.sha` equals `$GITHUB_SHA` — or fails loudly saying which build it got — replacing the sleep. Two things it must NOT do: treat `{"sha": null, "source": "unavailable"}` as a pass (that is the deploy misconfiguration ADR-033's Consequences names, and passing on it would restore exactly the blindness this removes), and keep the sleep as a fallback beside a real check. Two questions it has to settle rather than assume, both raised by M44-P1's cold review: the deployed sha may be ABBREVIATED, so equality has to be a prefix comparison in the right direction, not `==`; and Zeabur documents `ZEABUR_GIT_COMMIT_SHA` as "the commit the deployment belongs to", which for a merge or a rollback is not necessarily `GITHUB_SHA` — if they turn out to differ systematically, the workflow compares what it can and says which, instead of failing honest deploys.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the sleep is gone, a build mismatch fails the job with both shas in the log, and `unavailable` fails it separately with a message naming the Zeabur build-argument question — watched red by pointing the check at a sha that is not deployed.
<!-- AC:END -->
