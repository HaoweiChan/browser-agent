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
  }
}
```

- `model` — the planner model this run was built with, echoed so a run record is
  self-attributing. `null` where no named model planned it (the `fast` suite
  stubs the planner at the module boundary). Added at M9: the ablation submits a
  model and writes the answer into a committed report, and without an echo the
  attribution of every row is the driver's own assertion about a deployment that
  can redeploy mid-sweep (`specs/decisions/ADR-010-m9-model-ablation.md`
  Decision 13).
- `status` — `failure:<class>` uses exactly one of the 7 top-level classes in
  `docs/evals/failure-taxonomy.md` (nav, locate, act, extract, semantic, env,
  task). `unsupported` comes from pre-flight screening or mid-run discovery.
- `answer` — the user-facing result. **INV-0: `status` = `success` requires a
  non-empty `answer` AND a non-empty `evidence.trace`.** An empty extraction is
  `failure:extract`, never a quiet success.
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
  run, at this boundary, never per extraction. `judge_tokens`/`judge_usd` are
  0 for every stub (fast/live suites) and for a cache hit; only a live,
  uncached call spends either.
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
  "action": "navigate | click | fill | extract | extract_all",
  "target": {"role": "...", "name": "...", "text": "...", "near": "...", "index": 0} ,
  "value": "string | null",
  "anchor": "string | null",
  "rank": "true | false | null",
  "resolved": {"tier": "role|text|attrs|structural", "description": "..."} ,
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

- `postcondition_ok` is **true / false / null**, and null is not true: it means
  nothing was asserted about this step. Every key in `expected_state` must
  hold. A `click` with a null postcondition is unverifiable and the run is
  `failure:semantic`; a `fill` verifies itself by field readback and needs no
  authored postcondition.
- `resolved.tier` is the tier the winning locator is *attributed* to, which is
  the tier that found it in every case but one: a target carrying `near` is
  recorded as `structural` however its candidates were gathered, because
  proximity is what identified the element. The self-maintenance metric reads
  this field. `role`, `text` and `structural` are reachable; `attrs` is named
  here because the taxonomy defines the full ladder, and no run has ever
  emitted it. `structural` became reachable at M6 with `near` (below) and is
  still not a relocation rung: the ladder climbs between `role` and `text`
  only. That is *not* why two of the three mutations pass without recovering
  anything — the reason for that is that no plan was standing on the tiers they
  break (ADR-003).
- The five keys above are the **whole** target schema. A key outside it is a
  plan the executor cannot honour and stops the run as `failure:task`. It used
  to be dropped, and the step ran against whatever was left of the target —
  a plan quietly reinterpreted and a result reported for the weaker task that
  actually ran (`resolver-unknown-target-key`).
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
    again on the plan of record when the `act` ladder replans mid-run: an aggregate-shaped task (shared with
    the verifier's own guard through `verifier.is_aggregate` — one regex, two
    callers) whose extraction steps are not exactly one `extract_all` and
    nothing else is replanned once with a note naming the gap and stopped by
    the same no-progress rule as the `act` ladder. An accepted replan is
    charged to the same `replans` budget; a rejected one ends the run, so it
    bills tokens but no replan. It never executes
    twice (`verifier-aggregate-superlative-fails-loud`,
    `probe3-quotes-most-quoted-author`, `plan-gap-truth-table`,
    `specs/decisions/ADR-018-m31-plan-lint.md`).
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
  re-observe or wait rung is added it logs as `retry` and stays out of the
  recovery metric by construction, not by intention.
- `page_changed` — did this action change the page's text at all? `null` on
  `extract`/`extract_all` (which change nothing by definition) and on the
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
