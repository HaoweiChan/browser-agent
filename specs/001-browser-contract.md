# Output contract — browser task

Every run of the browser agent — CLI, gateway, or eval adapter — returns exactly
this shape. The eval adapter and the frontend both consume it; drift here is
contract-drift (spec-drift audits field-by-field).

## RunResult

```json
{
  "status": "success | partial | failure:<class> | unsupported",
  "answer": "string | list | null",
  "reason": "string | null",
  "verdict": { "verdict": "PASS | FAIL | INCONCLUSIVE", "layer": 1,
               "ground_truth": false, "checks": {}, "reason": null },
  "evidence": {
    "trace": [ TraceStep, ... ],
    "screenshots": ["step_1.png", ...],
    "extractions": [ {"value": "...", "page_text": "≤2000 chars around the value"} ],
    "final_url": "string | null",
    "final_page_digest": "first ~500 chars of page text | null"
  },
  "budgets_spent": {
    "actions": 0,
    "llm_tokens": 0,
    "llm_usd": 0.0,
    "replans": 0,
    "ms": 0
  }
}
```

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
- `evidence.extractions` — what was read and what the page said where it was
  read, captured at extraction time. This is the verifier's input; it exists so
  verification consumes raw evidence rather than the executor's conclusion.
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
  "action": "navigate | click | fill | extract",
  "target": {"role": "...", "name": "...", "text": "...", "near": "...", "index": 0} ,
  "value": "string | null",
  "anchor": "string | null",
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
- `resolved.tier` is the locator tier that won — the self-maintenance metric
  reads this field. Only `role` and `text` are reachable today; `attrs` and
  `structural` are named here because the taxonomy defines the full ladder, and
  no run has ever emitted them. That is also why two of the three mutations
  pass without recovering anything (ADR-002).
- `target.index` (0-based) selects the k-th match instead of requiring
  uniqueness — "the first search result" is a browsing primitive, not site
  knowledge. Without it, several matches remain a loud `locate` failure.
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
  `extract` (which changes nothing by definition) and on the pre-plan navigate.
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
- Remaining planned invariant (fast-suite-is-offline) enters specs/000 with its
  backing case when it is written; the boundary is measured today (ADR-002
  threshold 5) but not yet invariant-tagged.
