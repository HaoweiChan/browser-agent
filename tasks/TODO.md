# Task 1 milestones

Milestone-level only (ADR-001) — micro-tasks live in the session. Every row
names the reviewer evidence it buys (rubric cells:
`docs/product/assignment-requirements.md` §E1–E5). Hour guard: at **20–24
cumulative engineering hours on Task 1, freeze and start Task 2** regardless of
backlog appeal.

| # | Milestone | Contents | Reviewer evidence | Validation | Status |
|---|-----------|----------|-------------------|------------|--------|
| M0 | Harness | Planning package, ADR-001, prompts convention, CLAUDE.md amendments, suite naming, browser-domain + finish-task skills, agent charter tweaks | collab, deliverable | spec-drift finds no contradiction; fast suite still exits 0 | **done** |
| M1 | Walking Skeleton (~day 1) | `specs/001-browser-contract.md` first (task id `browser`) → trace schema → NL task → plan → execute → result via CLI · minimal pre-flight screening · **deploy spike: Dockerfile + SSE hello-world + trivial Playwright run live on Zeabur** · first golden fixture cases red → green, **including the `invariant`-tagged case that backs INV-0** | deliverable, mechanism-substance (trace spine) | deployed URL runs a real browser task end-to-end; INV-0 no longer decorative | **done** — validated on the deployed instance (run 09b21b3a: success, secret-42, $0.0029); prompts/002 records the three eval-driven corrections |
| M2 | Eval Backbone (~day 1–2) | Fixtures + 3 tier-breaking mutations · EvalAuditor adapter · OutcomeVerifier L1–L2 incl. identity anchors · TC1–TC5 coverage cells · LLM stub boundary · OpenRouter cost fields in reports · baseline run → **ADR-002 sets performance thresholds** | eval-depth, silent-failure | fast suite green offline; baseline report committed | **done** — 41/41 fast, 5/5 invariant, 6/6 traps caught, $0.00; INV-1/INV-2 added with cases proven red; close-out cold review found 3 more wrong-answer-scores-PASS paths, all now cases and all fixed; ADR-002 records what is measured and what is deliberately still unset |
| — | **Scope checkpoint** (after M2 baseline, before M3 — short committed note, not a re-plan) | Observed failure distribution · highest evidence-ROI mechanisms · **what we are explicitly NOT implementing** | analysis, honesty | note committed; M3 scope follows it | **done** — `docs/evals/scope-checkpoint.md`: 12 observed failures, `locate` 4 and `act` 4 → relocation + postcondition-replan, 2 families, third refused |
| M3 | Reliability (~day 2) | Classifier (7 classes) · ladders for checkpoint-chosen families (≤3, ≥2 genuinely distinct) · budgets · injected-failure cases · self-maintenance relocation loop · recovery + diagnosis + mutation metrics | mechanism-substance | recovery metric counts only strategy-switch traces; each L4 case watched red without relocation, green with | todo |
| M4 | Reviewer UI (~day 2–3) | Full frontend on the live deployment · trace viewer · support matrix live · spend/URL guards verified | deliverable, honesty | a stranger can submit a task, watch it, inspect a failure | todo |
| M5 | B-Freeze (~day 3) | Coverage cells verified · cost/latency numbers · `docs/analysis.md` from report data · README rewrite · prompts curated · **eval-adversary held-out probe vs deployed URL (mandatory gate, raw results in analysis)** | analysis, collab, all | B-floor exit criteria in `docs/plans/active/task1-b-level-plan.md` all green → **STOP, start Task 2** | todo |
| M6 | Optional hardening (post-freeze A-backlog, ranked reviewer-value ÷ effort) | hand-labeled verifier sample → precision/recall · hostile live domain · full mutation catalog · verifier-accuracy dashboard · cost/model ablation via OpenRouter · live-drift snapshot replay · adaptive locator learning · parallel eval runner · visual fallback (last) | E5 markers | each item lands with its own eval evidence | backlog |

Plan: `docs/plans/active/task1-b-level-plan.md` ·
Methodology: `docs/evals/evaluation-methodology.md` ·
Architecture: `docs/architecture/task1-overview.md`
