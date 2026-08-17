# Graph Report - /Users/willy/Documents/browser-agent  (2026-08-17)

## Corpus Check
- 54 files · ~192,960 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 473 nodes · 620 edges · 53 communities (21 shown, 32 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 80 edges (avg confidence: 0.74)
- Token cost: 157,646 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Loop & Failure Classes|Agent Loop & Failure Classes]]
- [[_COMMUNITY_Eval Suites & Domain Skill|Eval Suites & Domain Skill]]
- [[_COMMUNITY_Locator Tiers & Self-Maintenance|Locator Tiers & Self-Maintenance]]
- [[_COMMUNITY_Working Rules & Deployment|Working Rules & Deployment]]
- [[_COMMUNITY_Result Contract & Invariant Checks|Result Contract & Invariant Checks]]
- [[_COMMUNITY_Review Subagents & Fillability|Review Subagents & Fillability]]
- [[_COMMUNITY_Invariants as Enforcement|Invariants as Enforcement]]
- [[_COMMUNITY_Cost Discipline & Graphify Refs|Cost Discipline & Graphify Refs]]
- [[_COMMUNITY_Verification & Trace Store|Verification & Trace Store]]
- [[_COMMUNITY_Architecture & Milestones|Architecture & Milestones]]
- [[_COMMUNITY_Eval Runner|Eval Runner]]
- [[_COMMUNITY_OutcomeVerifier Module|OutcomeVerifier Module]]
- [[_COMMUNITY_Mutation Catalog Code|Mutation Catalog Code]]
- [[_COMMUNITY_Fixture Mutation Ground Truth|Fixture Mutation Ground Truth]]
- [[_COMMUNITY_Self-Maintenance Metrics|Self-Maintenance Metrics]]
- [[_COMMUNITY_Coverage & Scope Registry|Coverage & Scope Registry]]
- [[_COMMUNITY_Baseline Thresholds|Baseline Thresholds]]
- [[_COMMUNITY_Page Observation|Page Observation]]
- [[_COMMUNITY_Gateway & Reviewer UI|Gateway & Reviewer UI]]
- [[_COMMUNITY_Planner & Step Schema|Planner & Step Schema]]
- [[_COMMUNITY_URL Guard|URL Guard]]
- [[_COMMUNITY_Docs & Plans Layer|Docs & Plans Layer]]
- [[_COMMUNITY_Eval-Set-Is-Spec Rule|Eval-Set-Is-Spec Rule]]
- [[_COMMUNITY_Post-Edit Invariant Hook|Post-Edit Invariant Hook]]
- [[_COMMUNITY_Silent-Failure Measurement|Silent-Failure Measurement]]
- [[_COMMUNITY_B-Freeze Criteria|B-Freeze Criteria]]
- [[_COMMUNITY_Pre-Plan Observation Budget|Pre-Plan Observation Budget]]
- [[_COMMUNITY_Numeric Answer Matching|Numeric Answer Matching]]
- [[_COMMUNITY_Stream Honesty|Stream Honesty]]
- [[_COMMUNITY_Support Matrix Parsing|Support Matrix Parsing]]
- [[_COMMUNITY_Forms Fixture Ground Truth|Forms Fixture Ground Truth]]
- [[_COMMUNITY_Deterministic Classifier|Deterministic Classifier]]
- [[_COMMUNITY_Recovery Policy|Recovery Policy]]
- [[_COMMUNITY_Resolver Component|Resolver Component]]
- [[_COMMUNITY_Difficulty Levels|Difficulty Levels]]
- [[_COMMUNITY_Kept Metrics|Kept Metrics]]
- [[_COMMUNITY_M1 Walking Skeleton|M1 Walking Skeleton]]
- [[_COMMUNITY_E1 Mechanism Rubric|E1 Mechanism Rubric]]
- [[_COMMUNITY_E4 Analysis Rubric|E4 Analysis Rubric]]
- [[_COMMUNITY_E5 A-Level Rubric|E5 A-Level Rubric]]
- [[_COMMUNITY_Knowledge-Placement Boundary|Knowledge-Placement Boundary]]
- [[_COMMUNITY_Initial Domain Table|Initial Domain Table]]
- [[_COMMUNITY_Anchor Self-Satisfaction|Anchor Self-Satisfaction]]
- [[_COMMUNITY_Name-Prohibited Roles|Name-Prohibited Roles]]
- [[_COMMUNITY_Ladder Budget Classing|Ladder Budget Classing]]
- [[_COMMUNITY_Deploy-Drift Lesson|Deploy-Drift Lesson]]
- [[_COMMUNITY_Over-Refusal Declared|Over-Refusal Declared]]
- [[_COMMUNITY_Backlog Re-Ranking|Backlog Re-Ranking]]
- [[_COMMUNITY_Verifier Outranks Executor|Verifier Outranks Executor]]
- [[_COMMUNITY_Milestone-Only TODO|Milestone-Only TODO]]
- [[_COMMUNITY_Fast Suite Wall Clock|Fast Suite Wall Clock]]
- [[_COMMUNITY_Gateway Failure Contract|Gateway Failure Contract]]
- [[_COMMUNITY_Three-Fact Answer Compare|Three-Fact Answer Compare]]

## God Nodes (most connected - your core abstractions)
1. `Declared limitations (each citing a case id)` - 13 edges
2. `run_task()` - 12 edges
3. `graphify pipeline skill` - 10 edges
4. `_base_url()` - 10 edges
5. `_run_fixture_case()` - 9 edges
6. `ResolveError` - 9 edges
7. `OutcomeVerifier - the executor never grades itself` - 9 edges
8. `Task 1 A-level plan` - 9 edges
9. `StepError` - 8 edges
10. `assemble_result()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Eight hard rules (AGENTS.md)` --semantically_similar_to--> `Eight hard rules`  [INFERRED] [semantically similar]
  AGENTS.md → CLAUDE.md
- `Locator cache + drift events (designed, not built)` --semantically_similar_to--> `partial status (specced, no code path produces it)`  [INFERRED] [semantically similar]
  docs/evals/failure-taxonomy.md → specs/001-browser-contract.md
- `Coverage cells, not raw case counts` --semantically_similar_to--> `Review pass 2 — human scope rejection (A-minus wearing a B label)`  [INFERRED] [semantically similar]
  docs/evals/evaluation-methodology.md → prompts/001-project-planning.md
- `Project working rules (AGENTS.md)` --semantically_similar_to--> `Project working rules (CLAUDE.md)`  [INFERRED] [semantically similar]
  AGENTS.md → CLAUDE.md
- `Eval suite tags: invariant/fast/live/full/all` --semantically_similar_to--> `Eval suite commands and tag semantics`  [INFERRED] [semantically similar]
  AGENTS.md → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **near: proximity mechanism and the fixtures that hold its defects shut** — _claude_skills_browser_domain_skill_near_proximity, specs_001_browser_contract_near, specs_decisions_adr_006_m6_live_breadth_decision1_near_structural, src_browser_fixtures_shop_order_order_page, src_browser_fixtures_shop_lamp_spec_spec_page, prompts_009_m6_live_breadth_assumption_correction_chains [EXTRACTED 1.00]
- **Eval-first enforcement loop (facts, suites, hooks, subagents)** — claude_hard_rules, claude_eval_suites, claude_per_feature_loop, readme_enforcement_loop, readme_four_layer_architecture, readme_cold_reviewer [EXTRACTED 1.00]
- **Honest coverage reporting: cases vs verified, x/y with denominators** — docs_support_matrix_report_assisted_human_declared, docs_analysis_coverage, specs_decisions_adr_006_m6_live_breadth_decision5_numbers_license, tasks_todo_b_floor_exit_criteria, docs_analysis_trap_cases_floor [EXTRACTED 1.00]
- **Milestone quality gates** — _claude_agents_cold_reviewer_coldreviewer, _claude_agents_eval_adversary_evaladversary, _claude_agents_spec_drift_specdrift, _claude_skills_finish_task_skill_finishtask [EXTRACTED 1.00]
- **Offline eval gate chain** — _claude_skills_eval_protocol_skill_suite_invariant, _claude_skills_eval_protocol_skill_suite_fast, _github_workflows_eval_eval_gate, _claude_skills_cost_discipline_skill_zero_paid_fast_suite, agents_per_feature_loop [EXTRACTED 1.00]
- **The agent run pipeline — gateway to verified run record** — docs_architecture_task1_overview_gateway, docs_architecture_task1_overview_planner, docs_architecture_task1_overview_resolver, docs_architecture_task1_overview_executor, docs_architecture_task1_overview_classifier, docs_architecture_task1_overview_recovery_policy, docs_architecture_task1_overview_trace_store, docs_architecture_task1_overview_outcome_verifier [EXTRACTED 1.00]
- **Invariants enforced at the single result assembler** — specs_000_invariants_inv_0, specs_000_invariants_inv_1, specs_000_invariants_inv_2, specs_000_invariants_inv_3, specs_001_browser_contract_assemble_result, specs_decisions_adr_004_reviewer_ui_gateway_failure_path_runresult [EXTRACTED 1.00]
- **The six M3/M4 cold-review defects** — specs_decisions_adr_005_cold_review_corrections_answers_match, specs_decisions_adr_005_cold_review_corrections_replan_noop_laundering, specs_decisions_adr_005_cold_review_corrections_recovery_label_strategy_change, specs_decisions_adr_005_cold_review_corrections_url_guard_enforcement, specs_decisions_adr_005_cold_review_corrections_matrix_parse_fails_loudly, specs_decisions_adr_005_cold_review_corrections_dangling_supersede [EXTRACTED 1.00]
- **Nimbus Shop fixture family (catalogue plus product pages)** — src_browser_fixtures_shop_catalogue, src_browser_fixtures_shop_lamp_std_aurora_desk_lamp, src_browser_fixtures_shop_lamp_pro_aurora_desk_lamp_pro, src_browser_fixtures_shop_clock_meridian_wall_clock, src_browser_fixtures_shop_rug_cobalt_floor_rug, src_browser_fixtures_forms_enquiry_form [EXTRACTED 1.00]

## Communities (53 total, 32 thin omitted)

### Community 0 - "Agent Loop & Failure Classes"
Cohesion: 0.05
Nodes (64): BaseException, Exception, budget_stop(), check_state(), classify(), evidence_window(), The agent loop: screen -> plan -> execute step-by-step -> assemble result.  Ever, True / False / None, where None means "nothing was asserted".      None is not T (+56 more)

### Community 1 - "Eval Suites & Domain Skill"
Cohesion: 0.06
Nodes (41): Browser-agent domain knowledge (skill), Eval suite tags: invariant/fast/live/full/all, Adding a task (eval_adapter contract), Eval suite commands and tag semantics, Recovery rate — retries excluded by construction, Suite definitions (invariant / fast / full), Seven top-level failure classes, Retry vs recovery is a trace-level flag (+33 more)

### Community 2 - "Locator Tiers & Self-Maintenance"
Cohesion: 0.08
Nodes (40): Addressable ARIA roles (Playwright 1.49), Locator tiers (resolver order), near: document-order proximity, agent.PAGE_TEXT_KEEP evidence window (2000 chars), Per-feature loop (plan to commit), Rule 6 - no site-specific knowledge in execution policy, The eval set's own bias, measured, Scalability limits (concurrency one, in-memory runs) (+32 more)

### Community 3 - "Working Rules & Deployment"
Cohesion: 0.06
Nodes (39): OpenRouter planner calls + budget counter, Eight hard rules (AGENTS.md), Project working rules (AGENTS.md), The eval set IS the spec (CLAUDE.md), Eight hard rules, Project working rules (CLAUDE.md), Repo layout contract, Rule 8 - secrets are environment variables only (+31 more)

### Community 4 - "Result Contract & Invariant Checks"
Cohesion: 0.06
Nodes (32): BaseModel, Request, assemble_result(), _check_inv0(), _check_inv1(), _check_inv2(), INV-0: a completed run with empty output must not report success., INV-1: every non-success status carries exactly one known class. (+24 more)

### Community 5 - "Review Subagents & Fillability"
Cohesion: 0.09
Nodes (33): cold-reviewer subagent, Knowledge-Placement Violation, Retry-in-Disguise Anti-pattern, Silent Wrongness Failure Mode, Blindness Protocol, eval-adversary subagent, Pre-submission Deployed-URL Probe, Decorative Invariant (+25 more)

### Community 6 - "Invariants as Enforcement"
Cohesion: 0.07
Nodes (32): Decorative invariant = drift, INV-0: never success with empty output, INV-1: exactly one failure class per non-success status, INV-3: budget exhaustion is a loud classified failure, Proven-red-before-trusted-green discipline, The eval set is the spec, Hooks are law, CLAUDE.md is advice, specs/ holds three artifact kinds only (+24 more)

### Community 7 - "Cost Discipline & Graphify Refs"
Cohesion: 0.10
Nodes (29): Per-run Budget Counter, cost-discipline skill, Escalation Ladder, External Call Cache, graphify add + watch reference, Watcher debounce, graphify exports reference, graphify MCP stdio server (+21 more)

### Community 8 - "Verification & Trace Store"
Cohesion: 0.10
Nodes (22): Postcondition patterns (expected_state), Runtime performance (bimodal latency), Executor (Playwright), OutcomeVerifier component (production code, never a subagent), Trace record schema (specced before executor code), Trace store — one evidence pipeline, no parallel truths, Identity anchors — the task's entity must appear in evidence, Layered verification L1/L2/L3 (+14 more)

### Community 9 - "Architecture & Milestones"
Cohesion: 0.10
Nodes (22): Coverage table (76 cases, task classes, domains), What is not measured - the complete list, Architecture B — deterministic execution + LLM evolving-prefix planning, Evolving plan prefix (D7) — replanning as the normal loop, Grade ladder C / B / A operationalized, Thresholds set post-baseline via ADR-002, Family 1 — locate → relocation, Family 2 — act → postcondition invalidation → replan (+14 more)

### Community 10 - "Eval Runner"
Cohesion: 0.23
Nodes (12): aggregate(), load_cases(), main(), pctl(), Nearest-rank percentile — no numpy for a list of a few dozen floats., Sum whatever numeric keys the adapters put under `field`. The runner     stays t, Cost and latency roll-up. Adapters report spend under `budgets`., run_case() (+4 more)

### Community 11 - "OutcomeVerifier Module"
Cohesion: 0.29
Nodes (10): answers_match(), _clean(), normalize(), _num_parts(), OutcomeVerifier — layered outcome verification (docs/evals/evaluation-methodolog, Numbers compare structurally, not as normalized strings.      A single canonical, Return {"verdict": PASS|FAIL|INCONCLUSIVE, "layer", "checks", "reason"}.      `e, `(Decimal, currency|None, unit|None)`, or None when s is not a number.      Sign (+2 more)

### Community 12 - "Mutation Catalog Code"
Cohesion: 0.29
Nodes (3): apply_mutation(), Mutation catalog — deterministic HTML transforms selected by `?mut=<name>`.  Con, Unknown names are a loud error — a silently ignored `?mut=` would turn     an L4

### Community 13 - "Fixture Mutation Ground Truth"
Cohesion: 0.50
Nodes (5): Fixture map, A fixture must survive its own mutations, ?mut= deterministic HTML mutations, Quantified mutation test (one tier at a time), DOM mutations as self-maintenance ground truth

### Community 14 - "Self-Maintenance Metrics"
Cohesion: 0.40
Nodes (5): Mutation catalog (?mut=) as self-maintenance ground truth, A third recovery family explicitly refused, T4 self-maintenance requirement, A fixture must survive its own mutations, mutation_recovered counted separately from mutation_passed

### Community 15 - "Coverage & Scope Registry"
Cohesion: 0.67
Nodes (4): Coverage cells, not raw case counts, B-plan scope registry (MUST / SHOULD / BACKLOG), Task taxonomy TC1–TC5, Review pass 2 — human scope rejection (A-minus wearing a B label)

### Community 16 - "Baseline Thresholds"
Cohesion: 0.50
Nodes (4): fast suite ≥ 1.000 gated by baseline file, M2 observed baseline (41 cases, fast suite), fast suite cost = $0.00 exactly (boundary, not budget), Trap-catch ≥ 90% as a floor, not accuracy

### Community 18 - "Gateway & Reviewer UI"
Cohesion: 0.67
Nodes (3): Reviewer-facing frontend (vanilla JS + SSE), Gateway (FastAPI, SSE, semaphore), M4 Reviewer UI

### Community 19 - "Planner & Step Schema"
Cohesion: 0.67
Nodes (3): Planner (LLM via OpenRouter), Step schema (D9) — typed enough to verify, Action vocabulary

### Community 20 - "URL Guard"
Cohesion: 1.00
Nodes (3): URL guard (http/https only, private ranges blocked), url-guard-literal-ips — decimal/hex IP spellings bypassed the guard, The URL guard was never passed into run_task by any eval

### Community 21 - "Docs & Plans Layer"
Cohesion: 0.67
Nodes (3): No tasks.md / plan files (session-native tracking), Completed plans exempt from spec-drift audit, docs/ planning layer as reviewer deliverable

## Knowledge Gaps
- **78 isolated node(s):** `post-edit-invariant.sh script`, `Per-run Budget Counter`, `Hour guard tally`, `Gateway (FastAPI, SSE, semaphore)`, `Planner (LLM via OpenRouter)` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Declared limitations (each citing a case id)` connect `Locator Tiers & Self-Maintenance` to `Architecture & Milestones`, `Working Rules & Deployment`, `Review Subagents & Fillability`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `Support matrix - Task 1` connect `Architecture & Milestones` to `Verification & Trace Store`, `Locator Tiers & Self-Maintenance`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `browser-agent (README)` connect `Working Rules & Deployment` to `Verification & Trace Store`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `post-edit-invariant.sh script`, `Nearest-rank percentile — no numpy for a list of a few dozen floats.`, `Sum whatever numeric keys the adapters put under `field`. The runner     stays t` to the rest of the system?**
  _169 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agent Loop & Failure Classes` be split into smaller, more focused modules?**
  _Cohesion score 0.0528169014084507 - nodes in this community are weakly interconnected._
- **Should `Eval Suites & Domain Skill` be split into smaller, more focused modules?**
  _Cohesion score 0.05975609756097561 - nodes in this community are weakly interconnected._
- **Should `Locator Tiers & Self-Maintenance` be split into smaller, more focused modules?**
  _Cohesion score 0.07692307692307693 - nodes in this community are weakly interconnected._