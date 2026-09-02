---
id: DRAFT-78
title: D28's rows are declared against a build that predates the WebArea refusal
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-5
  - 'PR #43 (M40) T-M40-2'
  - >-
    split at pr-loop SPEC 2026-08-24 — the half of T-M40-2's acceptance that
    cannot be gated inside T-M40-2's own PR. Update (ADR-025
  - 'PR #51'
  - >-
    2026-08-24): the probe half of this task is done. Pre-registered in
    `specs/decisions/ADR-025-t-m40-5-preregistered-probe.md` (pushed as
    `82af7bf`
  - before any run)
  - >-
    then run 18 times against deployed `main@8183dc2` (`deploy-smoke`
    `32683725839`). Verdict: (a) zero wrong-success PASS 0/18; (b) regressed set
    ≥50% FAIL — 2/12 = 16.7% vs. prior 0/7
  - >-
    **the fix is insufficient**; (c) controls PASS; (d) 0 refusals. Full
    write-up `docs/analysis.md` §8a-4; D28 re-declared in
    `docs/support-matrix.md` (same commit); raw evidence
    `evals/report/20260824-030201-t-m40-5-probe.json`. What is NOT done: the
    probe surfaced three failure shapes (filed below as debt) that were not in
    D28's post-M32 taxonomy
  - >-
    and T-M40-2-1/T-M40-2-2 (the two levers this probe exists to attribute
    against) still need a decision now that the data they were waiting on exists
    — this block stays open until those are resolved rather than closed on "the
    re-probe happened." Update (round 2
  - '2026-08-24): re-run 18 times against a later commit'
  - '`main@c83febb` (`deploy-smoke` `32689266803`'
  - still carrying ADR-024's refusal)
  - >-
    same pre-registered thresholds and task set. Overall verdict this round:
    **PASS** — (a) 0/18 wrong-success (36/36 clean across both rounds); (b)
    regressed set **6/12 = 50.0%
  - exactly at the pre-registered bar**
  - not comfortably above it (x-rates.com 1/3→3/3
  - multpl.com 1/3→2/3
  - quotes-author 0/3→1/3
  - openlibrary.org unchanged 0/3→0/3); (c) controls 3/3 and 3/3
  - >-
    both PASS; (d) 0 refusals. Full write-up `docs/analysis.md` §8a-4 Round 2;
    ADR-025 Outcome section carries both rounds' verdicts; D28 re-declared with
    round-2 rows in `docs/support-matrix.md` (same commit); raw evidence
    `evals/report/20260824-042156-t-m40-5-probe-round2.json`. **Round 2 does NOT
    close this block's Acceptance and does NOT close M38's post-merge acceptance
    item**: 0/18 round-2 runs fired any M38 (PR #42) narrowing rung
  - >-
    so the frozen 6-task probe set is not evidence for or against M38 — the
    recovery traces to the replan path recovering mid-run (x-rates run 1
    `19ae36c1`
  - quotes run 9 `4d0d3142`
  - 'both `replans: 1`) and to possible model-side variance between builds'
  - >-
    neither of which this probe can separate. Round 2 also surfaced rep-level
    nondeterminism as its own finding — filed as T-M40-5-3 below. This block
    stays open until T-M40-2-1/T-M40-2-2 are decided (unchanged from the round-1
    update) and until T-M40-5-3 is resolved.
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
T-M40-2's acceptance ends "then the D28 rows re-declared from a post-fix probe of the same tasks". That clause is structurally not deliverable by the PR that carries the fix: a post-fix probe reads the DEPLOYED build, and the deploy is a push to `origin/main` (Zeabur), which happens after merge. D28 additionally lives on PR #43's branch and is not on `main`. So the rows that describe the WebArea failure shape stay declared against the pre-fix build until someone re-probes deliberately.

Depends (TODO.md ids): T-M40-2

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 after PR #43 has merged AND T-M40-2's fix is live on the deployed URL, the same tasks named in T-M40-2 (x-rates.com, multpl.com, quotes.toscrape.com's author page, openlibrary.org, companiesmarketcap.com as the control) are re-probed against that build and D28's rows re-declared from the results — including declaring a row `unsupported` where the probe says so. The build the probe measured is cited by sha.
<!-- AC:END -->
