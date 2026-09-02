---
id: DRAFT-55
title: >-
  mode B's planner prompt still advertises six actions while the executor
  implements eleven
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-1
  - M42 implementation
  - >-
    2026-08-26. Found while widening the vocabulary; deliberately not fixed in
    that PR.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-027 Decision 2 widens the action vocabulary for BOTH modes, and `agent.ACTIONS` now implements `select_option`, `scroll`, `press`, `wait_for` and `go_back` for both. But `planner.SYSTEM` — the mode B prompt — still lists `navigate|click|fill|extract|extract_all|observe` and nothing else, so a live mode B planner will never emit any of the five. The capability is real and graded (five red-first cases, all mode B fixture runs with hand-written plans); what is missing is that the live planner is told about it. Why it was not done in M42: adding five verbs to `SYSTEM` changes what every live mode B run plans, and this repo's rule for that is a measurement, not an edit — the M9 ablation, the M40 probe set and D28's declared rows are all statements about the planner as it is prompted today. Doing it inside a milestone whose acceptance is a LOOP-mode smoke would move mode B's behaviour under cover of a change about the other mode, and no case in `fast` can see the difference because every offline plan is hand-written (`stub_planner`).

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `SYSTEM` gains the five verbs with their postcondition obligations stated (`press`/`go_back` must carry `expected_state`; `wait_for` needs a predicate; `extract_all` unchanged), `planner-prompt-carries-the-note`'s sibling check is extended to pin that the advertised vocabulary equals `agent.ACTIONS` minus `final_answer` — watched red first against today's `SYSTEM` — and the change lands with a live probe under the ADR-022/ADR-025 protocol showing the regressed set did not move, because that is the only thing that can tell "the planner can now wait" from "the planner now waits instead of planning". Update 2026-08-30: the vocabulary build's fixed post-change campaign failed the declared no-regression gate: 5/12 correct versus the frozen 7/12 baseline (safety still passed at 0 wrong-success). None of its 12 traces used a newly advertised verb, while quotes-author and Open Library disagreed across their own identical repetitions. This is the existing T-M40-5-3 flake, not evidence that one of the five verbs caused the loss. `planner-request-disables-sampling` was watched red against the omitted request parameter; mode B now explicitly sends `temperature: 0`. ADR-041 pre-registers one no-retry remediation campaign on the deployed fix. Keep this task open until that campaign reaches the original 7-correct threshold; do not replace the failed receipt by resampling it. Remediation outcome, 2026-08-30: the one ADR-041 campaign on deployed `6d9b94ad` also measured 5/12, with 0 wrong-success and no new verb observed. `temperature: 0` therefore does not satisfy this acceptance criterion. Keep the task open. ADR-041 is exhausted; any seed/cache follow-up needs a new pre-registration and cannot relabel another sample as this campaign. Update 2026-08-30 (ADR-042): the follow-up is now pre-registered and its content-keyed plan cache is pinned red-first by `planner-cache-is-content-keyed`. Keep this task open until ADR-042's one fixed deployment campaign restores the frozen 7/12 correctness threshold with zero wrong-success; the offline cache case alone does not prove live task quality. ADR-042 outcome: the deployed campaign produced 4/12 correct, 8 loud failures, 0 wrong-success and 0 refusal. The cache made three tasks internally stable but stabilised two of them on repeatable bad plans; multpl still split one correct and two loud failures. Keep T-M42-1 open. The single authorised campaign is exhausted; receipt `evals/report/20260829-195310-probe.json`.
<!-- AC:END -->
