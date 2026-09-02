---
id: DRAFT-20
title: a ledger maximum written without its marker is still invisible
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D3
  - 'PR #65 R8'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
R8's finding, verbatim, was against the mechanism that shipped in round 1 and no longer exists: "the ban is over-broad against the exemption item 12 declares — the boundary fires whenever spelled with 'maximum' or 'highest', and so does unrelated prose like 'the largest per-case p95 we tolerate is 2.50s'. Green today only by accident of §2's current wording." Both halves were reproduced (`the highest value the rule still gives 105 for is 91.30s` and the p95 sentence, each CAUGHT by the shipped denylist) alongside R5's evasions, and the pair is what retired the denylist: a regex was being asked whether a number is a claim about the ledger, which is semantic, and the two findings are that one guess failing in both directions at once. ADR-019 §6 item 12 (ledger-max) is now a graded marker, so R8's over-breadth is gone with the thing that had it — the boundary and any p95 prose are untouched by design, not by wording. What is left is the opposite ceiling, which the item now declares in the words item 10 (restatement) uses for its own: a maximum written with NO marker is invisible. That is the price of asking the author instead of guessing, and it is the same open class as T-R62 one level up.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 closed either by T-R62's answer generalising to maxima, or by a positive rule — every `NN.NNs` token in §2/§3 must sit inside a recognised marker or a declared exemption — which was costed during PR #65 R5 and rejected THEN as disproportionate: it flags roughly a dozen legitimate tokens today (the trajectory figures, the boundaries, the derivation products) and would mean restructuring prose this task is a guest in. Take it when §2/§3 are being rewritten for another reason, not on its own.
<!-- AC:END -->
