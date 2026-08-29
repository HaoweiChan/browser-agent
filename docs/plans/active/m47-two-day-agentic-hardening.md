# M47 — two-day agentic hardening

Status: active planning. Implementation has a **12 engineering-hour ceiling**
(less than two working days). This is a reliability slice, not a claim that M44's
three-mode live campaign or a general Browser Agent is complete.

## Outcome

Ship the smallest vertical slice that makes the interviewer's two sharpest
runtime problems both less likely and easier to inspect:

1. a loop that chooses the same action on the same unchanged page is forced to
   change strategy, then stopped loudly if it repeats once more; and
2. the existing reviewer UI renders the agent's public decision trail as a
   terminal-style console while the run is live.

The implementation reuses the current `TraceStep` record, `on_step` callback,
SSE `step`/`done` events and inline frontend. It adds no framework, browser
runtime, event bus or dependency.

## Starting point

The repo already has the expensive pieces:

```text
loop driver -> executor attempt -> TraceStep -> on_step -> SSE step -> reviewer UI
                                      |
                                      +-----------> final RunResult trace
```

M42 detects repeated page-state revisits, but `T-M42-6` records the remaining
hole: one unchanged page plus one identical tool call can run until the general
action ceiling. The UI already renders every `TraceStep`, including recovery,
failure, postcondition, screenshot and final authoritative trace. M47 changes
those two existing surfaces rather than creating a second agent or telemetry
model.

## What we borrow — and what we do not

| Reference | Pattern adopted in M47 | Deliberately not adopted |
|---|---|---|
| [BrowserGym](https://github.com/ServiceNow/BrowserGym) | Treat each turn as observation -> action -> outcome -> termination, with termination evidence retained | Gym environment, benchmark packages and a second browser abstraction |
| [AgentLab](https://github.com/ServiceNow/AgentLab) | Reproducible run ids and inspectable trajectories are part of the result, not debug-only logs | Experiment launcher and study framework; this repo's eval harness already owns that job |
| [browser-use](https://github.com/browser-use/browser-use) | Bounded step history and explicit loop detection beside the action budget | Its tool registry, session layer, arbitrary JavaScript/file tools and model stack |
| [Stagehand](https://github.com/browserbase/stagehand) | Keep observe, act and extract visually distinct in the operator trail | Natural-language action runtime and locator cache |
| [browser-harness](https://github.com/browser-use/browser-harness) | A failure should leave a reusable diagnosis in the trajectory | Agent-written helpers and persisted site playbooks; both conflict with the fixed action space and no-site-specific-policy rule |

The architectural conclusion is intentionally boring: the missing value is a
better progress guard and a readable projection of evidence already emitted,
not another agent framework.

## Slice A — exact-repeat progress guard

Add one site-agnostic decision key at the loop boundary:

```text
(page-state fingerprint, action, target, value, expected_state, failure class)
```

The existing page-state fingerprint remains the source of page identity. Target
and value use canonical JSON so key ordering cannot manufacture a strategy
change.

Policy:

1. The first choice executes normally.
2. The first identical choice on the identical page is allowed, but the next
   driver turn receives a code-authored recovery note: the choice repeated and
   the next action must change strategy.
3. If the driver selects the identical choice again before the page changes,
   refuse it before execution and finish with the existing failure path. The
   trace names the repeated action signature and repeat count.
4. A changed action, target or page resets the exact-repeat streak.
5. `wait_for` and `observe` receive the same one-repeat allowance. They are not
   exempt: a legitimate asynchronous wait gets one second chance, not an
   unbounded loophole.

This is narrower than a general planner-memory or subgoal system. It closes the
demonstrated loop while keeping M44 responsible for measuring whether loop mode
actually completes the SEC Extractor flow.

## Slice B — public decision console

Add one plain `<pre aria-live="polite">` console to the existing inline page.
JavaScript derives its lines from the same `TraceStep` objects `renderSteps()`
already receives:

```text
[OBSERVE] page state available
[DECIDE ] #3 click {role: "link", name: "Weighting"}
[RESULT ] changed=no · postcondition=failed · 812ms
[RECOVER] exact repeat 2/2 · choose a different action or target
[DONE   ] failure:act · 4 actions · $0.0123
```

Console rules:

- Show public decision summaries, not hidden chain-of-thought, model prompts or
  raw page dumps.
- Use only escaped, clipped fields already present in the trace: action, target,
  resolver tier, page change, postcondition, failure class, recovery flag and
  elapsed time.
- A code-authored recovery note may be reduced to a one-line diagnosis. Page-
  authored strings are never promoted into a trusted rationale.
- Live `step` events are provisional. On `done`, rebuild from the final trace so
  late `superseded_by` updates and the terminal verdict are authoritative.
- Keep the existing detailed cards and screenshots. The console is the fast
  linear view, not a replacement evidence source.
- No mode selector ships here. M44 still decides the deployment default from
  measured completion and cost.

## Red-first evidence

Implementation starts with these cases and watches each new behavioural case
fail before the fix:

| Case | Red condition | Green condition |
|---|---|---|
| `loop-identical-choice-cannot-spend-the-action-budget` | scripted driver repeats one call on one unchanged page until the general ceiling | one repeat is diagnosed; the next identical choice stops before the general action ceiling with the signature in trace evidence |
| `loop-strategy-change-clears-the-exact-repeat-streak` | the guard treats a different target/action as the same loop | changed strategy executes and the streak resets |
| `loop-wait-gets-one-bounded-second-chance` | the guard either refuses the first retry or permits unlimited waits | one identical wait retry executes; the next one is refused if the page is still unchanged |
| `reviewer-console-is-a-trace-projection` | the frontend has no decision console or reads a separate event schema | console consumes existing `step` and authoritative `done` trace, escapes content and renders recovery/failure |
| `reviewer-console-does-not-render-private-reasoning` | raw model messages, prompts or page text are displayed as rationale | only the allowlisted trace fields reach console lines |

No paid call belongs in `invariant` or `fast`. A post-deploy check may spend at
most **$0.50 total**, runs sequentially, and records actual calls, tokens, cost,
wall clock, build SHA and run ids. That check demonstrates streaming and guard
visibility; it does not close M44 or select a default mode.

## Twelve-hour schedule and cut line

| Elapsed | Deliverable | Stop condition |
|---|---|---|
| 0–1h | Reproduce `T-M42-6`; freeze the five cases above | no implementation before the repeat case is red |
| 1–4h | Exact-repeat key, recovery note and fail-loud path | invariant cases green; no new action or trace schema |
| 4–6h | `<pre>` decision console projected from existing SSE trace | live and final traces render the same ordered attempts |
| 6–8h | Adversarial repair pass: async wait, strategy change, escaping, reconnect/final overwrite | all new cases plus existing trace/UI cases green |
| 8–10.5h | Full repository gate in documented order | invariant 100%; fast meets its committed baseline and ceiling |
| 10.5–12h | Deploy smoke and evidence update if deployment is available | stop at the $0.50 cap; unreachable deployment fails loudly |

Cut order when the ceiling approaches:

1. Cut visual polish first; the console may be monochrome.
2. Cut the paid deploy smoke if no matching build is reachable; never fabricate
   its evidence.
3. Do **not** cut the repeat guard, red-first cases, escaping, accessibility or
   the objective gate.

## Expected change surface

- `src/browser/agent.py` — exact-repeat policy at the loop boundary.
- `src/browser/server.py` — console markup and trace-to-line rendering only.
- `evals/adversarial/` and the browser eval adapter — red-first cases.
- `docs/analysis.md` / `docs/support-matrix.md` only when a real deployed run
  creates evidence that changes a declared row.

No new source file is expected. A new module, dependency, event type or frontend
build step requires deleting something of equal purpose or deferring it.

## Done means

M47 is complete only when:

- the exact-repeat cases demonstrate fail-before/pass-after and stop before the
  general action budget;
- the console streams every attempted step and rebuilds from final trace;
- the UI exposes no raw chain-of-thought, prompt or unbounded page text;
- the existing invariant and fast gates pass; and
- the result is described narrowly: one demonstrated loop class is closed and
  the decision trail is visible. M44's exact SEC/INTC three-mode campaign,
  Nasdaq entitlement/date handling, Chinese over-refusal, custom ARIA widgets,
  virtual lists and production `INCONCLUSIVE` remain open.

## Handoff to M44

M47 should land before M44 if both are ready. M44 then reuses the console and
repeat evidence while running its already-declared `plan` / `loop` / `escalate`
matrix. M47 supplies inspectability and one bounded recovery invariant; only
M44's live results may choose the public default mode or claim that the
interviewer's SEC Extractor failure is closed.
