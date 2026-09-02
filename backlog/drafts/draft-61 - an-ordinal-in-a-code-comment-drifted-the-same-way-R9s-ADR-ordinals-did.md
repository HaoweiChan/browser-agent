---
id: DRAFT-61
title: an ordinal in a code comment drifted the same way R9's ADR ordinals did
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M41-8
  - 'PR #58 R11'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/eval_adapter.py:5181-5182` reads "while this check stayed green and the third conjunct below actively rewarded the string's presence". The conjunct that rewards the endpoint string is `cases_not_citing_the_ground_truth_endpoint`, key 4 of 4 in the `wrong` dict at :5201-5204 (order: `endpoint_in_production_module`, `host_outside_the_allowlist`, `ground_truth_endpoint_fed_to_the_executor`, `cases_not_citing_the_ground_truth_endpoint`). No counting basis makes it third: counting `wrong` keys it is fourth; counting only conjuncts textually below the comment it is second. ADR-030:160, rewritten in PR #58's round-3 repair, now calls that same conjunct "the last". This is the third instance of the ordinal drift R9 was filed against — the count is derived and graded, the POSITION is derived by nothing — surviving in the one place R9's acceptance clause did not name, because that clause named only ADR-030 and D30. Introduced in `db54986` (PR #58 round-1 repair), so it predates the round-3 diff; routed to debt rather than repaired because it is LOW, out of scope for the three clauses the human's bounded round authorised, and nothing grades it.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the comment names the conjunct instead of numbering it (e.g. "the citation conjunct below"), matching what ADR-030 and support-matrix D30 now do; `invariant` and `fast` stay green. Worth deciding once for the repo rather than per site: an ordinal into a list nothing derives is a re-typed number, and this is the fourth one this PR found.
<!-- AC:END -->
