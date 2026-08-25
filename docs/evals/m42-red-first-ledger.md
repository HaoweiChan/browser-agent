# M42 red-first ledger

CLAUDE.md hard rule 2: *"an eval you've never seen red proves nothing."* This
file is the receipt. One row per case M42 adds: the case id, the red line
actually observed against the tree **before** the implementation existed, and
the commit that turned it green.

Reds were captured by running the named case ids against the pre-implementation
tree with the repo's own runner (`evals.run.load_cases` + `run_case`) on a probe
path that deliberately writes no row to `evals/report/history.jsonl` — the
T-M38-5 practice: probe runs stay out of the committed ledger.

The whole-suite red at that point, for context:

```
[eval] REGRESSION: 0.881 < baseline 1.000
[eval] suite 'fast': 177/201 = 0.881
```

20 new cases red, plus 4 pre-existing documents-of-record cases
(`adr-header-and-index`, `docs-numbers-are-derived`, `opt-in-expect-keys-declared`,
`published-band-matches-the-ledger`) that redden by construction the moment a
case is added to the suite. Those four are the declared republish cost of
growing a suite in this repo, not defects; they are closed by the documentation
slice of this milestone.

## Leg 1 — the loop driver, tool schemas, offline evaluability

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `loop-drives-a-fetch-then-render-page` (golden) | `checks {status: false, verdict: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` — no loop driver existed, so `mode: "loop"` and `stub_calls` were ignored and the run produced nothing | _pending_ |
| `loop-token-ceiling-stops-the-run-loudly` | `checks {status: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | _pending_ |
| `loop-usd-ceiling-stops-the-run-loudly` | `checks {status: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | _pending_ |
| `contract-trace-schema-loop-mode` | `KeyError: 'stub_plan'` at `eval_adapter.py:1444` in `_run_schema_case` — the schema runner had no loop-mode path at all | _pending_ |
| `gateway-mode-selects-the-driver` | `wrong: [{want {http: 422, planner_model: null, detail: "mode must be one of"}, got {http: 200, planner_model: "openai/gpt-5.6-luna", detail: null}}]` — `POST /tasks` accepted `mode: "sideways"` and ran mode B | _pending_ |

## Leg 2 — the re-homed guards (ADR-027 Decision 5)

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `loop-refuses-a-document-root-extract` | `checks {status: false, verdict: false, trace_actions: false, trace_note_contains: false}`, `got.status "failure:extract"` — no tool-call-time refusal existed; ADR-024's guard has no adoption point in loop mode | _pending_ |
| `loop-aggregate-single-read-at-answer-assembly` | `checks {status: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` — ADR-018's aggregate rule has no adoption point in loop mode | _pending_ |
| `loop-aggregate-enumeration-is-accepted` (positive direction) | `checks {status: false, verdict: false}`, `got.status "failure:extract"` | _pending_ |

## Leg 3 — the widened action vocabulary (both modes)

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `action-select-option-verifies-by-readback` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` | _pending_ |
| `action-select-option-refuses-an-absent-option` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` — red for the wrong reason first (unknown verb); re-watched red with the verb present and the readback removed, see below | _pending_ |
| `action-scroll-moves-the-viewport` | `got.reason "step 2 (scroll): StepError: unknown action 'scroll'"` | _pending_ |
| `action-scroll-that-moves-nothing-is-loud` | `got.reason "step 2 (scroll): StepError: unknown action 'scroll'"` | _pending_ |
| `action-press-carries-a-postcondition` | `got.reason "step 3 (press): StepError: unknown action 'press'"` | _pending_ |
| `action-wait-for-reaches-a-late-predicate` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` | _pending_ |
| `action-wait-for-that-never-holds-is-loud` | `got.reason "step 2 (wait_for): StepError: unknown action 'wait_for'"` | _pending_ |
| `action-go-back-returns-to-the-previous-page` | `got.reason "step 3 (go_back): StepError: unknown action 'go_back'"` | _pending_ |
| `loop-mode-b-cannot-read-the-un-awaited-result` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` — the A/B twin needs the shared verb before it can fail for the RIGHT reason (`failure:extract` on an un-awaited paint) | _pending_ |

## Leg 4 — observation reach

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `observe-reaches-into-an-iframe` | `checks {status: false, verdict: false, planner_saw: false}`, `got.status "failure:locate"`, `reason "step 3 (extract): relocation after locate failure: retargeting as {'text': 'Inventory turnover'}; ResolveError: no tier resolved {'text': 'Inventory turnover'}"` | _pending_ |
| `shadow-dom-value-is-reachable-and-grounded` | `checks {status: false, verdict: false, trace_actions: false}`, `got.status "failure:act"`, `reason "step 2 (click): StepError: expected_state not reached: {'text_visible': 'Audit code'}; replan made no progress (identical or empty plan)"` | _pending_ |

Direct measurement behind these two, taken on `fixtures/frames-host.html` before
any change (throwaway probe script, not a committed case):

```
ELEMENTS: WebArea / heading / Iframe "Source pane" / heading / button "Reveal audit code"
RESOLVE {'role': 'status', 'name': 'Document identifier'} -> FAIL ResolveError no tier resolved
RESOLVE {'role': 'button',  'name': 'Reveal audit code'}  -> role  'Reveal audit code'
shadow value read: 'NBX-7741'    value in body inner_text? False
page.accessibility.snapshot(root=<handle in child frame>) -> None
```

It corrected the milestone's own premise. An **open shadow root is already in
the accessibility tree and already resolvable** — the blind layer there is the
EVIDENCE pipeline (`page.inner_text("body")` does not traverse shadow roots),
not observation or resolution. The iframe half was blind in all three.

## Leg 5 — no-progress harness

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `loop-no-progress-revisit-ends-the-run-loudly` | `checks {status: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | _pending_ |

## Leg 6 — the frontier model allowlist addition

| case | red observed | greened by |
|---|---|---|
| `gateway-model-reaches-planner` (extended with the loop-model rows) | _pending_ | _pending_ |
