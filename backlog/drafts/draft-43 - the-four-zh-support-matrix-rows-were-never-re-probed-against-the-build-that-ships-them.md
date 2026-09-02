---
id: DRAFT-43
title: >-
  the four zh support-matrix rows were never re-probed against the build that
  ships them
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D5
  - M45 spec-drift audit
  - '2026-08-26'
  - finding 6. Structural
  - >-
    not an oversight: the obligation cannot be discharged from inside the PR
    that incurs it.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-022 Decision 1a requires every live-declared row to be re-run against the build being shipped, immediately before merge — the rule that exists because two of the three rows it was written for were withdrawn when a build changed underneath them. M45's four zh rows (`docs/support-matrix.md`, "Chinese-language (zh) evidence") were measured against `main@9c3340c`; merging M45 moves `main` and the deployment follows it, so the shipping build is a different build from the measured one. It is not a different BEHAVIOUR — M45 ships no production code change and `SCOPE_BLOCK` was byte-for-byte what it was, and stayed so until M45-D6's fold on 2026-08-28 — but 1a is a rule about the build, written that way because the rows it was created for were invalidated by a build change nobody expected to matter. No re-probe is possible pre-merge because the deployment only moves when `main` does — the same wall ADR-025 hit, which is why T-M40-5 was split out as its own task rather than folded into the PR that created the need. The gap is declared in the matrix section itself rather than left implicit, and the substantive risk is low and stated: this PR changes no production code, and no Group A task contains a `SCOPE_BLOCK` term in any case. Low risk is not a re-run.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 after M45 merges and `deploy-smoke` succeeds for the merge sha, the four Group A rows are re-run 3× each in Chinese against the deployed build, every run id published, and the matrix rows re-declared from the new numbers — including declaring a shape unsupported if the re-probe says so. If the re-probe contradicts the 12/12, the rows are withdrawn, not softened. Additionally: B1, B2 and B3 (密碼學 / 購買力平價 / 刪除的檔案) are re-submitted once each and must **still refuse**, at $0.00 with an empty trace, confirming D31's declared residual on the deployed build. That direction is deliberate and worth stating, because an earlier draft of this block had it backwards — it asked them to RUN, which would have made this probe's pass condition the opposite of what M45 shipped, and handed whoever ran it either a phantom regression or a reason to ship one of the narrowings M45 withdrew on purpose.
<!-- AC:END -->
