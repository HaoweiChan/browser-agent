# Output contract — browser task

Every run of the browser agent — CLI, gateway, or eval adapter — returns exactly
this shape. The eval adapter and the frontend both consume it; drift here is
contract-drift (spec-drift audits field-by-field).

## RunResult

```json
{
  "status": "success | partial | failure:<class> | unsupported",
  "model": "planner model id | null",
  "answer": "string | list | null",
  "reason": "string | null",
  "verdict": { "verdict": "PASS | FAIL | INCONCLUSIVE", "layer": 1,
               "ground_truth": false, "checks": {}, "reason": null },
  "evidence": {
    "trace": [ TraceStep, ... ],
    "screenshots": ["step_1.png", ...],
    "extractions": [ {"value": "...", "page_text": "window(s) around the value, and around the identity anchor if it falls outside", "body_len": 0} ],
    "final_url": "string | null",
    "final_page_digest": "first ~500 chars of page text | null"
  },
  "budgets_spent": {
    "actions": 0,
    "llm_tokens": 0,
    "llm_usd": 0.0,
    "replans": 0,
    "ms": 0,
    "judge_calls": 0,
    "judge_tokens": 0,
    "judge_usd": 0.0
  },
  "legs": [ {"mode": "plan", "status": "failure:<class>", "reason": "…", "answer": null,
             "steps": 0, "budgets_spent": {}, "extractions": []} ]
}
```

- `model` — the planner model this run was built with, echoed so a run record is
  self-attributing. `null` where no named model planned it (the `fast` suite
  stubs the planner at the module boundary). Added at M9: the ablation submits a
  model and writes the answer into a committed report, and without an echo the
  attribution of every row is the driver's own assertion about a deployment that
  can redeploy mid-sweep (`specs/decisions/ADR-010-m9-model-ablation.md`
  Decision 13).
- `legs` — **`escalate` runs only** (M46, `specs/decisions/ADR-037-m46-plan-then-loop-escalation.md`):
  one entry per leg that RAN, in order, carrying that leg's `mode`, `status`,
  `reason`, `answer`, step count, its own `budgets_spent`, and its own
  `extractions`. Absent on `plan` and `loop` runs, and on a run that never got
  off the ground (the gateway's pre-run `env` failure, which is mode-agnostic).
  The top-level `budgets_spent` is the per-key SUM over the legs, so the run's
  cost line is the run's cost; `evidence.trace` is their concatenation, with
  every step of a superseded leg pointing `superseded_by` at the next leg's
  first step. `evidence.extractions`, by contrast, is the FINAL leg's alone —
  that field is what the verdict was computed from, and a superseded leg's
  readings are in its `legs[]` entry rather than mixed into the graded evidence.
- `status` — `failure:<class>` uses exactly one of the 7 top-level classes in
  `docs/evals/failure-taxonomy.md` (nav, locate, act, extract, semantic, env,
  task). `unsupported` comes from pre-flight screening or mid-run discovery.
  On an `escalate` run it is the FINAL leg's status, re-derived through
  `assemble_result` so INV-0/1/2 hold of the merged record too.
- `answer` — the user-facing result. **INV-0: `status` = `success` requires a
  non-empty `answer` AND a non-empty `evidence.trace`.** An empty extraction is
  `failure:extract`, never a quiet success. The converse holds too (M28): a run
  the verifier rejected (`failure:semantic` through INV-2) carries `answer:
  null` — what was read is in `evidence.extractions`, in full, and the L1
  evidence checks (`grounded`, `not_a_dump`, `not_page_furniture`) cite it in
  `reason` by a bounded preview (`verifier.CITE_CHARS`) rather than quoting the
  page dump back (`extract-container-dump-is-not-the-answer`). Other reason
  sources (judge prose, `rank` ties, L2 `answer_matches`) are not bounded.
- `reason` — human-readable cause for non-success statuses; null on success.
- `verdict` — the OutcomeVerifier's finding (`src/browser/verifier.py`), null
  when the run stopped before anything could be verified (screened out,
  navigation failure). **INV-2: a non-PASS verdict can never be `success`.**
  `ground_truth` is false for a runtime verdict (layer 1 predicates only) and
  true when the caller supplied external ground truth — the eval adapter does,
  a live run cannot. `layer` names the deepest layer that ran.
- `verdict.checks.judge_responsive` / `judge_available` (M36) — present only
  when a run reached the terminal-verdict boundary (every L1 check already
  PASS). `judge_responsive` is the judge's own certify/reject; `judge_available:
  false` instead means the judge itself could not be reached (missing key,
  timeout, malformed response, budget exhausted) and the run failed CLOSED —
  `src/browser/agent.py`'s `_apply_judge`. `budgets_spent.judge_calls` is 0 or
  1 (`RUN_JUDGE_BUDGET`, `src/browser/judge.py`): at most one judge call per
  LEG, at this boundary, never per extraction — one leg is one `run_task`, so
  for `plan` and `loop` that is per run. An `escalate` run has two legs and its
  SUMMED `judge_calls` can therefore be 2, on exactly one path: a plan leg that
  reached the boundary and was rejected there is a `failure:semantic` leg, which
  is a trigger (ADR-037 Decisions 2 and 6), and the loop leg then reaches its own
  boundary with its own budget. Capping it across the legs would demote the loop
  leg's answer for the plan leg's spending, which is ADR-017's fail-closed firing
  on the wrong subject. `judge_tokens`/`judge_usd` are
  0 for every stub (fast/live suites) and for a cache hit; only a live,
  uncached call spends either.
- `verdict.checks.judge_attempts` (M39, ADR-023) — present alongside
  `judge_responsive`/`judge_available` whenever the judge boundary was reached:
  how many provider attempts that ONE boundary call took: 0, 1 or 2. It is 2
  only when the first attempt's completion body could not be read at all (empty
  or non-JSON) AND was not truncated — a truncated verdict
  (`finish_reason: "length"`), a refusal, a parsed body with no `certify`, a
  missing key, a transport failure and a reasoned FAIL are answers or non-calls,
  not failed reads, and are never retried. It is 0 when the per-run judge budget
  was already spent, so no provider attempt was made. Both attempts' reported
  usage is added to `judge_tokens`/`judge_usd`, so a retry is visible in the
  cost line rather than absorbed; `judge_calls` counts boundary calls and
  stays 1.
- `evidence.extractions` — what was read and what the page said where it was
  read, captured at extraction time. This is the verifier's input; it exists so
  verification consumes raw evidence rather than the executor's conclusion.
  `body_len` is the length of the real page (`body`) the value was read from —
  distinct from `len(page_text)`, since `page_text` is a bounded evidence
  window (capped at `PAGE_TEXT_KEEP`, and doubled when a distant identity
  anchor forces a second window onto it). `verify()`'s `not_a_dump` check
  prefers `body_len` as its denominator and falls back to `len(page_text)`
  when it is absent — every record in the frozen M7 hand-labeled sample
  (`evals/labels/verifier-sample.jsonl`) predates this field and always takes
  the fallback (case `verifier-dump-ratio-anchor-flip`).
- `partial` — only for enumerable multi-item tasks: `answer` holds the correct
  subset, `reason` states what is missing. Honesty note: no code path produces
  `partial` yet. It was scheduled for M2 with OutcomeVerifier L2 and did not
  land: L2 compares a whole answer against ground truth, and nothing in the
  B-floor task set enumerates a set whose *subset* is meaningfully correct.
  Until a case demands it, incomplete enumerations surface as failures, never
  as quiet successes.

## TraceStep

One record per attempted step; the trace is complete (every action attempted
appears, in order — no post-hoc reconstruction).

```json
{
  "i": 1,
  "action": "navigate | click | fill | extract | extract_all | observe | select_option | scroll | press | wait_for | go_back | click_at | final_answer",
  "target": {"role": "...", "name": "...", "text": "...", "near": "...", "index": 0} ,
  "value": "string | null",
  "anchor": "string | null",
  "rank": "true | false | null",
  "resolved": {"tier": "role|text|attrs|structural", "description": "...", "scope": "url"} ,
  "expected_state": {"url_contains": "..."} ,
  "postcondition_ok": true,
  "failure_class": null,
  "note": null,
  "retry_or_recovery": null,
  "superseded_by": null,
  "page_changed": null,
  "screenshot": "step_1.png",
  "ms": 0
}
```

- **The action vocabulary is the same in both execution modes** (see *Modes*
  below), because they share one executor. `navigate`, `click`, `fill`,
  `extract`, `extract_all` and `observe` are M1-M32's; ADR-028 adds five verbs
  and one terminal call:
  - `select_option` — choose an option of a `<select>` by its visible label or
    its value. Self-verifying: the options are read, one is chosen by value, and
    the selection is read back. A `value` no option matches is `failure:act`
    naming the options that exist; an element with no options at all is
    `failure:locate`, the same ruling `fill` gets for an element that cannot
    hold a value.
  - `scroll` — `value` pixels (negative scrolls up), or with a `target`, bring
    that element into view. Self-verifying: the scroll position must have moved,
    or the target must be visible after it. A scroll that moved nothing is
    `failure:act`, never a silent no-op the next step reads through.
  - `press` — one key to the target, or to the page when no target is given.
    Changes state like a click and carries a click's obligation.
  - `wait_for` — wait until an `expected_state` holds, within the same settle
    budget a postcondition gets. It performs nothing: the postcondition IS the
    wait. A `wait_for` with no `expected_state` is `failure:task` — a wait with
    no predicate is a sleep.
  - `go_back` — one entry back in the tab's history. No history to return to is
    `failure:act`.
  - `click_at` (ADR-035, M43) — click at `value` = `"x,y"` viewport CSS pixels,
    no `target`, for the element no tier can name. CLOSED-WORLD about where the
    coordinates came from (the same ruling unknown target keys get): refused at
    tool-call time — `failure:task`, recorded as a refused step, reason back to
    the model — unless the call was emitted from an observation bearing a
    **viewport** screenshot. A drill's element-scoped image does not arm it
    (the gate reads the frame LABEL — provenance, not origin arithmetic:
    ADR-035 Decision 2), and mode B never arms it (its planning
    observation carries no screenshot). Malformed coordinates are
    `failure:task`; out-of-viewport coordinates are not pre-checked — nothing
    is there and the authored `expected_state` fails the step, `click`'s own
    ruling. Changes state like a click and carries a click's obligation.
  - `final_answer` — loop mode's terminal call. It carries **no answer text**:
    the answer is assembled in code from what was `extract`ed, exactly as in
    mode B, so a model can never assert a value the verifier did not grade.
    A `final_answer` with nothing extracted is INV-0's empty answer.
- `postcondition_ok` is **true / false / null**, and null is not true: it means
  nothing was verified about this step. Every key in `expected_state` must
  hold. `text_visible` and `role_visible` are checked **in the frame the
  action touched** (ADR-036): the one `resolve` returned the target from
  (`resolved.scope`), or the main document for a step that resolved no target —
  so a decoy iframe cannot earn a click's postcondition. A FRAME, not a
  document: if the page re-navigates that same frame in place, the predicates
  are read in the successor document and that guarantee does not hold
  (ADR-036 §4's declared limit, T-M42-14). `url_contains` is
  page-level by nature, and the whole `expected_state` of `navigate`,
  `go_back` and `wait_for` stays page-wide, every frame: those actions have no
  single acted document, and a wait for a page that paints into an iframe
  legitimately wants the frame. An acted document that is GONE — a frame
  detached while its own step ran, by that step or by the page's own re-render —
  makes the postcondition **null**: not false, which would accuse an action
  that may have worked, and not page-wide, which let a decoy iframe verify a
  no-op whose frame the page detached on a timer (ADR-036 §4, PR #66 R6).
  A **state-changing** step with a null postcondition is unverifiable and
  the run is `failure:semantic`; the set is `{click, press, go_back, click_at}`
  (`verifier.STATE_CHANGING`). `fill`, `select_option` and `scroll` verify
  themselves by reading back what the browser holds and need no authored
  postcondition; `navigate` is excluded because its consequence is the URL it
  was handed.
- `resolved.tier` is the tier the winning locator is *attributed* to, which is
  the tier that found it in every case but two: a target carrying `near` is
  recorded as `structural` however its candidates were gathered, because
  proximity is what identified the element — and so is one narrowed by its
  identity anchor, which is proximity by another name (M38, `ADR-026`; which
  rung fired is named in the step's `note`). The self-maintenance metric reads
  this field.
  `role`, `text` and `structural` are reachable; `attrs` is named
  here because the taxonomy defines the full ladder, and no run has ever
  emitted it. `structural` became reachable at M6 with `near` (below) and is
  still not a relocation rung: the ladder climbs between `role` and `text`
  only. That is *not* why two of the three mutations pass without recovering
  anything — the reason for that is that no plan was standing on the tiers they
  break (ADR-003).
  `resolved.scope` (ADR-036, amending ADR-028 §7) is the URL of the document
  the winning locator lives in — the main document's URL, or a frame's. It is
  what scopes the step's own postcondition, and it is the record T-M42-14's
  "a frame the step touched vs a frame that moved on its own" comparison is
  specified to consume. Written by the one resolver both modes share; a step
  that resolves nothing keeps `resolved: null`.
- **Modes** (ADR-027, ADR-028). `run_task` takes `mode`, selected per task by
  `POST /tasks`'s `mode` field and defaulting to `BROWSER_AGENT_MODE`, itself
  defaulting to `plan`.
  - `plan` (mode B, the default and the only mode any offline suite exercises
    end to end for planning quality) — one planning call over a condensed
    observation, then deterministic execution, with observe/replan as the
    recovery path. Everything else in this document describes it.
  - `loop` — a driver is called after EVERY action with a fresh observation, the
    trace so far and what has been extracted, and returns exactly one tool call.
    Each loop observation also carries the viewport screenshot that is already
    the trace's step evidence (the same `step_N.png`, by filename — ADR-035;
    the pre-plan navigate gets one as the loop starts, filling its existing
    `screenshot` field), and a drill observation carries an element-scoped
    `step_N_element.png` beside it — a viewport shot CLIPPED to the element's
    box, never an element screenshot, because that one scrolls and an
    observation must not move the page (`loop-drill-capture-does-not-scroll-the-page`);
    an element wholly outside the viewport simply gets no crop.
    `live_driver` sends the image as a
    data-URL content part. The trace schema is unchanged by all of this.
    It replaces the planning **cadence** and nothing else: the same executor
    actions, the same resolver, **the same TraceStep with no additional fields**,
    the same answer assembly, the same verifier and the same judge
    (`contract-trace-schema-loop-mode` is what keeps that true). Its budgets are
    its own (`agent.LOOP_BUDGETS`: actions, tokens AND USD) and exhausting any
    of them is INV-3's loud stop.
  - Two rules that mode B enforces at plan adoption have no adoption point in a
    loop and are re-homed rather than lost (ADR-027 Decision 5): an
    extraction targeting the accessibility document root is refused **as the
    call is emitted** — recorded as a refused step, never executed, the reason
    returned to the model — and the aggregate single-read rule is applied at
    **answer assembly** over the executed trace. Both are the same functions
    mode B uses (`agent.root_target_gap`, `agent.plan_gap`), asked at a second
    anchor.
  - `escalate` (M46, ADR-037) — a POLICY over the other two, not a third
    cadence: mode B runs once, and only if that leg ends in a `failure:<class>`
    **and attempted no state-changing action** does the same task re-run in loop
    mode, with the loop's opening note seeded by `agent.escalation_note`.
    ANY plan-leg step whose action is in `verifier.STATE_CHANGING` refuses the
    escalation, whatever its `postcondition_ok` — that field is a verification
    outcome, not an execution fact, so `false` ("the predicate did not hold")
    and `null` ("nobody checked") are both compatible with the action having
    taken full effect (ADR-037 Decision 2a). The run then carries the plan leg's
    own failure and one `legs` entry, and `reason` says which step and which
    verb stopped it. No new status class: nothing new failed. That note carries four facts and nothing else —
    the failure class, the dying step's index, its action verb and its target
    KEY NAMES, each from a closed vocabulary — so no page text, target value or
    error string crosses between legs (rule 6 and the injection boundary in one
    clause). Both legs need their own factory (`planner` AND `driver`, refused
    otherwise), each spends its OWN mode's budgets, the traces concatenate into
    one run under supersede semantics (`legs` above), and the verifier and the
    judge run in the legs' own `finalize`, once per leg that reaches an answer:
    the RunResult's verdict is the final leg's, and a plan leg the judge
    rejected has already spent its own single boundary call, which the summed
    `judge_calls` reports. `unsupported` does not
    escalate: `screen()` refuses identically at the top of both legs.
  - A failed call does not end a loop run: the model is told what happened and
    chooses again. What bounds that is the budgets and the no-progress harness —
    arriving at the same `(URL, page signature)` state `LOOP_REVISIT_CAP` times
    with nothing new extracted forces a strategy change, and the arrival after
    that ends the run `failure:env` naming no-progress as the reason.
- The five keys above are the **whole** target schema. A key outside it is a
  plan the executor cannot honour and stops the run as `failure:task`. It used
  to be dropped, and the step ran against whatever was left of the target —
  a plan quietly reinterpreted and a result reported for the weaker task that
  actually ran (`resolver-unknown-target-key`).
- `observe` (M32, `ADR-020`) is the drill-down: its `target` names a container
  the planner was already shown, and the executor re-runs the observation
  scoped to that element — the whole `MAX_ELEMS` budget spent inside the
  subtree, and a 1,500-character text head instead of 300. The result reaches
  the planner as the `observation` argument of the next planning call, with a
  `note` saying which target was drilled; there is no second channel and no
  second observation format. It reads the page and changes nothing, so like
  `extract` it carries no `expected_state`, records `page_changed: null`, and
  never wears `retry_or_recovery: "recovery"` and never consumes a pending
  `superseded_by` pointer — it replaces nothing and recovers nothing, and it
  produces no answer either, so counting it as a rung inflates a published
  metric with an attempt that could not have saved anything. Both skip PAST an
  `observe` and land on the next attempt of any other kind, which is usually
  the `extract` the drill-down was asked for: an `extract` is read-only too,
  but it is the attempt that completes a recovery, and `recovery-replan-
  postcondition` is the shape where it is the ONLY step the new plan has
  (`recovery-label-lands-on-the-extract` pins where the label lands). An
  `expected_state` on an `observe` step is refused as `failure:task`: there is
  nothing for it to assert (`observe-step-cannot-carry-expected-state`). In **mode B** it
  spends one call from the existing `MAX_REPLANS` budget and adds no budget of
  its own, so the per-run call ceiling is unchanged; in **loop mode** there is no
  replan to spend, so the drill-down is a tool call like any other and spends the
  STEP budget — ADR-027 Decision 5's amendment to ADR-020, confined to that mode
  and graded by `loop-observe-drills-into-a-container`, which also pins that the
  subtree is actually disclosed and said to be a subtree. A refused drill-down —
  budget exhausted, or a replan that returned nothing usable — ends the run as
  `failure:env` naming the target that was asked for; it never falls through to
  the steps the plan put after the `observe`, because those were written
  against the observation the drill-down asked to replace
  (`observe-refused-drilldown-stops-the-run`,
  `observe-drilldown-no-progress-stops-the-run`). A plan that reaches an
  `extract` with no page-changing step before it — leading `observe` steps do
  not count as one — is refused by both replan paths while a failed action that
  changed nothing is outstanding, and the run ends as that action's failure
  (`observe-cannot-launder-noop-action`,
  `observe-drilldown-cannot-launder-noop-action`).
- `target.index` (0-based) selects the k-th match instead of requiring
  uniqueness — "the first search result" is a browsing primitive, not site
  knowledge. Without it, several matches remain a loud `locate` failure.
- `target.near` resolves the same ambiguity semantically: among a tier's
  matches, take the one closest **in document order** to a visible anchor
  string, never the anchor's own element (`near-excludes-its-own-anchor`). It
  is what reaches a value whose only identity is the label beside it — a price
  in a spec table, the submitter in a Hacker News subline — and it wins as tier
  `structural`, because proximity is a relation between elements rather than a
  property of one. Document order, not pixels: a subline's bounding box
  contains every link inside it, so layout distance ties exactly where `near`
  is needed most.
  `near` and `index` are alternative answers to the same question; when a plan
  carries both, `near` decides. Both are *intent*, not tier, so a relocation
  rung carries them forward — a rung that dropped `near` answered an easier
  question than the one that failed and reported success for it
  (`relocation-preserves-near`).

  Proximity refuses rather than guesses, twice over. The anchor is matched
  exactly if any element matches exactly and by substring otherwise, keeping
  only the deepest matches; two matches that do not contain one another mean
  the anchor names two places on the page, and the run fails `locate`
  (`near-anchor-substring`). Two candidates equidistant from the anchor mean
  the plan did not identify an element, and the run fails `locate` rather than
  breaking the tie (`near-equidistant-is-ambiguous`). A candidate that *wraps*
  the anchor outranks every neighbour — that is the row or card the value sits
  in (`near-prefers-the-container`) — and only the anchor's own element is
  excluded outright.

  The anchor is matched through **four passes**, strictest first (M38,
  `ADR-026`): exact, substring, then a normalised pass that accepts typographic
  variants of quote/apostrophe/dash characters and collapses whitespace runs,
  then the same over the anchor's first 40 characters. The last two exist
  because `get_by_text` is a literal match and a model quoting a page back gets
  the typography and the length wrong, which is indistinguishable from a page
  that does not contain the anchor at all (`no tier resolved`, run `e6768ee0`;
  `resolver-near-normalises-typography`). Order is the honesty: the loosest
  match is only reached when every stricter one found nothing, and a loose
  match that names two places is refused exactly like a literal one.
- **Narrowing** (M38, `ADR-026`). N>1 matches at every tier is not always a
  question the plan failed to answer; often the page answers it. After every
  tier has had its chance at a *unique* match — a clean single match at a later
  tier still outranks any narrowing at an earlier one — two rungs are tried,
  and only on a step that READS and whose task asks for ONE thing: the step's
  identity `anchor` reused as a proximity anchor (winning as tier `structural`,
  for the same reason `near` does), and the first match in document order. On a
  `click`, a `fill` or an `observe` the ambiguity stays loud, because narrowing
  there would act on a control the plan did not uniquely name rather than read
  one of several identical values; on a plural ask it stays loud because one of
  several matches answers a different question — wrong by omission. Both tests
  gate all three rungs, including the loosened anchor passes inside `near`
  matching, which sit above the other two and were ungated for a round
  (`resolver-refuses-plural-with-anchor`,
  `resolver-refuses-plural-on-a-loose-anchor`,
  `resolver-refuses-a-click-on-a-loose-anchor`). `near`'s own exact and
  substring matching is NOT gated: an anchor the page contains is the proximity
  the plan asked for, and M6 shipped it available to every step. The
  document-order rung is refused further unless the plan carried no `index` and
  the matches are interchangeable — same role and same rendered text, so the
  choice cannot change the answer. Removing any one of those conjuncts turns
  exactly one case red, verified by ablating each over the whole suite
  (`resolver-refuses-mixed-roles` for the role half,
  `resolver-refuses-different-readings` for the text half,
  `resolver-refuses-narrowing-a-click` for the acting refusal, the plural
  family for the other), and everything not covered by the rungs stays the loud
  `locate` failure it was.
  The rung that fired is recorded in the step's `note` as
  `narrowed: <rung>` — a run that answered from one of several matches has to
  say which one it picked and why. It is NOT `retry_or_recovery: "recovery"`:
  narrowing happens inside a single resolution, with nothing classified as a
  failure, nothing superseded and no ladder run, so labelling it would inflate
  the recovery metric with attempts that never failed (the ruling `ADR-020`
  made for the drill-down and `ADR-018` for the lint note).
- `extract_all` reads **every** match of its target instead of requiring the
  target to identify one element, and contributes a list to `answer`. It is the
  comparison primitive the vocabulary lacked: "which author has the most
  quotes", "the cheapest one" cannot be answered by reading a single element,
  and before M31 the planner had no way to express the enumeration those
  questions rank over (M10 probe #3, `live-books-cheapest-travel`). Two rules
  follow from where the comparison happens:
  - **`extract_all` MUST carry `rank`** — `true` if the answer is the one item
    the task ranks for, `false` if the answer is the enumeration itself. A step
    that omits it is a plan the executor cannot honour and stops the run as
    `failure:task` (`extract-all-undeclared-intent-fails-loud`). It is the one
    thing code cannot read off the page or the plan's shape, and three attempts
    to infer it from the task text each published a raw enumeration as the
    answer to a single-answer question (PR #29 R2, R9, R16). The declaration is
    echoed into the TraceStep, so the decision has evidence behind it.
  - **the ranking is done in code, never by the model** (`verifier.rank`,
    called at answer assembly whenever the enumeration IS the whole answer):
    the plan says "one of these", never "this one". Code picks the one the
    task's superlative asks for — numbers compare as numbers, anything else
    compares by how often it occurs; `rank: true` with no ranking word in the
    task refuses rather than picking (`rank-reduces-enumeration-in-code`). The
    plan lint's `is_aggregate` shape is a different question and a different
    vocabulary — it excludes price wording, so a "cheapest" task is reduced but
    not linted (`extract-all-cheapest-wording-still-reduces`,
    T-CHEAPEST-WORDING). A tie is
    `failure:semantic`, not a coin flip, the same ruling `near` already makes
    (`near-equidistant-is-ambiguous`). A task with no ranking word keeps its
    list, which is a legitimate answer shape.
  - **a plan that should have enumerated and did not is rejected before the
    first action.** `agent.plan_gap` is a deterministic, site-agnostic lint
    that runs at every point the executor adopts a plan — the first plan, and
    again on the plan of record when either mid-run replanner returns one: the
    `act` ladder, and M32's drill-down. There are three, not two, and the third
    was adopted unlinted until `observe-drilldown-replan-is-linted` (PR #34
    R16); they now splice through a single `adopt()`, and
    `plan-adoption-is-the-only-steps-rebind` reads `agent.py` structurally and
    fails if any binding of `steps` after the first plan is not adopt-derived,
    so a fourth adoption point is red before it can run. That sentence was a
    modal promise resting on convention for one round (PR #34 R25) — the same
    shape as ADR-018's "that is the invariant, not the two call sites", which
    is what R16 falsified — and it is now enforced instead. An aggregate-shaped task (shared with
    the verifier's own guard through `verifier.is_aggregate` — one regex, two
    callers) whose extraction steps are not exactly one `extract_all` and
    nothing else is replanned once with a note naming the gap and stopped by
    the same no-progress rule as the `act` ladder. An accepted replan is
    charged to the same `replans` budget; a rejected one ends the run, so it
    bills tokens but no replan. It never executes
    twice (`verifier-aggregate-superlative-fails-loud`,
    `probe3-quotes-most-quoted-author`, `plan-gap-truth-table`,
    `specs/decisions/ADR-018-m31-plan-lint.md`).
    The same lint carries a second rule, which is about the TARGET and holds for
    every task shape rather than only the aggregate one: an `extract`/
    `extract_all` naming the accessibility document root (`WebArea` or
    `RootWebArea`) is refused, because that node's text is the
    whole page and its accessible name is the page title — the string `observe`
    puts first in every observation. It is checked above the `is_aggregate`
    early return, since the tasks that produce it are ordinary single-answer
    ones, and it is not a rule about containers in general: `observe` on the
    same target is M32's drill-down and is untouched (untouched is not
    functional — T-M40-2-5), ARIA `document` is not the root and is not refused,
    and any other container stays with `verify`'s calibrated `not_a_dump`
    (`plan-lint-refuses-a-document-root-extract`, `plan-gap-truth-table`,
    `specs/decisions/ADR-024-document-root-is-not-an-answer.md`).
  - **`index` and `near` are refused on this step**, because both select one of
    the matches the step exists to enumerate; honouring either would enumerate
    a single element and let the relaxed aggregate guard certify a single-shot
    read (`extract-all-refuses-a-selector`). A tie in the ranking, and an
    enumeration that is only partly numeric, are `failure:semantic` for the
    same reason `near` refuses an ambiguous anchor.
  Each enumerated value becomes its own `evidence.extractions` record, so
  `grounded` and `not_a_dump` judge an enumeration row by row rather than as
  one page-sized blob (`verifier-list-rows-not-a-dump`).
- `anchor` (extract steps) is the identity anchor: the distinguishing string of
  the entity the task names. If it is absent from the page the answer was read
  from, the run is `failure:semantic`. Two known limits, both with cases: it is
  a substring test, so a near-miss entity whose name contains the target's name
  passes (`trap-near-miss-entity`); and on an aggregate page — a listing, a
  search-results page — every candidate entity is in the page text, so the
  anchor is satisfied by the wrong answer too (`trap-search-not-executed`).
  Only ground-truth verification catches either, and a live run has none.
- `retry_or_recovery` — null for first attempts; `"retry"` for same-strategy
  re-attempts; `"recovery"` only when a classified failure led to a different
  strategy. The recovery metric counts only `"recovery"` steps by construction.
  Two ladders emit it (`docs/evals/scope-checkpoint.md`): a `locate` failure
  relocated at a different tier, and an `act` failure replanned from a fresh
  observation — on a replan the flag sits on the FIRST step of the new plan,
  the one that differs from what failed. No `"retry"` rung exists yet; when a
  wait rung is added it logs as `retry` and stays out of the recovery metric by
  construction, not by intention. M32's re-observe rung (`observe`, `ADR-020`)
  logs as neither: it is not a second attempt at anything, so it carries a note
  and no label at all — this sentence used to promise it would log as `retry`,
  and the drill-down falsified that in the same file that shipped it. M38's
  narrowing rungs (`ADR-026`) log as neither for the same reason and one more:
  they are not a second attempt at all, but part of the FIRST resolution of the
  step, so there is no earlier attempt for them to supersede. What they carry
  instead is a `note` naming the rung.
- `page_changed` — did this action change the page's text at all? `null` on
  `extract`/`extract_all` and `observe` (none of which change anything by
  definition) and on the
  pre-plan navigate.
  It exists for one decision: a replan may drop the step it replaces only when
  that step actually moved the page. Two runs can be identical in plan, trace
  and failure — a click that lands, a postcondition that never arrives, a
  replan that skips straight to extraction — and differ only in whether the
  click did anything. In one the replanner is correctly reading an
  already-sorted page; in the other it reports the pre-action answer as the
  result. Nothing about the plan separates them, so the page does
  (`evals/adversarial/replan-cannot-launder-noop-action.json` against its
  benign twin `recovery-replan-postcondition`). Known ceiling: whole-body text
  equality, so an action whose only effect is off-page or purely visual reads
  as no change and its replan is refused — loudly, in the safe direction.
- `superseded_by` — null, or the `i` of the attempt that replaced this one. A
  failed attempt stays in the trace forever; this field is what stops it from
  also failing the *run*, so that a recovered run can be graded PASS. The
  exemption is gated in the verifier: a supersede pointing at an attempt that
  is not in the trace is itself a FAIL, and the last attempt in a chain is
  never superseded, so its failure always counts
  (`evals/adversarial/verifier-superseded-not-a-loophole.json`).
- Screenshots are written per step into the run directory alongside
  `trace.jsonl` and `result.json`.

## Progress stream (gateway)

`GET /tasks/{run_id}/stream` is Server-Sent Events. Each `data:` line is one
JSON object, and there are exactly two kinds:

```json
{"event": "step", "step": TraceStep}
{"event": "done", "result": RunResult}
```

- **Every attempted step is emitted, in order, exactly once** — including the
  ones a recovery ladder later supersedes. The stream is the trace, not a
  highlight reel: a viewer that showed only the steps that worked would render
  a tidier run than the one that happened, and nothing else in the suite would
  go red for it (`evals/adversarial/stream-shows-every-step.json`).
- A `step` event is a snapshot at emission time, so it is *provisional* in one
  field: `superseded_by` is written when the replacement attempt is created,
  which is after the failed attempt was already sent. The `done` event carries
  the authoritative trace and the frontend re-renders from it.
- `done` is terminal and always arrives — including when the run never started
  (see below). A run that ends without one is a hung stream, not a quiet
  success.
- The stream is single-consumer: the queue is drained, so a second viewer or a
  reconnect sees only what is left plus `done`. `GET /tasks/{run_id}` remains
  the complete-result path.

**Every gateway result is a RunResult**, including the catch-all for a run that
raised before `run_task` was entered — the missing-API-key path builds one
through the same `assemble_result` a real run uses. It has an empty trace, which
is correct (the key is validated before a browser is launched, so nothing was
attempted) and is not the same thing as a missing `evidence` object
(`evals/adversarial/gateway-error-contract-shape.json`).

Per-step screenshots are served from `GET /runs/{run_id}/{step_N.png}`; both
path components are pattern-matched, so nothing else in a run directory —
`result.json`, `trace.jsonl`, `observation.json` — is reachable over HTTP.

## Invariants bound to this contract

- INV-0 (specs/000): never `success` with empty output — enforced at
  `assemble_result`, backed by `evals/adversarial/inv0-no-empty-success.json`.
- INV-1: exactly one failure class per non-success status —
  `evals/adversarial/inv1-one-failure-class.json`.
- INV-2: the verifier outranks the executor —
  `evals/adversarial/inv2-verifier-outranks-executor.json`.
- Every field above is checked against a real run by
  `evals/adversarial/contract-trace-schema.json` (invariant-tagged). This
  document is prose, and prose does not fail a build; that case is its
  executable half. Add a field here and the case goes red until the code emits
  it — which is how `anchor` was caught, specced and never emitted, inside the
  session that added it.
- INV-3: budget exhaustion is a loud classified failure —
  `evals/adversarial/inv3-budget-exhaustion-loud.json`, with the end-to-end half
  in `budget-replans-exhausted`.
- Remaining planned invariants, both listed in
  `docs/evals/evaluation-methodology.md` and neither in specs/000: *fast suite
  is offline* (the boundary is measured today — ADR-002 threshold 5 — but not
  invariant-tagged) and *traces are complete* (every action carries pre/post
  observation). Each enters specs/000 with its backing case, not before.
