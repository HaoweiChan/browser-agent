# Task 1 A-level plan

Premise: the B-freeze happened and its record stands — M0–M5 done, 5 of 6
B-floor criteria met, criterion 2 (live breadth) partial. On 2026-08-17 the
owner reopened Task 1 (prompts/008): **B-baseline is accepted; the repo does
not go public yet; reach A-level first.** This supersedes the freeze rule in
`docs/plans/completed/task1-b-level-plan.md` by explicit instruction; Task 2
start is deferred by the same decision. This plan governs the reopened phase
and moves to `completed/` at A-freeze (ADR-001).

## What A-level means here

Not feature count. Anchored to rubric cell E5 (`docs/product/assignment-requirements.md`)
plus the two gaps the freeze actually measured:

1. **Live capability is thin** — 1 live domain, 1 task class, and the held-out
   probe scored 2/8 correct answers (about one hop deep).
2. **Verifier guarantees held by luck once** — probe #5's page-dump answer was
   rejected on a whitespace technicality; nothing checks that an answer is
   *responsive*. Precision/recall of the verifier has never been measured.

A-level = those gaps closed or honestly quantified, plus the E5 markers
(layered tradeoffs, honest failure modes) evidenced by committed data.

## Scope registry

- **MUST** (A-floor): live breadth (≥2 new live domains, ≥3 task classes live,
  L3 cases) · verifier hand-label sample → precision/recall · answer
  responsiveness check · full mutation catalog · hostile live domain ·
  cost/model ablation · second held-out probe as the A-freeze gate.
- **SHOULD** (only inside the time budget): live-drift snapshot replay ·
  expanded probe (>10 tasks) · OutcomeVerifier L3.
- **BACKLOG** (still out, unchanged from B-plan): adaptive locator learning ·
  parallel eval runner · verifier-accuracy dashboard (the *numbers* are MUST;
  the dashboard UI is not) · visual fallback · per-IP rate limiting.

## Phases

Ranked by reviewer-value ÷ effort, measured-gaps first.

| Phase | Depends on | Expected outputs | Validation | Main risk |
|-------|-----------|------------------|------------|-----------|
| M6 Live breadth & depth | reopen note | ≥2 new live domains (candidates: Hacker News, Open Library — named in the B-plan SHOULD list) · ≥3 task classes exercised live · L3-difficulty cases · support-matrix rows for each new domain | criterion 2 fully met; every new case watched red first; live cases carry the `live` tag (and `full`), so the offline gate never touches the network | live flakiness poisoning metrics — snapshot ground truth at run start |
| M7 Verifier accuracy | M6 traces (more live runs to label) | ~20–30 hand-labeled runs → precision/recall in `docs/analysis.md` · responsiveness check on answer-seeking tasks · new trap cases | numbers computed from committed labels; responsiveness trap case red before the fix | labeling the runs the verifier already handles well — sample must include live + probe-style runs |
| M8 Mutation & hostility | none (parallel-safe after M6) | full mutation catalog · hostile live domain · (SHOULD) live-drift snapshot replay | each new mutation red without relocation, green with; hostile results published raw | catalog scope creep — each mutation must break a tier a plan stands on, or it's decoration |
| M9 Cost/model ablation | stable suite from M6–M8 | ≥2-model OpenRouter ablation · cost/latency tradeoff table · ADR records the chosen default and why | table built from committed report runs, not estimates | paying for runs that answer no question — fix the question per ADR before running |
| M10 A-Freeze | all | analysis/README/support-matrix refresh · prompts curated · **second held-out probe vs deployed URL (mandatory gate, raw results committed)** | A-exit criteria below all green → owner decides submission/public | honesty debt — improvements must cite runs, not prose |

## A-exit criteria (the A-freeze line)

1. Coverage criterion 2 fully met: ≥3 live domains, ≥3 task classes live,
   L1/L2/L3/L4/L5 all filled.
2. Verifier precision/recall reported from ≥20 hand-labeled runs, committed;
   responsiveness gap closed or explicitly declared as a limitation.
3. Full mutation catalog passing, each case seen red first; hostile-domain
   results published raw.
4. Cost/model ablation table in `docs/analysis.md` from committed runs; ADR
   for the default-model choice.
5. Second held-out probe: **zero wrong-answer-reported-as-success stays
   inviolable**; correct-answer rate published raw against the 2/8 baseline
   (goal: ≥2×, reported honestly either way).
6. Invariant suite still 100%; fast suite green; no baseline move without an ADR.
7. ~~Repo stays private until the owner flips it after A-freeze.~~
   **Superseded 2026-08-17, owner's call**: the repo went public before
   A-freeze, because server-side branch protection on `main` (required
   `eval-gate`, strict, `enforce_admins`) is unavailable on a free plan while
   the repo is private. Struck rather than deleted — an exit criterion that
   quietly disappears is the drift `spec-drift` exists to catch. A-freeze
   inherits no privacy condition; the deliverable was always a public repo
   (assignment R2).

## Hour guard

The B-phase guard is what made the freeze happen — it worked. The A-phase gets
one too: **default +12 engineering hours from reopen, then A-freeze with
whatever is green**, unless the owner sets a different number. An unbounded
reopen is the exact failure the freeze rule existed to prevent.

## Risks

| Risk | Mitigation |
|------|-----------|
| Reopen becomes unbounded ("too interesting to stop", again) | hour guard + MUST-names-its-rubric-cell discipline carried over |
| Live-site flakiness | `full`-tag isolation + API/snapshot ground truth, as in B-phase |
| Probe #2 regresses on the inviolable property | any wrong-answer-as-success is a stop-the-line defect, not a rate |
| Verifier labels biased toward easy runs | sample drawn from live + probe traces, not fixtures only |
