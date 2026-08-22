# Task 1 B-level plan

Hard constraint: **strong-B within 2–3 full engineering days (20–24h hour
guard), then freeze and start Task 2.** The goal is maximum reviewer-evidence
density per engineering hour, not the best possible browser agent.
Moves to `docs/plans/completed/` at freeze (ADR-001).

## Scope registry

- **MUST** (B-floor): everything tagged MUST in `docs/product/problem-definition.md`,
  `docs/evals/evaluation-methodology.md`, `docs/evals/failure-taxonomy.md`,
  `docs/architecture/task1-overview.md`. Every MUST names its rubric cell; a
  feature that can't name one gets cut.
- **SHOULD** (B-strong, only inside the time budget): hostile live domain ·
  HN/books.toscrape/Open Library beyond the ≥1-live minimum · full mutation
  catalog · OutcomeVerifier L3 · hand-labeled verifier sample (~15–20) ·
  record/replay smokes · L3-difficulty cases.
- **BACKLOG** (post-freeze M6): adaptive locator learning · verifier-accuracy
  dashboard · cost/model ablation · live-drift snapshot replay · parallel eval
  runner · visual fallback · per-IP rate limiting.

## Phases

| Phase | Depends on | Expected outputs | Validation | Main risk |
|-------|-----------|------------------|------------|-----------|
| M1 Walking Skeleton | planning package (done) | contract spec, trace schema, CLI agent loop, minimal pre-flight screen, **live Zeabur deploy**, first red→green fixture cases | deployed URL runs a real browser task | Playwright-in-Docker on Zeabur (image size, memory, sandbox flags) — that's why it's first |
| M2 Eval Backbone | M1 | fixtures + 3 mutations, EvalAuditor adapter, verifier L1–L2 + identity anchors, coverage cells, LLM stubs, cost logging, committed baseline report, **ADR-002 thresholds** | fast suite green offline | fixture/mutation scope creep — 2 fixtures, 3 mutations, stop |
| Scope checkpoint | M2 baseline | committed note: failure distribution → chosen mechanisms → explicit non-goals | note in repo before M3 code | skipping it under time pressure — it IS the evidence that investment followed measurement |
| M3 Reliability | checkpoint | classifier, ladders (≤3 families, ≥2 distinct), budgets, injected cases, relocation loop, recovery/diagnosis/mutation metrics | L4 cases red without relocation, green with; recovery metric excludes retries | building ladders for imagined failures — checkpoint guards this |
| M4 Reviewer UI | M1 deploy, M3 traces | frontend (submit, SSE progress, trace viewer, support matrix), guards verified | stranger-test: submit, watch, inspect a failure | trace retrofit — prevented by M1 trace schema |
| M5 B-Freeze | all | analysis from report data, README, curated prompts, held-out probe results, coverage verification | B-floor exit criteria below | honesty debt — unsupported list must cite real failing examples, not prose |

## B-floor exit criteria (the freeze line)

1. Deployed public frontend passes the smoke path (submit → live progress →
   inspect a failure) and has been alive since M1.
2. Coverage cells all filled (≈20–25 cases; 3 domains incl. both fixtures +
   ≥1 live; TC1–TC5; levels **L1/L2/L4/L5** — L3 only if B-strong time remains).
3. Invariant suite 100%; trap-catch ≥90%; performance meets ADR-002 numbers.
4. Real self-correction: checkpoint-chosen ladders (≥2 genuinely distinct
   families) with strategy-switch traces. Real self-maintenance: relocation
   passing all 3 tier-breaking mutations.
5. Spend cap, per-run budgets, URL guard live on the public deployment.
6. Requirement matrix (`docs/product/assignment-requirements.md`) every row
   evidenced; support matrix declared with eval backing; unsupported list cites
   concrete failing cases; cost/latency baseline in `docs/analysis.md`.

**Freeze rule**: at B-floor, if Task 2 has not started → freeze Task 1 now.
Post-freeze, only held-out-probe regressions and deliverable-claim fixes may
touch Task 1; everything else goes to M6. **Hour guard: 20–24h cumulative,
whichever comes first.**

## B-strong (only if inside the time budget)

35–45 cases · 4+ domains incl. hostile · full mutation catalog · verifier
hand-label sample reported as precision/recall · OutcomeVerifier L3 ·
expanded held-out probe.

## Risks

| Risk | Mitigation |
|------|-----------|
| Live-site flakiness poisoning metrics | API-snapshot ground truth at execution start; live cases tagged `full` only |
| LLM cost runaway | OpenRouter key spend limit + in-code budget counters; LLM stubbed in `fast` |
| Verifier/planner correlated errors | deterministic layers first; traps reported as floor; limitation stated in analysis |
| Zeabur image size / memory | M1 deploy spike; ≥1–2GB instance; context semaphore |
| Fixture-realism criticism | ≥1 live domain per B-floor, honest refusals, held-out probe results published raw |
| Public endpoint abuse | URL guard, budgets, spend cap, concurrency semaphore |
| Scope creep ("too interesting to stop") | hour guard + freeze rule + MUST-names-its-rubric-cell discipline |
