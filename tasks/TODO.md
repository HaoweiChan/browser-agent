# Task 1 milestones

Milestone-level only (ADR-001) — micro-tasks live in the session. Every row
names the reviewer evidence it buys (rubric cells:
`docs/product/assignment-requirements.md` §E1–E5). Hour guard: at **20–24
cumulative engineering hours on Task 1, freeze and start Task 2** regardless of
backlog appeal. *(B-freeze executed at M5; guard superseded 2026-08-17 by the
owner's reopen decision — see the Reopen note below. A-phase guard: +12h.)*

| # | Milestone | Contents | Reviewer evidence | Validation | Status |
|---|-----------|----------|-------------------|------------|--------|
| M0 | Harness | Planning package, ADR-001, prompts convention, CLAUDE.md amendments, suite naming, browser-domain + finish-task skills, agent charter tweaks | collab, deliverable | spec-drift finds no contradiction; fast suite still exits 0 | **done** |
| M1 | Walking Skeleton (~day 1) | `specs/001-browser-contract.md` first (task id `browser`) → trace schema → NL task → plan → execute → result via CLI · minimal pre-flight screening · **deploy spike: Dockerfile + SSE hello-world + trivial Playwright run live on Zeabur** · first golden fixture cases red → green, **including the `invariant`-tagged case that backs INV-0** | deliverable, mechanism-substance (trace spine) | deployed URL runs a real browser task end-to-end; INV-0 no longer decorative | **done** — validated on the deployed instance (run 09b21b3a: success, secret-42, $0.0029); prompts/002 records the three eval-driven corrections |
| M2 | Eval Backbone (~day 1–2) | Fixtures + 3 tier-breaking mutations · EvalAuditor adapter · OutcomeVerifier L1–L2 incl. identity anchors · TC1–TC5 coverage cells · LLM stub boundary · OpenRouter cost fields in reports · baseline run → **ADR-002 sets performance thresholds** | eval-depth, silent-failure | fast suite green offline; baseline report committed | **done** — 41/41 fast, 5/5 invariant, 6/6 traps caught, $0.00; INV-1/INV-2 added with cases proven red; close-out cold review found 3 more wrong-answer-scores-PASS paths, all now cases and all fixed; ADR-002 records what is measured and what is deliberately still unset |
| — | **Scope checkpoint** (after M2 baseline, before M3 — short committed note, not a re-plan) | Observed failure distribution · highest evidence-ROI mechanisms · **what we are explicitly NOT implementing** | analysis, honesty | note committed; M3 scope follows it | **done** — `docs/evals/scope-checkpoint.md`: 12 observed failures, `locate` 4 and `act` 4 → relocation + postcondition-replan, 2 families, third refused |
| M3 | Reliability (~day 2) | Classifier (7 classes) · ladders for checkpoint-chosen families (≤3, ≥2 genuinely distinct) · budgets · injected-failure cases · self-maintenance relocation loop · recovery + diagnosis + mutation metrics | mechanism-substance | recovery metric counts only strategy-switch traces; each L4 case watched red without relocation, green with | **done** — 49/49 fast, 10/10 invariant, $0.00, 23.4s; recovery 3/3 verified (6 rungs tried), mutation 4/4 passed **2 by relocating**, diagnosis 5/5; `l4-shop-button-text-renamed` flipped failure:locate → success on an unchanged plan (report history: `20260816-154959` red → `20260816-160339` green); INV-3 added; ADR-003 records what is measured and that recovery-as-a-rate stays unset |
| M4 | Reviewer UI (~day 2–3) | Full frontend on the live deployment · trace viewer · support matrix live · spend/URL guards verified | deliverable, honesty | a stranger can submit a task, watch it, inspect a failure | **done** — 52/52 fast, 12/12 invariant, $0.00, 24.3s; SSE trace stream (every attempt, incl. superseded), per-step screenshots, matrix served from `docs/support-matrix.md` itself; guard refused `http://127.1/admin` in-browser before a browser opened; ADR-004 records what the UI is not allowed to hide. **Live-planner submit path is unverified on the deployment** — needs the key, folded into M5's held-out probe |
| — | **Cold review** (M3 + M4, before the M5 freeze — the first two milestones committed without one) | Two scopes: reliability core, gateway/UI · findings → cases → fixes · unfixed findings declared | eval-depth, honesty | every new case watched red against its own fix | **done** — 6 defects in code already green on 52 cases, 3 of them wrong-or-unverified-answer-scores-PASS: grader equated `-39`/`39` and `€18`/`$18`; a replan laundered an action that never landed (success + wrong answer); a retry wore recovery's badge; the URL guard was an input filter only (and **no eval ever passed it into `run_task`**); the support matrix could parse quietly to zero limitations; a supersede dangled on the failure path. 58/58 fast, 16/16 invariant, $0.00, 31.9s. ADR-005 records all six and the 7 findings deliberately **not** fixed |
| M5 | B-Freeze (~day 3) | Coverage cells verified · cost/latency numbers · `docs/analysis.md` from report data · README rewrite · prompts curated · **eval-adversary held-out probe vs deployed URL (mandatory gate, raw results in analysis)** | analysis, collab, all | B-floor exit criteria in `docs/plans/completed/task1-b-level-plan.md` all green → **STOP, start Task 2** | **done** — 60/60 fast, 18/18 invariant, 1/1 live. First live domain (books.toscrape.com) + the observation-budget bug it found; M2–M4 **deployed at last** (the URL had served the M1 build for four milestones) and guards re-verified live; `docs/analysis.md`, README rewrite, prompts 004–007. Held-out probe run: **2/8 correct answers, 1/2 refusals, $0.0681, no wrong answer ever reported as success** — it found the `log into` scope bypass that let the agent touch a real credential field (fixed). B-floor: **5 of 6 criteria met**, criterion 2 (coverage) short on live breadth — see below |
| M6 | Live breadth & depth (A-phase, top-ranked — closes the one partial B-floor criterion) | ≥2 new live domains (candidates: Hacker News, Open Library) · ≥3 task classes exercised live · L3-difficulty cases · support-matrix rows per new domain | eval-depth (E2), T2 | criterion 2 fully met; every new case watched red first; live cases tagged `full` only | **next** |
| M7 | Verifier accuracy | ~20–30 hand-labeled runs → precision/recall in `docs/analysis.md` · answer-responsiveness check (probe #5: a page dump was rejected only on a whitespace technicality) · new trap cases | silent-failure (E3), analysis (E4), E5 | precision/recall from committed labels; responsiveness trap case red before the fix | planned |
| M8 | Mutation & hostility hardening | full mutation catalog · hostile live domain · live-drift snapshot replay (SHOULD) | mechanism-substance (E1), eval-depth (E2) | each new mutation red without relocation, green with; hostile results published raw | planned |
| M9 | Cost/model ablation | ≥2-model OpenRouter ablation · cost/latency tradeoff table · ADR for the default-model choice | analysis (E4), E5 tradeoffs | table from committed report runs, not estimates | planned |
| M10 | A-Freeze | analysis/README/support-matrix refresh · prompts curated · **second held-out probe vs deployed URL (mandatory gate, raw results committed)** | all, esp. E5 | A-exit criteria in `docs/plans/active/task1-a-level-plan.md` all green → owner decides submission/public | gate |
| — | Still backlog (not promoted) | adaptive locator learning · parallel eval runner · verifier-accuracy dashboard UI · visual fallback · per-IP rate limiting | — | each would need its own eval evidence | backlog |

## B-floor exit criteria — status at freeze

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Deployed frontend passes the smoke path (submit → live progress → inspect a failure) | **met** — walked end to end against the live URL; run `cd7121fc` streamed, failed loudly, screenshots served |
| 2 | Coverage: ~20–25 cases, 3 domains incl. both fixtures + ≥1 live, TC1–TC5, L1/L2/L4/L5 | **partial** — 61 cases, TC1–TC5 and L1/L2/L4/L5 all filled, 6 domains. But the live domain is **1 case, 1 task class**, and the probe showed live capability is thinner than the fixtures suggest. The thinnest cell, declared not hidden |
| 3 | Invariant 100%; trap-catch ≥90%; performance meets ADR-002 | **met** — 18/18 invariant, 6/6 traps (a floor, not accuracy), 32s ≪ 60s, $0.00 |
| 4 | Real self-correction (≥2 distinct families, strategy-switch traces); relocation passes all 3 mutations | **met** — 2 families, `recovery 3/3 verified (6 rungs)`, `mutation 4/4 passed, 2 by relocating` |
| 5 | Spend cap, per-run budgets, URL guard live on the public deployment | **met** — all guards re-verified against the live host, incl. cloud-metadata IP and traversal |
| 6 | Requirement matrix evidenced; support matrix eval-backed; unsupported list cites failing cases; cost/latency in analysis | **met** — every R/T row evidenced, 23 declared limitations each citing a case or a deployed run id |

**5 of 6 met; criterion 2 partial.** Per the freeze rule, Task 1 stops here and
Task 2 starts. Live breadth is the top item if Task 1 is ever reopened.

## Reopen — A-phase (2026-08-17)

Owner decision, recorded in `prompts/008-a-level-reopen.md`: **B-baseline is
accepted; the repo does not go public yet; Task 1 reopens for A-level before
submission.** This supersedes the freeze rule above by explicit instruction —
Task 2 start is deferred by the same decision, and the A-phase carries its own
hour guard (+12h default) so the reopen stays bounded. Milestones M6–M10 above
are the A-phase roadmap, ranked by reviewer-value ÷ effort against the two gaps
the freeze measured (live breadth, verifier accuracy). Per-feature loop is
unchanged: eval cases first, watch them red, then implement — **no
implementation has started under this reopen; planning docs only.**

A-plan: `docs/plans/active/task1-a-level-plan.md` ·
B-plan: `docs/plans/completed/task1-b-level-plan.md` ·
Methodology: `docs/evals/evaluation-methodology.md` ·
Architecture: `docs/architecture/task1-overview.md`
