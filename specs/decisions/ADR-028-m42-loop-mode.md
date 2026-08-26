# ADR-028: loop mode ships — one model call per step, sharing every piece of machinery that grades it

Date: 2026-08-26
Status: accepted

**Ruling**: `run_task` gains `mode="loop"`, selected per task (`POST /tasks`'s `mode` flag, defaulting to `BROWSER_AGENT_MODE` and to mode B when that is unset or unrecognised), in which a *driver* — `async (task, url, observation, trace, found, note) -> (call, usage)`, the same injection boundary `planner` and `judge` already have — is called after EVERY action with a fresh observation, the executed trace, what has been extracted so far, and any note, and returns exactly one OpenRouter tool call; twelve tools are declared, one per executor action plus `final_answer`; the action vocabulary widens for BOTH modes with `select_option`, `scroll`, `press`, `wait_for` and `go_back`, each with a postcondition and a red-first case; observation and evidence pierce iframes and open shadow roots; a no-progress harness forces a strategy change and then ends the run loudly when the loop revisits a state without learning anything; loop budgets are `{"actions": 40, "llm_tokens": 400_000, "llm_usd": 5.00}`, injectable so they can be graded; and `ALLOWED_MODELS` gains `anthropic/claude-opus-5` as a third list, `LOOP_MODELS`, deliberately outside `ABLATION_MODELS`.
**Because**: ADR-027 ruled the loop is a deliverable and set the boundary of the "any means necessary" mandate — zero wrong-success, rule 6, eval-first and the single trace pipeline are not reachable by it — so the entire engineering question left was *how to add a second planning cadence without adding a second anything else*; every decision below is an answer to that, and the two guards that ADR-027 Decision 5 said would lose their anchor are the proof it was the right question.
**Enforced by**: the cases named below, each watched red first with the observed output recorded in `docs/evals/m42-red-first-ledger.md` — `loop-drives-a-fetch-then-render-page`, `loop-mode-b-cannot-read-the-un-awaited-result`, `loop-token-ceiling-stops-the-run-loudly`, `loop-usd-ceiling-stops-the-run-loudly`, `contract-trace-schema-loop-mode`, `loop-refuses-a-document-root-extract`, `loop-aggregate-single-read-at-answer-assembly`, `loop-aggregate-enumeration-is-accepted`, `action-select-option-verifies-by-readback`, `action-select-option-refuses-an-absent-option`, `action-scroll-moves-the-viewport`, `action-scroll-that-moves-nothing-is-loud`, `action-press-carries-a-postcondition`, `action-wait-for-reaches-a-late-predicate`, `action-wait-for-that-never-holds-is-loud`, `action-go-back-returns-to-the-previous-page`, `observe-reaches-into-an-iframe`, `shadow-dom-value-is-reachable-and-grounded`, `loop-no-progress-revisit-ends-the-run-loudly`, `gateway-mode-selects-the-driver` — `loop-observe-drills-into-a-container`, `driver-tools-match-the-executor`, `loop-refused-anchor-is-not-an-answer`, `loop-failed-enumeration-does-not-disarm-rank`, `extract-all-refuses-matches-in-two-documents`, `loop-recovered-failure-still-verifies`, `replan-cannot-launder-noop-action-in-a-frame`, `replan-after-an-iframe-only-change-is-not-laundering` (the pair that specifies `page_changed`; see item 5) — plus the extended `gateway-model-reaches-planner`, the moved row in `gateway-model-not-allowlisted`, and `mode` added to both `contract-trace-schema` cases.

---

## Context

ADR-027 decided that loop mode gets built and listed what must not be lost on
the way. It deliberately left five things to this ADR, "decided with
implementation evidence in hand": the driver's prompt and tool schemas, the new
trace fields, the step cap's number, which frontier model joins the allowlist,
and — the one that turned out to matter most — how the two plan-shape guards are
re-homed when there is no plan to anchor them to.

## Decision

### 1. The loop replaces the cadence and nothing else, enforced structurally

`drive_loop` is a nested function inside `run_task`, beside the step loop it
replaces. It calls the same `execute`/`attempt` the plan path calls, and it ends
by calling `finalize` — the answer assembly, `verifier.rank`, `verify` and the
judge — which was extracted from `run_task`'s tail in this change *precisely so
that there is one copy*. Mode B reaches `finalize` from outside the browser
context and the loop reaches it from inside; two copies of a grading tail is the
divergence ADR-027's "the verifier and the judge are shared" forbids, and it
would not have been visible in any test.

The loop never binds `steps`. `plan-adoption-is-the-only-steps-rebind` reads
`agent.py` structurally and would redden if it did, which is how a second
adoption point stays impossible rather than merely discouraged.

**The final answer is not the model's.** `final_answer` takes no answer text: it
says "I am done", and the answer is assembled from what was `extract`ed exactly
as in mode B. This is the single most load-bearing choice here for ADR-027's
zero-wrong-success invariant — a model-authored final string would be an answer
no `grounded` check, no `not_a_dump` ratio and no `rank` ever touched. A
`final_answer` with nothing extracted is INV-0's empty answer and fails loudly.

### 2. Both re-homed guards are one function with two callers, never two copies

ADR-027 Decision 5 named the risk exactly: ADR-024's document-root refusal and
ADR-018's aggregate single-read rule are anchored at plan adoption, and a loop
has no adoption point, so a loop-mode `WebArea` extract would be the T-M40-2
shape with no guard at all.

* **Root-target refusal** → `agent.root_target_gap(step)`, asked by `plan_gap`
  (mode B, before anything runs) and by `execute` (loop mode, as the call is
  emitted). The refused call is recorded as a refused trace step, never
  executed, and its reason is handed back to the model — which then names the
  element that holds the value. `loop-refuses-a-document-root-extract` ends
  `success`, and that is the point: the guard is not a dead end, and the case
  asserts through `trace_note_contains` that the root read never happened, since
  the status alone cannot tell a refusal from a permission.
* **Aggregate single-read** → the same `plan_gap`, asked once more at answer
  assembly over the *executed* trace (refused and superseded steps excluded).
  That is the last moment before an answer exists, and it is the only "before"
  a loop has.

Writing a loop-specific copy of either judgement was the alternative, and it is
the shape this repo has been burned by repeatedly (ADR-018's two call sites,
M32's unlinted third adoption point). One rule, two anchors.

### 3. Five new actions, each with the postcondition that makes it verifiable

| action | what it does | postcondition |
|---|---|---|
| `select_option` | reads the control's options, matches `value` against label or value, selects by value | readback of `input_value()` — the browser's answer, not the call's return |
| `scroll` | `window.scrollBy(value)` px, or `scroll_into_view_if_needed` with a target | the scroll position moved / the target is visible |
| `press` | one key to the target or the page | the authored `expected_state` (a click's obligation) |
| `wait_for` | nothing — `attempt`'s `check_state` IS the wait | the predicate holds within `SETTLE_BUDGET_MS`, else `act` |
| `go_back` | `page.go_back()` | the authored `expected_state`; no history is an `act` failure |

Shared by both modes, because the modes share the executor. That sharing is what
makes `loop-mode-b-cannot-read-the-un-awaited-result` an honest A/B: mode B has
`wait_for` and still fails the postmortem's S1/S4 page, because it cannot
*author* a wait for a banner whose wording does not exist at planning time.

`select_option` reads the options and picks one rather than letting Playwright
match the string, for a measured reason: two match attempts (label, then value)
burn a timeout each on the failure path — 20s per absent option in a suite
budgeted at 90s — and tell the model nothing about what it could have picked
instead. It now says.

`verifier.STATE_CHANGING` widens the unverified-state-change guard from `click`
alone to `{click, press, go_back}`. `fill`, `select_option` and `scroll` read
back what the browser holds and set their own `postcondition_ok`; `navigate` is
deliberately out, since its consequence is the URL it was handed.

### 4. Observation reach: the iframe was invisible, the shadow root was ungradeable

Measured on `fixtures/frames-host.html` before any change, and it corrected this
milestone's own premise:

* **iframes** — `page.accessibility.snapshot()` reports the frame as one node
  and stops; `page.accessibility.snapshot(root=<handle in the child frame>)`
  returns `None`; and a Playwright locator never crosses a frame boundary, so
  `resolve` raised `no tier resolved` for every element inside. Blind in
  observation *and* resolution, in both modes, regardless of vision. Our own
  sec-10k inspector renders its source pane as an iframe.
* **open shadow roots** — already in the accessibility tree, already resolvable.
  That half needed no fix. What was blind was the **evidence**:
  `page.inner_text("body")` does not traverse shadow roots (`'NBX-7741' in body`
  was `False` while the same value read back off the locator), so a correct read
  was failed as ungrounded by the verifier, a `text_visible` postcondition over
  shadow content could never hold, and `page_changed` could not see a
  shadow-only mutation. A correct answer graded wrong is the same run-killer as
  an unreachable element and a worse one to debug.

Two fixes, each in one place. `observe()` continues into every child frame using
Playwright's own ARIA snapshot — the roles and names computed by the same engine
`get_by_role` matches with, so what the observation advertises is what the
resolver can reach — spending whatever is left of the *same* `MAX_ELEMS` budget,
because an iframe does not buy the page a second one. `resolve()` builds the
same tiers in each scope, main frame first, so a page without iframes resolves
byte-identically to before.

`observe.page_text(page)` is the single evidence path: main frame first, each
frame's `innerText` plus each open shadow root's rendered children, one
`evaluate` per frame. It replaced all five `page.inner_text("body")` call sites
at once — the evidence window, `text_visible`, the `page_changed` comparison,
the per-page furniture record and the final digest — because fixing the one a
bug report names leaves the other four broken.

### 5. The no-progress harness counts VISITS, and its own golden case caught it

A step cap is not a harness: it lets a run grind its whole budget down in a
circle and then report a *resource* failure, which names the symptom and not the
cause. The interviewer's 首頁↔dashboard loop was 18 model calls and 2 repairs of
exactly that.

When the loop arrives at a `(URL, page-signature)` state it has already been to
`LOOP_REVISIT_CAP` (3) times with nothing new extracted since, the driver is
handed a `NO PROGRESS` note it cannot ignore; on the visit after that the run
ends `failure:env` with that reason — `env` for the same reason `budget_stop`
and M32's drill-down guard use it, a ladder that could not help IS the failure,
with the difference that the reason now says why.

**A visit is an arrival, not a turn.** The first version counted turns, and
`loop-drives-a-fetch-then-render-page` immediately went red: select an option,
click, then wait for the result is three turns on one page whose observation
barely moves, and the harness called that a circle and killed a run that was
working. This is the eval set doing its job on the milestone's own new
mechanism, and it is the reason the case is golden rather than adversarial.

`page_signature` is the roles, names and text head the model is shown — two
turns the model cannot tell apart must not look like progress to the harness
either. It excludes the URL because the caller pairs it with `page.url`: a SPA
changes state without changing URL and a query string changes URL without
changing state.

*Declared ceiling*: the other no-progress shape — the same call repeated forever
on one page — is bounded by the step cap rather than by this harness. Named in
the code as a `ponytail:` comment with its upgrade path; nothing has produced it.

### 6. Budgets are runaway protection, and they are injectable so they can be graded

`LOOP_BUDGETS = {"actions": 40, "llm_tokens": 400_000, "llm_usd": 5.00}`, and
`budget_stop` takes the table as a parameter so one function serves both modes.

`llm_usd` exists here and not in `RUN_BUDGETS` because mode B plans once with a
model held under ADR-010's ceiling, where tokens are a faithful meter, while
loop mode calls a frontier model once per step, where the same token count can
be two orders of magnitude apart in money.

The caps are injectable (`run_task(loop_budgets=...)`). The first version of the
two ceiling cases scripted 500,000 tokens and $99 of stub usage to trip the
shipped caps; it worked, and it put `cost $99.0000 · 500010 tok` on the headline
of a suite whose entire claim is $0.00 (cost-discipline rule 4). Runaway
protection that can only be exercised by actually running away is protection
nothing checks. The cases now trip a 1-token and a $0.000001 cap, and pin
through `expect.budgets` that the run really did *account* for what the stub
reported — ADR-027's "not a constraint is a budget statement, not permission to
stop measuring" is otherwise the half that quietly breaks.

### 6b. Loop-mode `observe` spends the step budget — the ADR-020 amendment

ADR-027 Decision 5 assigned this to M42's ADR and it was nearly lost: the code
cited ADR-027 directly and routed around the implementation ADR that was
supposed to record it (spec-drift audit, finding 4).

ADR-020 rules that `observe` spends the replan budget and no new one. In loop
mode there is no replan: the drill-down is a tool call like any other, so it
spends the STEP budget through `attempt` and never touches `budgets["replans"]`.
`loop-observe-drills-into-a-container` grades both halves — `budgets.replans: 0`,
and `planner_saw` proving the subtree was actually disclosed. The disclosure
half was itself a defect: `execute` filled `drilled` and only mode B's branch
popped it, so loop-mode `observe` was a silent no-op while the tool description
handed to the model promised "you are shown that subtree alone". A second round
found the other half of the same promise — the scoped observation was swapped in
with no note saying it was a subtree, and `observe.render` prints the PAGE's URL
and title either way, so the model could not have told. Mode B has always passed
that note; loop mode does now.

ADR-020's ruling for mode B is unchanged. This amendment is confined to loop
mode, exactly as ADR-027 Decision 5 scopes it.

### 7. The trace gains no fields

Every tool call is a `TraceStep` in the existing schema, `final_answer`
included, so the reviewer UI, the verifier and the judge read a loop run
unchanged and there is no second evidence pipeline.
`contract-trace-schema-loop-mode` is the case that reddens the day someone adds
a loop-only key.

The RESULT does gain one field, and it is not a trace field: `mode`, beside
`model`, because a run record has to be self-attributing. Without it a loop run
and a mode B run of the same task on the same model are byte-identical in shape
and the only way to tell them apart is counting `final_answer` steps — while
M44's entire job is comparing the two modes from committed run records
(spec-drift audit, finding 9). This is why the driver is handed `found` — what has been
extracted so far — as an argument rather than reading it out of the trace: the
trace records what was *attempted*, not what came back, and writing extracted
values into the trace `note` would have moved mode B's evidence shape to serve a
loop-mode need.

`live_driver` is stateless: every turn is rebuilt from (task, observation,
trace, extractions, note) rather than from an accumulated message list. That
costs prompt tokens — accepted by ADR-027's mandate, recorded per run — and buys
exactly the property ADR-027 asks for by name: the trace IS the state.

### 8. `anthropic/claude-opus-5`, as a third list

`LOOP_MODELS` is separate from `ABLATION_MODELS` and from `DEFAULT_MODEL`. The
id is in `ALLOWED_MODELS`, so `POST /tasks` accepts it and the existing
containment check requires it to be frozen evidence; it is **not** in
`ABLATION_MODELS`, where the price sweep runs, so ADR-010's ceiling is untouched
for every arm that ADR-027 said keeps it.

Price, read from `https://openrouter.ai/api/v1/models` on 2026-08-26 and frozen
into `evals/labels/openrouter-models-20260820.json` beside every other entry
(never typed by hand — a copied price literal drifted 11% inside one working
session once already): **$0.000005 prompt / $0.000025 completion per token**,
against `CEILING_MODEL`'s $0.0000016 / $0.0000032 — **3.1x and 7.8x over the
ADR-010 ceiling**. Over by construction, which is exactly why ADR-027 required
the amendment to be declared rather than absorbed. `input_modalities` includes
`image` and `supported_parameters` includes `tools`; both are recorded in the
snapshot entry, because loop mode needs tool-calling now and M43 needs vision.

`gateway-model-reaches-planner` was extended in the same change, watched red
first (`allowlisted_but_not_in_the_verified_snapshot: [anthropic/claude-opus-5]`),
and now grades all three properties. `gateway-model-not-allowlisted`'s
refused-frontier-model row moved to `anthropic/claude-sonnet-5`: the row's point
— a public unauthenticated endpoint must refuse an expensive model nobody
allowlisted — is unchanged, and it went red the moment the allowlist and its own
refusal case disagreed.

## Consequences

- The `fast` suite grows and stays $0.00 and offline. It reports 2
  stub-declared tokens and $0.000002, from the two ceiling cases; that is the
  meter proving it works, not spend.
- `select_option`, `press`, `wait_for`, `scroll` and `go_back` are available to
  mode B's planner, but `planner.SYSTEM` still advertises the original six.
  Widening the planner prompt is a change to mode B's measured behaviour and
  belongs with a mode B measurement, not with this one — logged as debt
  (`T-M42-1`), not smuggled in.
- Every page read now costs one `evaluate` per frame instead of one
  `inner_text`. On a frameless page that is the same round trip; the shadow walk
  is `querySelectorAll('*')` per read, whose ceiling is named in the code.
- `POST /tasks` is public and unauthenticated, and `mode: "loop"` on a frontier
  model is now reachable from it. The USD ceiling is what bounds that, and it is
  the reason the ceiling is per-run rather than per-deployment.

## What the review round found, because it is the same lesson six times

Cold review and the spec-drift audit ran before this ADR was final, and between
them found five defects that are one defect: **mode B ends the run at the first
failed step, so a failed step's side effects never outlived it — and every guard
written against "the run dies here" had to be re-read for a mode where a failed
call is routine.**

1. `execute` appended to `answers`/`extractions` and *then* ran the
   identity-anchor check. In loop mode the refused read stayed: `success`,
   verdict PASS, and the trace carrying `failure_class: "semantic"` on the very
   step the answer came from. Fixed as a **rollback in `attempt`**, not as a
   reordering of that one check — "a failed step leaves no evidence behind" is
   the property, and the URL guard that fires after `execute` returns is its
   second instance.
2. `finalize` read the ranking declaration off the first `extract_all` that was
   not superseded — and nothing in loop mode ever set `superseded_by`. A first
   attempt that omitted `rank` (which `execute` refuses in a message that
   teaches the model the exact retry) left `enumerated = None`, `rank` never
   ran, and a raw candidate list answered a which-one question. ADR-018's
   defect family, through a path none of its guards cover.
3. The mirror image: the verifier's unverified-state-change guard counts a
   failed `click` because a raise inside `execute` leaves `postcondition_ok`
   null, so a run that clicked wrong, was told, and then read the right answer
   was demoted. **(2) and (3) share one fix**: a failed loop call is superseded
   by whatever the model does next, through the same `pending_supersede`
   mechanism mode B's replan uses — with `final_answer` excluded, so a model
   that gives up right after a failure is still graded on that failure.
4. Frame-scoped resolution was first-win *per document*, which is right for a
   unique match and silently wrong twice: `extract_all` returned whichever
   document matched first (an enumeration truncated to one frame, wrong by
   omission), and a main-frame ambiguity was settled by a unique match in a
   child frame. Now each document resolves to completion before the next opens,
   and an enumeration matching in two documents is refused loudly.
5. `page_text`'s new reach moved calibrated inputs it had no business moving.
   The shadow walk checked visibility only on a root's direct children, so the
   ordinary wrapper-`div` shape let hidden text ground answers — fixed by
   walking the subtree and skipping anything the page is not rendering.

   `page_changed` — the sole evidence behind the anti-laundering guard — took
   two more rounds and ends up at the OPPOSITE of what this item ruled when it
   was first written. That ruling ("evidence is widened; a calibrated guard's
   input is not", i.e. keep `page_changed` main-frame-only) is **withdrawn**;
   it is recorded here rather than deleted because it was the position this ADR
   argued for, and because reversing it is the substance of what follows.

   **Shipped ruling: `page_changed` compares `page_text(page)` — every frame —
   on both sides.** Three settings were tried and only the third survives:

   | setting | no-op step on a framed page | step whose only effect is inside a frame |
   |---|---|---|
   | asymmetric (`before` main-only, `after` all frames) | **true** — guard disarmed | true |
   | symmetric, main-frame-only | false | **false** — legitimate replan refused, run dies claiming the step "changed nothing" |
   | symmetric, frames-aware (shipped) | false | true |

   The two cases that pin it are the same page shape with and without a real
   effect, and **the pair is the specification of the field** — neither alone
   constrains this line, which is exactly how the first repair flipped the sign
   while staying green: `replan-cannot-launder-noop-action-in-a-frame` and
   `replan-after-an-iframe-only-change-is-not-laundering`.

   The accepted cost is a page whose frame mutates on its own — a ticking
   third-party iframe, a rotating ad, a chat bubble — reading as a change
   nobody caused, which unlatches the guard in the other direction. That hazard
   is real and has never been reproduced here, while the false negative was
   reproduced on a six-line fixture; this repo widens on what a probe found,
   not on what someone imagined (D21). **T-M42-14** carries the repro that
   would reopen it. Both costs are now declared, which is the part that was
   missing the first time: the false positive was documented and the false
   negative was not.

None of the five is exotic. Each is the ordinary case: a model-authored anchor
that misses the page, a tool argument omitted once and corrected, a click with
a wrong expectation, a page with an iframe. The reason they were reachable is
worth more than the fixes: **loop mode did not add a new failure path, it
removed an old assumption** — that the first failure ends the run — and every
guard downstream had been written under it.

## What is NOT decided here

Whether loop mode becomes the live default (M44's evidence decides), vision
observation (M43), and the live A/B numbers. This ADR ships the mechanism and
its offline grading; the deployment probes that measure the live model's step
choices are M44's, under ADR-022/ADR-025's protocol.
