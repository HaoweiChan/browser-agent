# Assignment requirement matrix — Task 1

Source: `Whaleforce-AI-Coding-Test-EN.md` / `-ZH.md` (2026 update). Both files were
read in full; they are identical in substance — no divergence to reconcile.
Every requirement below cites its source section. Status legend:
`planned` (this phase) → `building` → `evidenced` (link to proof).

## Common deliverables (apply to every submitted task)

| ID | Requirement | Source | Evidence we expose | Status |
|----|-------------|--------|--------------------|--------|
| R1 | AI-assisted workflow: how AI was used to reason, implement, evaluate, iterate | Common req. 1 | `prompts/00N-*.md` correction chains; README "where AI helped" section | **evidenced** — `prompts/001-project-planning.md`…`prompts/006-cold-review-and-freeze.md`, each ending in an assumed→eval-said→corrected chain; README "Where AI helped, and where it was wrong" |
| R2 | Public Git repo; commit history reflects the actual development process | Common req. 2 | Incremental commits gated by pre-commit eval hook; no squashed mega-commits, no manufactured history | **evidenced** — 18 commits, 11 of them on this task; every gated by the pre-commit eval hook; no squashes, no manufactured history |
| R3 | Publicly accessible web frontend per task; not API-only; operable/inspectable in a browser | Common req. 3 | Deployed Zeabur URL (spike lands in M1, kept alive); frontend spec in `docs/architecture/task1-overview.md` | **evidenced** — https://whaleforce-browser-agent.zeabur.app/ serving the M4 UI; guards re-verified against the live host at M5 |
| R4 | Root `prompts/` folder with key prompts — reviewers will read them | Common req. 4 | Curated `prompts/00N-*.md` + auto-dumped `prompts/raw/`; convention in `prompts/README.md` | **evidenced** — `prompts/` with 6 curated records + raw session dumps |
| R5 | README: how to run, key design decisions, where AI helped | Common req. 5 | README rewritten at M5 (B-freeze) | **evidenced** — README rewritten at M5 |
| R6 | Analysis report: runtime performance, cost, scalability, correctness verification | Common req. 6 | `docs/analysis.md` written from committed eval-report data (real numbers, not estimates) | **evidenced** — `docs/analysis.md`, written from committed report data; states what is NOT measured |
| R7 | Public or self-created material only | Common req. 7 | Live domains chosen for legality/politeness; fixtures are self-created; rule restated in problem definition | **evidenced** — 5 self-authored fixtures + books.toscrape.com, a sandbox published for scraping practice; one page load per run, no crawling |

## Task 1 functional requirements

| ID | Requirement | Source | Evidence we expose | Status |
|----|-------------|--------|--------------------|--------|
| T1 | Accepts natural-language task descriptions | Task 1 ¶1 | Frontend submit box + POST /tasks; EN and ZH tasks in the eval set | **evidenced** — submit box + POST /tasks; 6 ZH cases alongside EN |
| T2 | Reliably executes across different sites | Task 1 ¶1 | Eval set spans fixtures + ≥1 live domain at B-floor (more at B-strong); per-domain results in support matrix | **partial** — 5 self-authored fixtures + **1 live domain, 1 task class, 1 case**. The thinnest B-floor cell; declared as such in `docs/analysis.md` §6 |
| T3 | Self-correction: diagnose cause on failure, try different strategies | Task 1 bullet 1 | Deterministic failure classifier; class-conditional recovery ladders; recovery metric counts ONLY classify→strategy-switch→verified-success traces (retries excluded) | **evidenced** — deterministic 7-class classifier (`diagnosis 8/8`); 2 ladders; `recovery 3/3 verified (6 rungs tried)` with retries excluded by construction |
| T4 | Self-maintenance: detect UI/selector changes, adjust locator strategies dynamically | Task 1 bullet 2 | SemanticTarget → tiered Resolver → stale detection → relocation; quantified by committed DOM-mutation suite (`?mut=`) | **evidenced, with the honest split** — `mutation 4/4 passed, 2 by relocating`; only 1 of 3 mutation types breaks a tier a plan stood on |
| T5 | Self-built eval set covering diverse domains and task types | Task 1 ¶2 | `evals/golden/` + `evals/adversarial/`; coverage cells in `docs/evals/evaluation-methodology.md`; case-count matrix with empty cells visible | **evidenced** — 61 cases; coverage cells in `docs/analysis.md` §6 with the empty L3 row shown |
| T6 | Frontend accepts tasks, shows execution progress/results, makes failures inspectable | Task 1 ¶2 | SSE live progress; per-step trace viewer (action, locator tier, postcondition, screenshot, failure class, strategy switch) | **evidenced** — SSE trace stream (every attempt, incl. superseded), per-step screenshots, three-valued postcondition rendering; ADR-004 |
| T7 | List supported websites + operations per site | Task 1 list bullet 1 | `docs/support-matrix.md` + frontend page: eval-backed, human-declared statuses with reasons | **evidenced** — `docs/support-matrix.md`, parsed and served to the frontend from the same file the README renders |
| T8 | List problematic/unreliable/unsupported sites and task types, with concrete examples | Task 1 list bullet 2 | Same matrix; `unreliable`/`unsupported` rows cite concrete failing cases; L5 refusal cases demonstrate the boundary live | **evidenced** — 23 declared limitations, each citing a case id; a case fails if a citation stops resolving or the section parses empty |
| T9 | Survives reviewer verification with unseen tasks against the deployed system | "We will verify with our own unseen tasks" | Pre-submission held-out probe: eval-adversary agent runs blind-written tasks against the deployed URL; raw results committed into the analysis | **evidenced, and it did not go well** — 10 blind tasks run against the live URL, raw table in `docs/analysis.md` §8a. 2/8 correct answers, 1/2 refusals. No run reported success with a wrong answer. It found a scope-guard bypass (`log into`) that let the agent touch a real credential field — now fixed with `l5-refuse-login-contracted` |

## Reviewer criteria → evidence map

These are the rubric cells the evidence budget in `docs/plans/completed/task1-b-level-plan.md`
scores against. Source: "What we'll look at" + "How We Evaluate" sections.

| ID | Rubric cell | What reviewers inspect | Our evidence |
|----|-------------|------------------------|--------------|
| E1 | `mechanism-substance` | Self-correction/self-maintenance substance — "not just try/except retries" | Trace records showing diagnosis → strategy switch; retry-vs-recovery flag in every trace; mutation suite where relocation passes what static locators fail |
| E2 | `eval-depth` | Depth of the evaluation set | Coverage cells (task classes × domains × difficulty × mutations); injected-failure cases; provenance on every golden case |
| E3 | `silent-failure` | Silent-failure prevention | OutcomeVerifier (executor never grades itself); identity anchors; ≥5 trap cases; INCONCLUSIVE ≠ pass; INV-0 lineage |
| E4 | `analysis` | Runtime perf, cost, scalability, correctness verification | `docs/analysis.md` from committed report data: latency p50/p95, tokens/$ per task (OpenRouter usage fields), concurrency model, verifier accuracy discussion incl. stated limitations |
| E5 | A-level markers | Layered/weighted tradeoffs, honest failure modes, high-quality AI collaboration | Architecture alternatives with tradeoff table; support matrix with declared `unreliable` rows; prompts/ correction chains (3 review passes on the plan itself) |

Cross-cutting rubric cells used by the plan but implied rather than named by the
assignment: `honesty` (E5 failure-mode honesty + T8) and `collab` (R1/R4 + E5),
`deliverable` (R2/R3/R5 + T6/T7).

## Explicit non-requirements (scope guards)

Things the assignment does NOT ask for, recorded so they don't creep in:
production-grade universal browser automation, authenticated flows, CAPTCHA
handling (also prohibited by policy), multi-user accounts, persistence beyond
run records, CI infrastructure, mobile frontends. The grading ladder rewards
eval depth and honesty, not feature count.
