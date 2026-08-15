# Architecture — Task 1 browser agent

Evaluation methodology (`docs/evals/evaluation-methodology.md`) was designed
first; this architecture exists to produce the evidence that methodology
measures. Scope tags: **MUST** / **SHOULD** / **BACKLOG**.

## Alternatives considered

| Criterion | A. LLM-per-step | **B. Deterministic execution + LLM evolving-prefix planning** | C. Full hierarchical multi-agent |
|---|---|---|---|
| Implementation complexity | low-medium | medium | high |
| Reliability | weak (every step is a model call that can drift) | strong (postcondition-verified steps) | strong but heavy |
| Latency | worst — 1 LLM call per action | 1 call + replans | planner+executor+verifier calls per phase |
| Cost | highest | lowest of the three | high |
| Inspectability | poor (reasoning buried in transcripts) | strong (typed steps, typed failures) | strong |
| Generalization | highest ceiling | high (semantic targets, no site code) | high |
| Ease of evaluation | hard (nondeterministic paths) | easy (deterministic components unit-gated offline) | medium |
| Silent-failure risk | high — model tempted to self-grade | low — postconditions + external verifier are structural | low |

**Chosen: B.** It maximizes inspectability × evaluability ÷ cost, and makes
silent-failure prevention *structural* (machine-checkable postconditions +
external OutcomeVerifier) rather than *behavioral* (prompting the model to be
careful). C's verifier idea is not discarded — it survives offline as the
OutcomeVerifier. A's generality ceiling is not needed at this scope.

### The evolving plan prefix (D7)

An upfront whole-task plan is wrong by construction for tasks where step N's
input doesn't exist until step N-1 executes (search-result quality, pagination,
disambiguation). Instead of a plan plus an "escape hatch" (a trapdoor that would
quietly turn the majority path into architecture A), **replanning is the normal
loop**: the planner emits typed steps; the executor runs them until a
postcondition is invalidated or the plan is exhausted; the planner then receives
the observation evidence and extends or revises the plan. **Replan rate is a
tracked metric** — if most tasks replan on most steps, the architecture claim is
re-examined openly in an ADR rather than papered over.

### Step schema (D9) — typed enough to verify, not a workflow DSL

```json
{
  "action": "click",
  "target": { "role": "button", "name": "Search", "text": null, "near": null },
  "value": null,
  "expected_state": { "url_contains": "/search" }
}
```

Extraction steps carry a separate small extraction schema. No preconditions
DSL, no retry policies in the plan, no nested workflows.

### Verification stance

Default runtime verification is deterministic (postconditions, identity
anchors, `/state` endpoints). LLM semantic verification, when enabled (verifier
layer 3, SHOULD), is **weak independent evidence, never ground truth**. Model
diversity between planner and verifier is an optional ablation [BACKLOG], not a
correctness assumption.

## Components

```
POST /tasks ─► Gateway (FastAPI) ─► run queue (semaphore, 1–2 browser contexts)
                    │                        │
             SSE progress ◄─── Trace store ◄─┤ per-step records + screenshots
                    │                        │
                    │            ┌───────────▼───────────┐
                    │            │  Agent loop            │
                    │            │  Planner (LLM/OpenRouter)
                    │            │  Resolver (deterministic)
                    │            │  Executor (Playwright)
                    │            │  Classifier (deterministic)
                    │            │  Recovery policy (ladders + budgets)
                    │            └───────────┬───────────┘
                    │                        │ evidence bundle
                    │            OutcomeVerifier (L1 predicates → L2 compare → [L3 LLM])
                    │                        │ verdict + cited evidence
                    └────────────────── run record (persisted)
```

- **Gateway** [MUST]: POST /tasks, GET run records, SSE with ~15s heartbeats;
  the task never runs inside the request handler — runs are persisted so a
  reload/reconnect recovers the trace. Serves the frontend and the fixture
  sites (`/fixtures/shop`, `/fixtures/forms`, with `?mut=` middleware).
- **Planner** [MUST]: LLM via OpenRouter (default `anthropic/claude-sonnet-4.5`,
  planning/replanning only). Receives task + condensed a11y observation;
  emits typed steps.
- **Resolver** [MUST]: SemanticTarget → ranked concrete locators from the
  accessibility snapshot (tiers per `docs/evals/failure-taxonomy.md`). Pure code.
- **Executor** [MUST]: Playwright; performs the action; captures pre/post
  observations + screenshot; checks `expected_state`.
- **Classifier** [MUST]: deterministic rules → one of 7 failure classes.
- **Recovery policy** [MUST]: class-conditional ladders (built for the
  checkpoint-chosen families), correction/replan/action/token budgets enforced
  in code.
- **Trace store** [MUST]: JSONL per run + screenshots. **One evidence pipeline**
  feeds the frontend, the OutcomeVerifier, and the EvalAuditor — no parallel
  truths.
- **OutcomeVerifier** [MUST L1–L2, SHOULD L3]: production code in `src/`, used
  at runtime and by the eval adapter. Never a Claude subagent.

### Trace record (specced before executor code — the executor emits this from
the first walking skeleton)

Per step: `{action, target, resolved_locator, tier, postcondition, postcondition_result,
screenshot_ref, failure_class?, ladder_rung?, retry_or_recovery?, tokens, ms}`.
Per run: task text, plan versions (each replan), verdict + cited evidence,
budgets spent. The trace viewer is the *demo* of self-correction — E1 evidence
lives here.

## Ops (trimmed to reviewer ROI)

[MUST → analysis(cost/scalability)]: per-run token/action budgets · global
spend cap = OpenRouter key limit + in-code counter · max 1–2 concurrent browser
contexts via a simple semaphore (no queue architecture) · URL guard: http/https
only, private/loopback ranges blocked (cheap, real SSRF-shaped risk on a public
endpoint) · instance ≥ 1–2 GB (one Chromium context ≈ 300–500 MB) · Playwright
Docker base image (~2 GB → slow deploy cycles → deploy spike in M1, kept alive).
Dropped from B [BACKLOG]: per-IP rate limiting, production abuse infrastructure.
Evals hit fixtures via loopback; the analysis says so when reporting latency.

## Frontend (thin, reviewer-facing) [MUST → deliverable]

Vanilla JS + SSE, no build step: submit box · run list · run detail = step
timeline (status, screenshot, failure class, strategy switch, retry-vs-recovery
flag) · final verdict + cited evidence · support-matrix page · latest eval
report rendered. The mutation demo is first-class UI: base PASS / ids-renamed
PASS / button-text-renamed PASS with the relocation trace visible.

## Subagent / skill layer (development-side, not runtime)

- Existing agents kept, none added: **eval-adversary** (+ pre-submission
  held-out probe of the deployed URL), **cold-reviewer** (+ retry-in-disguise,
  static-map-as-maintenance, knowledge-placement checks), **spec-drift**
  (unchanged). The OutcomeVerifier is production code, not an agent.
- Skills added: `browser-domain` (Playwright pitfalls, tiers, mutations,
  postconditions), `finish-task` (ship checklist). Skipped as duplicates:
  /run-eval (CLAUDE.md command), /execute-task (session-native), /create-spec +
  /plan-feature (plan mode + ADR-000 format), /analyze-failures (failure-triage
  skill).
