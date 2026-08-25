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

20 cases red in the opening sweep (six more were added later and are below), plus 4 pre-existing documents-of-record cases
(`adr-header-and-index`, `docs-numbers-are-derived`, `opt-in-expect-keys-declared`,
`published-band-matches-the-ledger`) that redden by construction the moment a
case is added to the suite. Those four are the declared republish cost of
growing a suite in this repo, not defects; they are closed by the documentation
slice of this milestone.

## Leg 1 — the loop driver, tool schemas, offline evaluability

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `loop-drives-a-fetch-then-render-page` (golden) | `checks {status: false, verdict: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` — no loop driver existed, so `mode: "loop"` and `stub_calls` were ignored and the run produced nothing | `M42: loop mode` (the implementation commit) |
| `loop-token-ceiling-stops-the-run-loudly` | `checks {status: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | `M42: loop mode` (the implementation commit) |
| `loop-usd-ceiling-stops-the-run-loudly` | `checks {status: false, trace_actions: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | `M42: loop mode` (the implementation commit) |
| `contract-trace-schema-loop-mode` | `KeyError: 'stub_plan'` at `eval_adapter.py:1444` in `_run_schema_case` — the schema runner had no loop-mode path at all | `M42: loop mode` (the implementation commit) |
| `gateway-mode-selects-the-driver` | `wrong: [{want {http: 422, planner_model: null, detail: "mode must be one of"}, got {http: 200, planner_model: "openai/gpt-5.6-luna", detail: null}}]` — `POST /tasks` accepted `mode: "sideways"` and ran mode B | `M42: loop mode` (the implementation commit) |

## Leg 2 — the re-homed guards (ADR-027 Decision 5)

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `loop-refuses-a-document-root-extract` | `checks {status: false, verdict: false, trace_actions: false, trace_note_contains: false}`, `got.status "failure:extract"` — no tool-call-time refusal existed; ADR-024's guard has no adoption point in loop mode | `M42: loop mode` (the implementation commit) |
| `loop-aggregate-single-read-at-answer-assembly` | `checks {status: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` — ADR-018's aggregate rule has no adoption point in loop mode | `M42: loop mode` (the implementation commit) |
| `loop-aggregate-enumeration-is-accepted` (positive direction) | `checks {status: false, verdict: false}`, `got.status "failure:extract"` | `M42: loop mode` (the implementation commit) |

## Leg 3 — the widened action vocabulary (both modes)

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `action-select-option-verifies-by-readback` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` | `M42: loop mode` (the implementation commit) |
| `action-select-option-refuses-an-absent-option` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` — red for the wrong reason first (unknown verb); re-watched red with the verb present and the readback removed, see below | `M42: loop mode` (the implementation commit) |
| `action-scroll-moves-the-viewport` | `got.reason "step 2 (scroll): StepError: unknown action 'scroll'"` | `M42: loop mode` (the implementation commit) |
| `action-scroll-that-moves-nothing-is-loud` | `got.reason "step 2 (scroll): StepError: unknown action 'scroll'"` | `M42: loop mode` (the implementation commit) |
| `action-press-carries-a-postcondition` | `got.reason "step 3 (press): StepError: unknown action 'press'"` | `M42: loop mode` (the implementation commit) |
| `action-wait-for-reaches-a-late-predicate` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` | `M42: loop mode` (the implementation commit) |
| `action-wait-for-that-never-holds-is-loud` | `got.reason "step 2 (wait_for): StepError: unknown action 'wait_for'"` | `M42: loop mode` (the implementation commit) |
| `action-go-back-returns-to-the-previous-page` | `got.reason "step 3 (go_back): StepError: unknown action 'go_back'"` | `M42: loop mode` (the implementation commit) |
| `loop-mode-b-cannot-read-the-un-awaited-result` | `got.reason "step 2 (select_option): StepError: unknown action 'select_option'"` — the A/B twin needs the shared verb before it can fail for the RIGHT reason (`failure:extract` on an un-awaited paint) | `M42: loop mode` (the implementation commit) |

## Leg 4 — observation reach

| case | red observed (pre-implementation) | greened by |
|---|---|---|
| `observe-reaches-into-an-iframe` | `checks {status: false, verdict: false, planner_saw: false}`, `got.status "failure:locate"`, `reason "step 3 (extract): relocation after locate failure: retargeting as {'text': 'Inventory turnover'}; ResolveError: no tier resolved {'text': 'Inventory turnover'}"` | `M42: loop mode` (the implementation commit) |
| `shadow-dom-value-is-reachable-and-grounded` | `checks {status: false, verdict: false, trace_actions: false}`, `got.status "failure:act"`, `reason "step 2 (click): StepError: expected_state not reached: {'text_visible': 'Audit code'}; replan made no progress (identical or empty plan)"` | `M42: loop mode` (the implementation commit) |

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
| `loop-no-progress-revisit-ends-the-run-loudly` | `checks {status: false}`, `got.status "failure:extract"`, `reason "empty answer or empty trace"` | `M42: loop mode` (the implementation commit) |

## Leg 6 — the frontier model allowlist addition

| case | red observed | greened by |
|---|---|---|
| `gateway-model-reaches-planner` (extended with the loop-model rows) | see the row in the section below — the extension was written after the opening sweep | `M42: loop mode` (the implementation commit) |

## Written after the first sweep — same rule, same receipt

Two cases were not in the opening batch because the defects they pin were found
*during* implementation rather than designed up front. Both were still watched
red before the fix, and both reds are below.

| case | red observed | greened by |
|---|---|---|
| `loop-observe-drills-into-a-container` | `checks {status: true, verdict: true, trace_actions: true, planner_saw: false, budgets: true}` — and the shape of that row is the finding: the run **succeeded** with the right answer while the disclosure it depends on never happened. Instrumented directly, the driver's three turns were shown `elems=60 has_SN=False` / `elems=60 has_SN=False` / `elems=60 has_SN=False`; after the fix the second turn is `elems=27 has_SN=True`. `execute` was filling `drilled` and only mode B's branch ever popped it, so loop-mode `observe` was a silent no-op while its tool description promised the model "you are shown that subtree alone" | `M42: loop mode` (the implementation commit) |
| `gateway-model-reaches-planner` (extended) | `{"allowlisted_but_not_in_the_verified_snapshot": ["anthropic/claude-opus-5"], ...}` — the allowlist widened before the frozen evidence did, which is exactly the order ADR-027 forbids | `M42: loop mode` (the implementation commit) |

And one case went red as a *consequence* of the allowlist change, which is the
whole reason it exists:

| case | red observed | fixed by |
|---|---|---|
| `gateway-model-not-allowlisted` | `{model: anthropic/claude-opus-5, want {http: 422, planner_model: null, detail: "model blocked"}, got {http: 200, planner_model: "anthropic/claude-opus-5", detail: null}}` — the allowlist and its own refusal case disagreeing the moment the list moved | the refused-frontier-model row moved to `anthropic/claude-sonnet-5`; the row's point is unchanged |

## Two defects the new cases found in the new code

Recorded because "the eval set is the spec" is worth nothing if the cases only
ever confirm what the author already believed.

1. **The no-progress harness killed a working run.** `loop-drives-a-fetch-then-render-page`
   went red with `failure:env` / *"no progress: step 4 arrived at ... in the same
   page state for the 4th time"*. Selecting an option, clicking, and waiting for
   the result is three turns on one page whose observation barely moves — the
   first version counted TURNS and called that a circle. A visit is now an
   ARRIVAL. The case is golden rather than adversarial for exactly this reason.
2. **The ceiling cases put $99 on a $0.00 suite's headline.** Tripping the
   shipped 400,000-token / $5.00 caps by scripting 500,000 tokens and $99 of stub
   usage worked, and made the `fast` suite report
   `cost $99.0000 · 500010 tok` — the number README publishes and
   `docs-numbers-are-derived` recomputes. Runaway protection that can only be
   exercised by actually running away is protection nothing checks, so the caps
   became injectable and the cases now trip 1 token and $0.000001.

## The review round — six more cases, all watched red

`cold-reviewer` and `spec-drift` ran over the diff before the milestone was
final. Between them they found five defects that are **one** defect wearing five
faces, and it is the defect a second execution mode was always going to have:

> mode B ends the run at the first failed step, so a failed step's side effects
> never outlived it. Loop mode makes a failed call routine, and every guard
> written under "the run dies here" had to be re-read.

Each finding became a case, each case was watched red, and three of the five
reds are **wrong-success** — the property ADR-027 says the mandate does not
reach.

| case | red observed | greened by |
|---|---|---|
| `loop-refused-anchor-is-not-an-answer` | `status "success"`, `answer "Meridian Wall Clock"` — a value the executor had just REFUSED (`failure_class: "semantic"` on that same step, in the same trace). `execute` appended to `answers`/`extractions` before running the identity-anchor check | `M42: review-round repairs` |
| `loop-failed-enumeration-does-not-disarm-rank` | `status "success"`, `answer ["Aurora Desk Lamp $39.00", "Aurora Desk Lamp Pro $59.00", "Meridian Wall Clock $24.50", "Cobalt Floor Rug $18.00"]` — the raw unranked candidate list answering a which-one question, verdict PASS. ADR-018's own defect family, through a path none of its guards cover | `M42: review-round repairs` |
| `extract-all-refuses-matches-in-two-documents` | `status "success"`, `answer ["NBX-7741"]` — one row of three, because frame-scoped resolution returned the first document with any match. Wrong by omission, and `grounded` cannot see it now that `page_text` concatenates frames | `M42: review-round repairs` |
| `loop-recovered-failure-still-verifies` | `status "failure:semantic"`, `reason "verifier FAIL: a step's postcondition was not reached"` — the mirror image: a run that clicked with a wrong expectation, was told, and then read the right answer, demoted for the attempt it recovered FROM | `M42: review-round repairs` |
| `loop-observe-drills-into-a-container` | `planner_saw: false` while `status`, `verdict` and `trace_actions` were all green — the run succeeded with the right answer while the disclosure it depends on never happened (see the section above) | `M42: loop mode` |
| `driver-tools-match-the-executor` | `unknown invariant check driver-tools-match-the-executor` — a comment in `planner.py` asserted this case "reads both and reddens if they disagree", and the case existed nowhere in the tree. Re-watched red by ablation after the check was written: removing `go_back` from `TOOL_TABLE` gives `{"only_the_executor_implements": ["go_back"]}` plus the schema-name mismatch | `M42: review-round repairs` |

Three more cases changed as consequences of those fixes, each red first:

| case | red observed | why |
|---|---|---|
| `contract-trace-schema` / `contract-trace-schema-loop-mode` | `{"result": {"missing": ["mode"], "extra": []}}` on both | a run record could not say which cadence produced it, and comparing the two modes from committed run records is M44's entire job |
| `gateway-mode-selects-the-driver` | `want planner_model "anthropic/claude-opus-5", got "openai/gpt-5.6-luna"` | loop mode drove the frontier-model loop with the model ADR-010's COST ablation picked — `DEFAULT_LOOP_MODEL` was documented as the loop's default and dead in production |
| `gateway-error-contract-shape` | `result` keys missing `mode` | the shape of a run that never got off the ground is where the field matters most: there is no trace to infer the mode from |

### The one that went green for the wrong reason

`loop-refused-anchor-is-not-an-answer` was first written against a link name
`shop.html` does not carry, so it passed on a `locate` failure without ever
reaching the ordering it exists to pin. Recorded because it is the failure mode
this whole file exists to prevent: a green case proves nothing until you know
why it is green, and the same is true of a red one.
