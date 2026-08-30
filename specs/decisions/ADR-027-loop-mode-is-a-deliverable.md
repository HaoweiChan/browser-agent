# ADR-027: the per-step agentic loop is a deliverable capability, not an ablation — completion outranks cost, honesty outranks both

Date: 2026-08-25
Status: accepted

**Ruling**: the owner relayed an interviewer mandate on 2026-08-25 — the agent must complete tasks "by any means necessary, cost is not a constraint" — and this ADR re-weights the goals accordingly: a second execution mode ("loop mode") is built in which the model is called after EVERY action with a fresh observation and chooses the next tool call (architecture A of `docs/architecture/task1-overview.md`, previously rejected on cost), with a wider action vocabulary and, in a second milestone, screenshot/vision observation; mode B (plan-then-execute) stays shipped and stays the offline-suite substrate; per-run cost CEILINGS are raised to runaway-protection levels while cost ACCOUNTING is unchanged — every run still records tokens and USD, because "not a constraint" is a budget statement, not permission to stop measuring.
**Because**: the 2026-08-24 demo failure (`docs/evals/2026-08-24-demo-sec10k-inspector-postmortem.md`) and D28's declared boundary are structural to plan-ahead execution — a page painted after load (S1) and an un-awaited async result (S4) cannot be planned from an observation taken before they exist, and production browser agents do not have those failure classes because they re-observe after every step; the repo's own M33 block already contained the mechanism as a measurement arm, and the mandate converts its question from "should we?" into "how fast, and what must not be lost on the way".
**Enforced by**: no code — this is a direction ADR; the tracking hooks are `tasks/TODO.md` M42 (loop core), M43 (vision observation), M44 (matrix re-declaration under loop mode), each of which must land with its own ADR and red-first cases; what this ADR itself rules non-negotiable is listed under Invariants below and is graded by the existing cases named there.

---

## Context

Architecture B — one planning call over a condensed observation, then
deterministic execution with observe/replan as the recovery path — was chosen
for cost, trace inspectability and offline evaluability, and those properties
produced this repo's strongest results: a $0.00 `fast` suite of 181 cases, a
verifier that grades every step, and zero wrong-success across 36 pre-registered
probe runs (ADR-025). The same choice produced the weakest results: D28's
`unsupported` for script-painted pages and dense grids, T-M40-2's document-root
reach, and the 2026-08-24 demo failure against our own sec-10k inspector, where
four page shapes (S1–S4 in the postmortem) are all consequences of planning
before the page exists.

The M33 queue block ("per-step tool-calling planner vs evolving-prefix, numbers
decide") already specifies the loop mechanism: OpenRouter native tool-calling,
one model call per step, fresh observation after every step, the step cap as the
budget. What changed on 2026-08-25 is the decision criterion. M33 asked whether
the measured completion gain justifies the cost; the interviewer has answered
that question by fiat. What remains to decide is engineering order and what is
preserved.

## Decision

1. **Loop mode is built as a peer mode, not a replacement.** `agent.py` gains a
   loop driver selected per task (`POST /tasks` flag and an env default). Mode B
   remains the default for the offline suites and the $0 paths. The two modes
   share the executor's action implementations, the resolver, the trace schema,
   the verifier and the judge — the loop replaces the *planning cadence*, not
   the machinery that grades what was done.

2. **The action vocabulary widens** (loop mode and B alike, since they share the
   executor): `select_option`, `scroll`, `press`, `wait_for` (condition-based,
   reusing `check_state`'s predicates), `go_back`. Each action lands with its
   postcondition semantics and red-first cases, per the existing per-feature
   loop. A default post-click settle (postmortem S4) is subsumed: in loop mode
   the model sees the un-settled page and can wait; in mode B the existing
   authored `expected_state` path stands.

3. **Observation in loop mode is on-demand rich.** The per-step observation
   keeps a budget (an unbounded DOM dump is noise, not information — the D7
   lesson stands), but the model can spend steps drilling (`observe` exists) and
   the budget is per-call, not per-run. M43 adds screenshots to the loop
   observation for a vision-capable model, which is the fix for the S2 class
   (answers that are not accessible names): the model looks instead of relying
   on ARIA.

4. **Budgets become runaway protection, and this amends ADR-010.** Loop mode
   gets its own step cap and token/USD ceilings, set generously and recorded
   per run. `ALLOWED_MODELS` gains at least one frontier vision-capable model —
   which is above ADR-010's price ceiling by construction, so this is a
   declared amendment, not a drift: the ceiling STAYS for the ablation arms and
   for mode B's default, and is lifted only for the loop-mode additions, each
   allowlisted by explicit id with its price recorded in M42's ADR. The graded
   exclusion (`gateway-model-reaches-planner`) must be extended in the same
   change that widens the list, watched red first, so the ceiling it enforces
   is the amended rule and not a fiction.

5. **The plan-shape guards are re-homed, not lost.** ADR-018's aggregate
   single-read rule and ADR-024's document-root refusal are anchored "at every
   point the executor adopts a plan" — an anchor loop mode does not have, and
   without re-homing, a loop-mode `WebArea` extract would be exactly the
   T-M40-2 shape with no guard (ADR-024 deliberately moved the root OUT of
   `verify`'s remit). M42 therefore re-homes both as tool-call-time refusals —
   a root-target extract call is refused as it is emitted, and the aggregate
   rule is enforced at answer assembly over the trace — each watched red in
   loop mode before the mode ships. ADR-018 and ADR-024's rulings for mode B
   are unchanged; this extends their reach, scoped to loop mode. Similarly
   scoped: ADR-020 rules `observe` spends the replan budget and no new one —
   in loop mode `observe` spends the STEP budget like any other call, which is
   an amendment to ADR-020 confined to loop mode; mode B's observe budget is
   untouched.

6. **M33 is absorbed, not deleted.** The A-vs-B measurement still runs — as
   M44's evidence that loop mode earns default-ness for live traffic, and as
   the honest record of what the mandate bought per dollar. Declared rather
   than blurred: M44's arm runs on the D28/M40-card/inspector probe set, not
   M33's M9 task set — the comparison moves to the tasks the mandate is about;
   if the M9-set comparison is still wanted it is a separate, unqueued ask.
   The M33 block in `tasks/TODO.md` carries a note to this effect rather than
   being rewritten.

## Invariants — what "無所不用其極" does NOT reach

The mandate is about effort and cost, and it is read narrowly. These stand:

- **Zero wrong-success stays the hard property.** The verifier's L1 guards and
  the fail-closed judge (ADR-017, ADR-023) grade loop-mode runs unchanged. A
  mode that completes more tasks by lying about completion is a regression, and
  the existing guard cases (`extract-container-dump-is-not-the-answer`, the
  judge fail-closed set) run against loop-mode traces too.
- **Rule 6 stands.** No site-specific selectors, DOM paths or navigation
  recipes in the execution policy — capability comes from the loop and the
  model, not from memorising sites. Per-site data stays start URL, rate limit,
  ground-truth endpoint.
- **Eval-first stands, and is the real engineering cost of this ADR.** Every
  loop feature lands with cases driven by a scripted tool-call stub (the same
  injection-boundary shape as `stub_planner` and the ADR-017 judge stub): the
  stub model emits a recorded tool-call sequence, so the driver, the new
  actions and the trace shape are graded at $0 in `fast`. What the stub cannot
  grade — the live model's step choices — is measured the way this repo already
  measures planning quality: deployment probes with published run ids
  (ADR-022, ADR-025 protocol).
- **The trace stays the evidence.** Every tool call is a trace step in the
  existing schema (extended by its own ADR where new actions need new fields),
  so the reviewer UI, the verifier and the judge read loop runs without a
  second evidence pipeline.

## Consequences

- Per-task cost in loop mode is expected to be one to three orders of magnitude
  above mode B (one planning call ~1.4k tokens today vs. per-step calls on a
  frontier model, plus images under M43). Accepted by mandate; recorded per run;
  `docs/analysis.md` gains a per-mode cost row when M44 reports.
- The `fast` suite does not measure loop-mode *planning quality* — only its
  machinery. This is the same epistemic split the repo already lives with for
  mode B (stubbed plans vs. live probes) and it is stated rather than hidden.
- Rep-level nondeterminism (T-M40-5-3) likely worsens with more model calls per
  run; M44's protocol therefore stays 3 reps minimum per declared task.
- The wall-clock ceilings of the offline suites are untouched — loop mode adds
  no case to `fast`/`invariant` that spends network or tokens.

## What is NOT decided here

The loop driver's exact prompt/tool schemas, the new trace fields, the step
cap's number, which frontier model joins the allowlist, and whether loop mode
becomes the live default — each belongs to M42/M43/M44's own ADRs, decided
with implementation evidence in hand.

*Answered 2026-08-26 by ADR-028 (M42), except the live default, which is still
M44's:* the schemas and the driver prompt are in ADR-028 §1/§7, the trace gains
NO fields (§7), the caps are `{actions 40, llm_tokens 400k, llm_usd $5}` and are
injectable so they can be graded (§6), and the model is `anthropic/claude-opus-5`
at 3.1x/7.8x this ceiling, frozen with its price (§8). Decision 5's re-homing is
§2, and it came out narrower than this ADR anticipated in one respect worth
recording: both guards are the SAME functions asked at a second anchor, not
loop-mode reimplementations of them.

## Amendment — ADR-046 canonical migration

ADR-046 supersedes Decision 1's permanent peer-mode direction only: `plan` and
`loop` become temporary parity comparators on the path to one canonical graph.
Its preservation requirements — shared executor, resolver, trace, verifier,
judge, rule 6, and zero wrong-success — remain unchanged.
