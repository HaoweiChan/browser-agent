# Evaluation methodology — Task 1

Evaluation is designed before architecture: these definitions drive what gets
built. Scope tags: **MUST** (B-floor) / **SHOULD** (B-strong) / **BACKLOG**.

## Grade ladder, operationalized

- **C** (happy path): golden L1–L2 pass on friendly domains; no failure story.
- **B** (our floor): four complete stories — normal execution, multi-step,
  controlled breakage recovered, explicit honest failure — plus deployed
  frontend, coverage cells filled, real cost/latency numbers.
- **A** (backlog, only after freeze): verifier accuracy quantified, hostile
  domain, cost ablations, expanded held-out evidence.

## Coverage cells, not raw counts

Reviewers don't credit 45 cases over 30; they credit coverage. The gates:

| Cell | Minimum | Tag |
|------|---------|-----|
| Every task class (TC1–TC5) | ≥ 2 base cases | MUST |
| Every failure class we claim to recover from | ≥ 1 injected case | MUST |
| Every locator tier we claim | ≥ 1 mutation that breaks the previous tier | MUST |
| Silent-failure traps (near-miss entity, absent answer, planted wrong outcome) | ≥ 5 | MUST |
| Explicit refusal (L5) cases | ≥ 3 | MUST |
| ZH-language sample | ≥ 1 per TC | MUST |

B-floor lands around 20–25 cases across 3 domains (both fixtures + ≥1 live);
B-strong grows to 35–45 across 4+ domains including the hostile one [SHOULD].
The analysis report shows the actual case-count matrix **with empty cells
visible** — honesty about gaps is itself graded material.

## Difficulty levels

| Level | Definition | Tag |
|-------|-----------|-----|
| L1 | direct deterministic interaction | MUST |
| L2 | multi-step workflow | MUST |
| L3 | ambiguity / dynamic state | SHOULD — easily becomes fuzzy testcase engineering; does not block B-freeze |
| L4 | perturbed UI/locator (fixtures only — controlled) | MUST — the assignment's named self-maintenance evidence |
| L5 | expected failure / unsupported | MUST |

## Metrics

Kept metrics, each with definition / measurement / ground truth / limitations:

| Metric | Definition | Measured how | Ground truth | Limitations |
|--------|-----------|--------------|--------------|-------------|
| E2E verified success rate | verifier-confirmed goal satisfaction | EvalAuditor over run evidence | layered OutcomeVerifier | inherits verifier accuracy |
| Semantic accuracy (golden) | normalized match of `answer` vs `expect` | string/number normalization + compare | hand-labeled `expect` with `provenance`; API cross-check where available | normalization rules can hide near-misses — traps cover this |
| **Silent-failure rate** | claimed success contradicted by ground truth | trap cases + disagreement log | planted traps, API cross-checks | traps sample *imaginable* wrongness — stated as a floor |
| Recovery rate | recovered after a classified failure | trace must show classify → strategy-switch → verified success; **retries excluded by construction** | injected failures in fixtures | only measures injected classes |
| Mutation-recovery rate | success on `?mut=` variant where base locator strategy fails | mutation suite, per type | fixture authored by us | fixture realism — mitigated by live domains per TC |
| Diagnosis accuracy | classifier assigns the known injected class | compare on injected-failure cases | injection defines the class | top-level classes only (7) |
| Replan rate | replans per task | trace | — | architecture-honesty alarm: if most tasks replan constantly, the "evolving prefix" claim is re-examined in the ADR |
| Latency p50/p95 | wall-clock per task | harness `seconds` + per-step ms | — | eval hits fixtures via loopback; stated in analysis |
| Cost | tokens, $ per task, actions/task | OpenRouter usage/cost response fields + action counter | — | $ is provider-reported estimate |

Dropped, with reasons: **step success rate** (no per-step ground truth — steps
remain in traces for diagnosis, not gated) · **unnecessary-action rate** (no
minimal-sequence ground truth — raw actions/task reported instead) · **live
UI-change recovery as a gated metric** (live drift is uncontrollable; the
mutation suite tests the mechanism; live drift events are logged when observed).

## Mutation catalog (self-maintenance ground truth)

Deterministic server-side HTML transforms on fixture pages, selected by
`?mut=<name>`, committed to the repo — reproducible controlled breakage instead
of waiting for real sites to change.

B-floor (3 types, each chosen to break a specific locator tier) [MUST]:
ids-renamed (breaks stable-attr tier) · button-text-renamed (breaks
text/label tier) · wrapper-nesting (breaks structural assumptions).

B-strong [SHOULD], **implemented at M8** — the admission test is "does it break
a capability a plan stands on", which is wider than "is it a locator tier" and
narrower than the original wish-list:

| mutation | breaks | the rung that survives | case |
|---|---|---|---|
| duplicate-labels | role+name **uniqueness** — the only source of `ambiguous-match` in the catalogue | text | l4-shop-duplicate-labels |
| a11y-stripped | the role tier for controls (button → div, text and ids intact) | text | l4-shop-a11y-stripped, l4-forms-a11y-stripped |
| element-reordered | positional `index` | none — `near` survives it, `index` has no rung | l4-shop-element-reordered (+ …-near) |
| render-delayed | *when* the resolver looks (content arrives 10s late) | none | l4-shop-render-delayed |
| overlay-modal | actionability — the element resolves and cannot be clicked | replan (the act family, not relocation) | l4-shop-overlay-modal |

**classes-scrambled is dropped, not deferred**: the resolver has no class tier
and no code path anywhere reads a class attribute, so scrambling classes would
break nothing a locator stands on. A mutation every case survives without
changing anything measures the catalogue's size, not the agent
(`specs/decisions/ADR-009-m8-mutation-hostility.md`).

An L4 case = one base task × one mutation; pass = same semantic result as base
**where the agent survives at all**. Two of the five above are committed with
the failure as their expectation, because that is what the build really does,
and `expect.mutation_survived: false` keeps them out of the survival numerator
(the metric otherwise counts "matched its expectation", which for a case that
expects a loud stop counts a failure as a survival).

## OutcomeVerifier — layered verification (executor never grades itself)

| Layer | What | Reliability | Cost | Latency | Correlated-error risk |
|-------|------|-------------|------|---------|------------------------|
| 1. Deterministic predicates [MUST] | URL patterns, DOM-state asserts, fixture `/state` endpoint, **identity anchors** (the target entity's distinguishing string must appear in the evidence) | highest | ~0 | ~0 | none |
| 2. Expected-output compare [MUST] | normalized compare vs `expect`; live ground truth **snapshotted at execution start** via site APIs, or tolerance predicates ("answer ∈ top-N at either timestamp") | high | ~0 | one API call | none |
| 3. Evidence-only LLM check [SHOULD] | only where 1–2 can't decide; input = task + final screenshot + extracted text + trace summary, **never the executor's conclusion**; must verify entity match, not evidence coherence; verdict PASS / FAIL / INCONCLUSIVE (INCONCLUSIVE ≠ pass) | medium | 1 call | seconds | REAL — see below |

Identity anchors exist because the canonical silent failure is
wrong-but-self-consistent: agent lands on similar Product Y, extracts a real
price, everything looks coherent. Layer 1 therefore checks that the *task's*
entity appears in the evidence, deterministically where possible.

**Verification stance**: default runtime verification is deterministic. LLM
semantic verification, when enabled, is intentionally treated as **weak
independent evidence, never ground truth**. Model diversity between planner and
verifier is an optional ablation [BACKLOG], not a correctness assumption.

**Verifier accuracy estimation**:
- Trap set [MUST]: planted wrong outcomes the verifier must fail. This measures
  false-positive-success on *imaginable* wrongness — reported as a **floor**,
  not the accuracy estimate. Gate: trap-catch ≥ 90%.
- Hand-labeled sample [SHOULD]: ~15–20 audited verdicts, stratified pass/fail,
  reported as precision/recall in the analysis.
- Disagreement log [MUST]: every executor-claim vs verifier-verdict mismatch is
  recorded and reviewed during triage.
- Definitions: **false-positive success** = verifier passes a wrong outcome;
  **false-negative failure** = verifier fails a correct one; **inconclusive** =
  verifier abstains (counts against E2E success, surfaced in reports).
- Stated limitation [MUST → honesty]: planner and (if enabled) LLM verifier may
  share a model family; shared semantic blind spots are exactly what traps
  cannot sample. This is written in the analysis, not hidden.

## Suites

| Suite | Contents | Network/LLM | When |
|-------|----------|-------------|------|
| `invariant` | pure-code property checks (budget enforcement, trace completeness, classifier mapping) | none | every src edit (hook) |
| `fast` | fixture E2E with **LLM stubbed at the module boundary** (resolver / classifier / verifier L1–2 are deterministic — the parts worth gating); ≤2–3 record/replay smokes only if cheap [SHOULD] | offline, $0 | every commit (pre-commit gate) |
| `full` | live sites + real LLM calls | paid | manual / scheduled; feeds the analysis and support matrix — never CI |

Planned invariants (enter `specs/000-invariants.md` only WITH their backing
cases, per the drift rule): no success without verifier-checkable evidence ·
every failure carries exactly one class · budgets always enforced · traces
complete (every action has pre/post observation) · fast suite is offline.

## Thresholds

A priori (integrity): invariant suite 100% · trap-catch ≥ 90%.
Performance thresholds (E2E success, recovery, mutation-recovery) are set
**after the M2 baseline run, via ADR-002, citing observed numbers** — naming
them pre-baseline invites goalpost-moving in a graded commit history.
