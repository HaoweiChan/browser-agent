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
  "evidence": {
    "trace": [ TraceStep, ... ],
    "screenshots": ["step_1.png", ...],
    "final_url": "string | null",
    "final_page_digest": "first ~500 chars of page text | null"
  },
  "budgets_spent": {
    "actions": 0,
    "llm_tokens": 0,
    "llm_usd": 0.0,
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
- `partial` — only for enumerable multi-item tasks: `answer` holds the correct
  subset, `reason` states what is missing.

## TraceStep

One record per attempted step; the trace is complete (every action attempted
appears, in order — no post-hoc reconstruction).

```json
{
  "i": 1,
  "action": "navigate | click | fill | extract",
  "target": {"role": "...", "name": "...", "text": "...", "near": "..."} ,
  "value": "string | null",
  "resolved": {"tier": "role|text|attrs|structural", "description": "..."} ,
  "expected_state": {"url_contains": "..."} ,
  "postcondition_ok": true,
  "failure_class": null,
  "note": null,
  "retry_or_recovery": null,
  "screenshot": "step_1.png",
  "ms": 0
}
```

- `resolved.tier` is the locator tier that won — the self-maintenance metric
  reads this field.
- `retry_or_recovery` — null for first attempts; `"retry"` for same-strategy
  re-attempts; `"recovery"` only when a classified failure led to a different
  strategy (M3). The recovery metric counts only `"recovery"` steps by
  construction.
- Screenshots are written per step into the run directory alongside
  `trace.jsonl` and `result.json`.

## Invariants bound to this contract

- INV-0 (specs/000): never `success` with empty output — enforced at
  `assemble_result`, backed by `evals/adversarial/inv0-no-empty-success.json`.
- Future invariants (budgets-enforced, trace-complete, one-class-per-failure)
  enter specs/000 with their backing cases as the features land (M2–M3).
