# Graph Report - /Users/willy/Documents/browser-agent  (2026-08-17)

## Corpus Check
- 174 files · ~123,448 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 464 nodes · 639 edges · 43 communities (29 shown, 14 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 82 edges (avg confidence: 0.8)
- Token cost: 387,894 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Invariants & Result Contract|Invariants & Result Contract]]
- [[_COMMUNITY_Review Subagents & Domain Skills|Review Subagents & Domain Skills]]
- [[_COMMUNITY_Architecture & Milestone Ladder|Architecture & Milestone Ladder]]
- [[_COMMUNITY_Fixture Server & Mutations|Fixture Server & Mutations]]
- [[_COMMUNITY_Trace Contract Fields|Trace Contract Fields]]
- [[_COMMUNITY_Graphify Skill References|Graphify Skill References]]
- [[_COMMUNITY_Layered Verification & Traps|Layered Verification & Traps]]
- [[_COMMUNITY_Browser Eval Adapter|Browser Eval Adapter]]
- [[_COMMUNITY_Scope Guards & Held-Out Probe|Scope Guards & Held-Out Probe]]
- [[_COMMUNITY_Agent Loop|Agent Loop]]
- [[_COMMUNITY_Resolver & Declared Limitations|Resolver & Declared Limitations]]
- [[_COMMUNITY_Self-Maintenance Relocation|Self-Maintenance Relocation]]
- [[_COMMUNITY_Invariant Enforcement Checks|Invariant Enforcement Checks]]
- [[_COMMUNITY_Eval Runner|Eval Runner]]
- [[_COMMUNITY_CLI, Observe & Planner|CLI, Observe & Planner]]
- [[_COMMUNITY_Resolver & Verifier Modules|Resolver & Verifier Modules]]
- [[_COMMUNITY_Browser Domain Knowledge|Browser Domain Knowledge]]
- [[_COMMUNITY_Failure Classifier|Failure Classifier]]
- [[_COMMUNITY_Eval Adapter Case Runners|Eval Adapter Case Runners]]
- [[_COMMUNITY_Eval Gate & Enforcement Layers|Eval Gate & Enforcement Layers]]
- [[_COMMUNITY_Shop Fixture Scripts|Shop Fixture Scripts]]
- [[_COMMUNITY_Coverage Matrix & Scope|Coverage Matrix & Scope]]
- [[_COMMUNITY_A-Level Bar & Hour Guard|A-Level Bar & Hour Guard]]
- [[_COMMUNITY_URL Guard|URL Guard]]
- [[_COMMUNITY_Knowledge-Placement Boundary|Knowledge-Placement Boundary]]
- [[_COMMUNITY_Cost Budgets|Cost Budgets]]
- [[_COMMUNITY_Planner Step Schema|Planner Step Schema]]
- [[_COMMUNITY_Freeze Exit Criteria|Freeze Exit Criteria]]
- [[_COMMUNITY_Docs & Plans Layer|Docs & Plans Layer]]
- [[_COMMUNITY_Eval-First Scaffold|Eval-First Scaffold]]
- [[_COMMUNITY_Post-Edit Invariant Hook|Post-Edit Invariant Hook]]
- [[_COMMUNITY_Scalability Limits|Scalability Limits]]
- [[_COMMUNITY_Failure Class Taxonomy|Failure Class Taxonomy]]
- [[_COMMUNITY_Self-Correction Loop|Self-Correction Loop]]
- [[_COMMUNITY_Numeric Answer Matching|Numeric Answer Matching]]
- [[_COMMUNITY_Probe Blindness Protocol|Probe Blindness Protocol]]
- [[_COMMUNITY_Support Matrix Parsing|Support Matrix Parsing]]
- [[_COMMUNITY_Commit Discipline|Commit Discipline]]
- [[_COMMUNITY_Secrets Handling|Secrets Handling]]
- [[_COMMUNITY_Kept Metrics|Kept Metrics]]
- [[_COMMUNITY_CostModel Ablation|Cost/Model Ablation]]
- [[_COMMUNITY_M1 Walking Skeleton|M1 Walking Skeleton]]
- [[_COMMUNITY_Fast Suite Wall Clock|Fast Suite Wall Clock]]

## God Nodes (most connected - your core abstractions)
1. `run_task()` - 17 edges
2. `run_case()` - 15 edges
3. `graphify pipeline skill` - 11 edges
4. `_base_url()` - 10 edges
5. `ResolveError` - 9 edges
6. `finish-task ship checklist` - 9 edges
7. `Observed failure distribution (locate 4/12, act 4/12, silent 3/12, env 1/12)` - 9 edges
8. `TraceStep record` - 9 edges
9. `StepError` - 8 edges
10. `assemble_result()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `ponytail plugin (repo-wide)` --semantically_similar_to--> `Escalation Ladder`  [INFERRED] [semantically similar]
  AGENTS.md → .claude/skills/cost-discipline/SKILL.md
- `graphify Honesty Rules` --semantically_similar_to--> `Hard rule 4: no mocked results`  [INFERRED] [semantically similar]
  .claude/skills/graphify/SKILL.md → AGENTS.md
- `Retry vs recovery is a trace-level flag` --semantically_similar_to--> `superseded_by — a failed attempt stays in the trace`  [INFERRED] [semantically similar]
  docs/evals/failure-taxonomy.md → README.md
- `The deployed instance served the M1 build for four milestones` --semantically_similar_to--> `An author-written eval set is blind where the author was already looking`  [INFERRED] [semantically similar]
  docs/analysis.md → README.md
- `verifier-anchor-not-self-satisfied — an anchor equal to the answer certifies itself` --semantically_similar_to--> `No run reported success with a wrong answer (10/10)`  [INFERRED] [semantically similar]
  prompts/003-m2-eval-backbone.md → docs/analysis.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Milestone quality gates** — _claude_agents_cold_reviewer_coldreviewer, _claude_agents_eval_adversary_evaladversary, _claude_agents_spec_drift_specdrift, _claude_skills_finish_task_skill_finishtask [EXTRACTED 1.00]
- **Offline eval gate chain** — _claude_skills_eval_protocol_skill_suite_invariant, _claude_skills_eval_protocol_skill_suite_fast, _github_workflows_eval_eval_gate, _claude_skills_cost_discipline_skill_zero_paid_fast_suite, agents_per_feature_loop [EXTRACTED 1.00]
- **Locator resolution and mutation testing flow** — _claude_skills_browser_domain_skill_semantictarget, _claude_skills_browser_domain_skill_resolver, _claude_skills_browser_domain_skill_locator_tiers, _claude_skills_browser_domain_skill_mutation_catalog, _claude_skills_browser_domain_skill_fixture_map, _claude_skills_browser_domain_skill_expected_state [EXTRACTED 1.00]
- **The agent run pipeline — gateway to verified run record** — docs_architecture_task1_overview_gateway, docs_architecture_task1_overview_planner, docs_architecture_task1_overview_resolver, docs_architecture_task1_overview_executor, docs_architecture_task1_overview_classifier, docs_architecture_task1_overview_recovery_policy, docs_architecture_task1_overview_trace_store, docs_architecture_task1_overview_outcome_verifier [EXTRACTED 1.00]
- **Silent-failure prevention stack** — readme_inv_0, readme_inv_2, readme_inv_3, readme_outcome_verifier, docs_evals_evaluation_methodology_identity_anchors, docs_evals_evaluation_methodology_trap_set, docs_specs_001_task1_problem_definition_silent_semantic_failure [EXTRACTED 1.00]
- **Adversarial review and unfamiliar input as the only blind-spot movers** — readme_authors_blind_spot, readme_cold_reviewer, docs_analysis_held_out_probe_t9, prompts_006_cold_review_and_freeze_benign_twin, prompts_007_m5_freeze_and_held_out_probe_log_into_bypass, prompts_006_cold_review_and_freeze_observe_chrome_budget [EXTRACTED 1.00]
- **Invariants enforced at the single result assembler** — specs_000_invariants_inv_0, specs_000_invariants_inv_1, specs_000_invariants_inv_2, specs_000_invariants_inv_3, specs_001_browser_contract_assemble_result, specs_decisions_adr_004_reviewer_ui_gateway_failure_path_runresult [EXTRACTED 1.00]
- **The six M3/M4 cold-review defects** — specs_decisions_adr_005_cold_review_corrections_answers_match, specs_decisions_adr_005_cold_review_corrections_replan_noop_laundering, specs_decisions_adr_005_cold_review_corrections_recovery_label_strategy_change, specs_decisions_adr_005_cold_review_corrections_url_guard_enforcement, specs_decisions_adr_005_cold_review_corrections_matrix_parse_fails_loudly, specs_decisions_adr_005_cold_review_corrections_dangling_supersede [EXTRACTED 1.00]
- **Nimbus Shop fixture family (catalogue plus product pages)** — src_browser_fixtures_shop_catalogue, src_browser_fixtures_shop_lamp_std_aurora_desk_lamp, src_browser_fixtures_shop_lamp_pro_aurora_desk_lamp_pro, src_browser_fixtures_shop_clock_meridian_wall_clock, src_browser_fixtures_shop_rug_cobalt_floor_rug, src_browser_fixtures_forms_enquiry_form [EXTRACTED 1.00]

## Communities (43 total, 14 thin omitted)

### Community 0 - "Invariants & Result Contract"
Cohesion: 0.05
Nodes (48): Decorative invariant = drift, INV-0: never success with empty output, INV-1: exactly one failure class per non-success status, INV-2: the verifier outranks the executor, INV-3: budget exhaustion is a loud classified failure, Proven-red-before-trusted-green discipline, anchor — identity anchor on extract steps, assemble_result — the single result assembler (+40 more)

### Community 1 - "Review Subagents & Domain Skills"
Cohesion: 0.07
Nodes (45): cold-reviewer subagent, Retry-in-Disguise Anti-pattern, Silent Wrongness Failure Mode, Blindness Protocol, eval-adversary subagent, Pre-submission Deployed-URL Probe, Decorative Invariant, Drift Severity Ladder (+37 more)

### Community 2 - "Architecture & Milestone Ladder"
Cohesion: 0.07
Nodes (30): Runtime performance — bimodal p50/p95 from the settle loop, Architecture B — deterministic execution + LLM evolving-prefix planning, Evolving plan prefix (D7) — replanning as the normal loop, Reviewer-facing frontend (vanilla JS + SSE), Gateway (FastAPI, SSE, semaphore), Recovery policy (class-conditional ladders + budgets), Grade ladder C / B / A operationalized, Thresholds set post-baseline via ADR-002 (+22 more)

### Community 3 - "Fixture Server & Mutations"
Cohesion: 0.08
Nodes (20): BaseModel, Request, apply_mutation(), Mutation catalog — deterministic HTML transforms selected by `?mut=<name>`.  Con, Unknown names are a loud error — a silently ignored `?mut=` would turn     an L4, fixture(), forms_state(), forms_submit() (+12 more)

### Community 4 - "Trace Contract Fields"
Cohesion: 0.10
Nodes (27): page_changed — did the action move the page, postcondition_ok (three-valued), SSE progress stream (step / done events), resolved.tier locator ladder, retry_or_recovery labelling rule, Screenshot route pattern-matching (run dir not browsable), superseded_by and the supersede exemption, target.index k-th match selector (+19 more)

### Community 5 - "Graphify Skill References"
Cohesion: 0.11
Nodes (26): graphify add + watch reference, Watcher debounce, graphify exports reference, graphify MCP stdio server, Discrete confidence rubric, Node ID format rule, Extraction subagent prompt spec, graphify GitHub clone and merge reference (+18 more)

### Community 6 - "Layered Verification & Traps"
Cohesion: 0.08
Nodes (25): eval_adapter.run_case contract, No run reported success with a wrong answer (10/10), Trap cases are a detection floor, not verifier accuracy, Verification layers L1/L2/L3 as implemented, Executor (Playwright), OutcomeVerifier component (production code, never a subagent), Trace record schema (specced before executor code), Trace store — one evidence pipeline, no parallel truths (+17 more)

### Community 7 - "Browser Eval Adapter"
Cohesion: 0.20
Nodes (18): _base_url(), _check_supersede_dangling(), _get_json(), _post(), Eval adapter for task "browser" — the EvalAuditor (contract: evals/run.py).  Jud, Field-by-field conformance to specs/001-browser-contract.md.      The contract i, Start the gateway app on a free loopback port, once per process., The progress stream must show the run that happened, not a tidier one.      Grad (+10 more)

### Community 8 - "Scope Guards & Held-Out Probe"
Cohesion: 0.12
Nodes (18): Every new failure becomes a case, watched red first, Per-feature loop (eval-first development cycle), The deployed instance served the M1 build for four milestones, T9 held-out probe — 10 blind tasks on the deployed URL, With no start URL the planner plans blind, Scope-guard bypass — 'log into' has no word boundary, M10 A-Freeze (second held-out probe as gate), Explicit non-requirements (scope guards) (+10 more)

### Community 9 - "Agent Loop"
Cohesion: 0.15
Nodes (16): budget_stop(), check_state(), evidence_window(), The agent loop: screen -> plan -> execute step-by-step -> assemble result.  Ever, True / False / None, where None means "nothing was asserted".      None is not T, Bounded page-text evidence that still contains the extracted value.      A flat, Run-level resource check. Non-None means: stop now, loudly, classified.      Lad, run_task() (+8 more)

### Community 10 - "Resolver & Declared Limitations"
Cohesion: 0.12
Nodes (16): The complete not-measured list, Resolver (SemanticTarget to ranked locators, pure code), Recovery rate — retries excluded by construction, Locator tier order and tradeoffs, Retry vs recovery is a trace-level flag, SemanticTarget{role, name, text?, near?}, E1 mechanism-substance rubric cell, T7 list supported websites + operations (+8 more)

### Community 11 - "Self-Maintenance Relocation"
Cohesion: 0.13
Nodes (15): Reliability numbers with denominators printed, Mutation catalog (?mut=) as self-maintenance ground truth, Locator cache per (site, target) so drift is detectable, Relocation loop (self-maintenance), Stale locator detection, A third recovery family explicitly refused, M8 Mutation & hostility, T4 self-maintenance requirement (+7 more)

### Community 12 - "Invariant Enforcement Checks"
Cohesion: 0.14
Nodes (15): assemble_result(), _check_inv0(), _check_inv1(), _check_inv2(), _check_inv3(), INV-2: a FAIL/INCONCLUSIVE verdict can never be reported as success., INV-3: budget exhaustion is a loud classified failure, never a quiet stop., INV-0: a completed run with empty output must not report success. (+7 more)

### Community 13 - "Eval Runner"
Cohesion: 0.23
Nodes (12): aggregate(), load_cases(), main(), pctl(), Nearest-rank percentile — no numpy for a list of a few dozen floats., Sum whatever numeric keys the adapters put under `field`. The runner     stays t, Cost and latency roll-up. Adapters report spend under `budgets`., run_case() (+4 more)

### Community 14 - "CLI, Observe & Planner"
Cohesion: 0.24
Nodes (9): main(), CLI entry: python3 -m src.browser.cli "task" [--url ...] [--model ...]  Uses the, Condensed page observation for the planner (docs/architecture, D7).  The planner, render(), live_planner(), parse_plan(), PlanError, Planner: NL task -> typed steps (docs/architecture/task1-overview.md, D9).  A pl (+1 more)

### Community 15 - "Resolver & Verifier Modules"
Cohesion: 0.29
Nodes (9): SemanticTarget -> Playwright locator, tier by tier, plus relocation.  Tiers (doc, answers_match(), _clean(), normalize(), _num_parts(), OutcomeVerifier — layered outcome verification (docs/evals/evaluation-methodolog, Numbers compare structurally, not as normalized strings.      A single canonical, `(Decimal, currency|None, unit|None)`, or None when s is not a number.      Sign (+1 more)

### Community 16 - "Browser Domain Knowledge"
Cohesion: 0.22
Nodes (10): Knowledge-Placement Violation, Addressable ARIA Roles, browser-domain skill, Fixture Map, Locator Tier Ladder, Mutation Catalog, Resolver candidate ranking, SemanticTarget (+2 more)

### Community 17 - "Failure Classifier"
Cohesion: 0.25
Nodes (8): BaseException, Exception, classify(), A step failure whose class the executor already knows — an empty     extraction,, Failed step -> exactly one taxonomy class (docs/evals/failure-taxonomy.md)., StepError, Diagnosis ground truth: (action, error) -> exactly one taxonomy class.      The, _run_classify_case()

### Community 18 - "Eval Adapter Case Runners"
Cohesion: 0.22
Nodes (9): Relocation rungs: same intent, different tier, never the tier that just     fail, Mutation catalog integrity: each transform must break its own tier and     leave, Direct probes of the grader itself. The grader is the only component     with no, Ordinary maintenance of the matrix doc must break loudly, not quietly.      Each, run_case(), _run_matrix_drift_case(), _run_mutation_case(), _run_relocate_case() (+1 more)

### Community 19 - "Eval Gate & Enforcement Layers"
Cohesion: 0.25
Nodes (8): Never hand-edit .eval-baseline.json, Eval suites (invariant / fast / full / all), No mocked results — fail loudly, Pre-commit eval gate, Planner is stubbed in every suite — the central caveat, Suite definitions (invariant / fast / full), Enforcement loop — hooks are law, advice doesn't bind, Four layers — facts / knowledge / execution / enforcement

### Community 20 - "Shop Fixture Scripts"
Cohesion: 0.32
Nodes (8): display:none removes rows from the a11y tree, doSearch, Deliberately id-free script wiring, list (catalogue accessor), rows (row accessor), sortByPrice, summary (result summary accessor), Catalogue deliberately not in price order

### Community 21 - "Coverage Matrix & Scope"
Cohesion: 0.47
Nodes (6): Coverage matrix — 61 cases, empty cells shown, Coverage cells, not raw case counts, Difficulty levels L1–L5, B-plan scope registry (MUST / SHOULD / BACKLOG), Task taxonomy TC1–TC5, Review pass 2 — human scope rejection (A-minus wearing a B label)

### Community 22 - "A-Level Bar & Hour Guard"
Cohesion: 0.40
Nodes (6): What A-level means here (two measured gaps), A-phase hour guard (+12h from reopen), Freeze rule + 20–24h hour guard, E5 A-level markers rubric cell, Owner reopen directive — B accepted, reach A before going public, Backlog re-ranked on freeze data rather than M5-era order

### Community 23 - "URL Guard"
Cohesion: 0.67
Nodes (4): Deployment verified against the live URL at M5, URL guard (http/https only, private ranges blocked), url-guard-literal-ips — decimal/hex IP spellings bypassed the guard, The URL guard was never passed into run_task by any eval

### Community 24 - "Knowledge-Placement Boundary"
Cohesion: 0.67
Nodes (3): No site-specific knowledge in the execution policy, What 'generalized' means (knowledge-placement boundary), Semantic targets, never CSS selectors

### Community 25 - "Cost Budgets"
Cohesion: 0.67
Nodes (3): Budget controls that bound cost, Measured cost — two observed deployed runs, Budgets (corrections, replans, actions, tokens)

### Community 26 - "Planner Step Schema"
Cohesion: 0.67
Nodes (3): Planner (LLM via OpenRouter), Step schema (D9) — typed enough to verify, Action vocabulary

### Community 27 - "Freeze Exit Criteria"
Cohesion: 0.67
Nodes (3): A-exit criteria (the A-freeze line), B-floor exit criteria, M5 B-Freeze

### Community 28 - "Docs & Plans Layer"
Cohesion: 0.67
Nodes (3): No tasks.md / plan files (session-native tracking), Completed plans exempt from spec-drift audit, docs/ planning layer as reviewer deliverable

## Knowledge Gaps
- **70 isolated node(s):** `post-edit-invariant.sh script`, `Addressable ARIA Roles`, `expected_state postconditions`, `Hour guard tally`, `groundwork (eval-first scaffold)` (+65 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Are the 2 inferred relationships involving `ResolveError` (e.g. with `classify()` and `StepError`) actually correct?**
  _`ResolveError` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `post-edit-invariant.sh script`, `Nearest-rank percentile — no numpy for a list of a few dozen floats.`, `Sum whatever numeric keys the adapters put under `field`. The runner     stays t` to the rest of the system?**
  _163 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Invariants & Result Contract` be split into smaller, more focused modules?**
  _Cohesion score 0.0549645390070922 - nodes in this community are weakly interconnected._
- **Should `Review Subagents & Domain Skills` be split into smaller, more focused modules?**
  _Cohesion score 0.06666666666666667 - nodes in this community are weakly interconnected._
- **Should `Architecture & Milestone Ladder` be split into smaller, more focused modules?**
  _Cohesion score 0.07126436781609195 - nodes in this community are weakly interconnected._
- **Should `Fixture Server & Mutations` be split into smaller, more focused modules?**
  _Cohesion score 0.07881773399014778 - nodes in this community are weakly interconnected._
- **Should `Trace Contract Fields` be split into smaller, more focused modules?**
  _Cohesion score 0.10256410256410256 - nodes in this community are weakly interconnected._