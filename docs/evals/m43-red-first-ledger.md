# M43 red-first ledger

CLAUDE.md hard rule 2: *"an eval you've never seen red proves nothing."* This
file is the receipt for the seven cases M43 adds.

## How this evidence was produced — read this before the tables

**Reconstructed post-hoc on 2026-08-28, not captured in-session while the cases
were being written.** M43's implementing session was killed mid-flight by an API
session limit, and whatever it observed while writing these cases died with it.
The ADR and all seven case files were already citing this ledger by name before
the file existed, which is a citation to nothing — so the evidence was rebuilt
for real rather than the citation quietly dropped.

The rebuild, exactly:

1. The seven cases, the fixture (`src/browser/fixtures/s2-nameless-readout.html`),
   the specs and the eval-adapter graders were left in place.
2. The four production modules M43 changes — `src/browser/agent.py`,
   `observe.py`, `planner.py`, `verifier.py` — were replaced with
   `origin/main`'s versions (`git checkout origin/main -- …`) at merge base
   `6089850`. That is the tree as it was *before* the implementation, with the
   cases already written against it.
3. Each case was run through `src/browser/eval_adapter.run_case` on a probe path
   that writes no row to `evals/report/history.jsonl` (T-M38-5: probe runs stay
   out of the committed ledger). The `red observed` column below is that run's
   own output, copied, not paraphrased.
4. The four modules were restored and the same seven cases re-run: 7/7 green.

**What this therefore does and does not prove.** It proves each case
DISCRIMINATES: it is red on the tree without M43's implementation and green with
it, so none of the seven is a case that would pass against anything. It does
**not** prove the stronger thing rule 2 asks for — that each case was watched red
at the moment it was written, before its fix was in hand. That evidence is gone.
No claim is made here that it exists.

`s2-bare-value-mode-b-root-reach-is-pinned` did **not** go red in step 3. That is
a finding, it is recorded as one below, and it is not papered over.

## The six that were red without the implementation

Tree: `origin/main` @ `6089850` for `agent.py` / `observe.py` / `planner.py` /
`verifier.py`; everything else as this branch has it.

| case | red observed (implementation reverted) | greened by |
|---|---|---|
| `loop-observation-carries-the-step-screenshot` (golden) | `checks {status: true, verdict: true, trace_actions: true, trace_screenshots: false, driver_screenshots: false}`, `got {status: "success", answer: "Hello Fixture"}` — the run still succeeds on ARIA alone (M42's behaviour), and that is the point: both screenshot conjuncts are red while nothing else is. No observation carried an image and the pre-plan navigate's `screenshot` was still hardcoded null | ADR-035 Decision 1 |
| `loop-drill-observation-carries-an-element-screenshot` (golden) | `checks {status: true, verdict: true, trace_actions: true, driver_screenshots: false}`, `got {status: "success", answer: "SN-88231"}` — the drill re-observed the subtree (M42) but captured no element-scoped image, so the frame sequence the case asserts was absent | ADR-035 Decision 2 |
| `loop-click-at-resolves-and-records-coordinates` (golden) | `checks {status: false, verdict: false, trace_actions: true, trace_postconditions: false, trace_values: true}`, `got {status: "failure:extract", reason: "empty answer or empty trace"}` — the executor had no `click_at`, the control was never pressed and the readout never painted. Note `trace_values` is green here *on its own*: the coordinate string rides in the trace's existing `value` field, which a refused step records too, so that conjunct alone does not discriminate — the case is carried by `status` / `verdict` / `trace_postconditions` | ADR-035 Decision 4 |
| `s2-bare-value-loop-vision-path-answers` (golden) | `checks {status: false, verdict: false, trace_actions: true, driver_screenshots: false}`, `got {status: "failure:extract", reason: "empty answer or empty trace"}` — the S2 acceptance shape end to end: no screenshot, no coordinate click, so `7.41` is never painted and never read | ADR-035 Decisions 1+4 |
| `click-at-without-a-screenshot-is-refused` (adversarial) | `checks {status: true, trace_postconditions: true, reason_contains: false}`, `got {status: "failure:task", reason: "step 2 (click_at): StepError: unknown action 'click_at'"}` — red for the *wrong reason*, which is what makes it worth recording: the pre-implementation tree refuses the call because the verb does not exist, not because the closed-world gate held. `reason_contains` is the conjunct that separates the two, and it is the one that is red | ADR-035 Decision 4 |
| `loop-click-at-from-a-drill-observation-is-refused` (adversarial) | `checks {status: true, verdict: true, trace_actions: true, driver_note_contains: false, driver_screenshots: false, trace_note_contains: false}`, `got {status: "success", answer: "SN-88231"}` — the run reaches a success by another route while all three gate conjuncts are red: no element frame, no refusal, no note back to the model | ADR-035 Decision 2 |

## The seventh — green without the implementation, and why

`s2-bare-value-mode-b-root-reach-is-pinned` (adversarial) ran **green** against
the reverted tree: `checks {status: true, actions: true, reason_contains: true}`,
`got {status: "failure:task", reason: "plan rejected before execution: the plan
reads 'extract' targets 'WebArea', the accessibility root of the document …"}`.

That is the expected result, not a defect, and the case was not changed to
manufacture a red. It is the **contrast half** of the S2 pair (ADR-035 Decision
6): its whole job is to pin that mode B's documented failure on this fixture is
*unchanged* by M43. A control that went red before the implementation would be
asserting that M43 changes mode B, which is the opposite of the ruling it
enforces (`planner.SYSTEM` still advertises mode B's original six verbs; the
T-M42-1 ruling). The behaviour it pins — ADR-024's document-root lint — predates
this milestone, so reverting this milestone cannot move it.

A control still has to be shown non-vacuous, so it was watched red by **ablation**
instead, against the guard it actually pins. With `agent.root_target_gap`
stubbed to return `None` — ADR-024's lint disabled, everything else on the full
implementation tree — the case is red on all three conjuncts:

```
passed: false
checks: {"status": false, "actions": false, "reason_contains": false}
got:    {"status": "success", "answer": "Meter panel", "reason": null}
```

The ablated failure is the dangerous one and is why the control is worth its
runtime: the run reports **`success`** with the answer `"Meter panel"` — the page
title, read off the accessibility root — where ground truth is `7.41`. A wrong
answer delivered confidently is exactly the shape ADR-024's lint exists to refuse
and the shape the loop-side case of this pair claims to fix.

This ablation is the method the case's own `provenance` field already declared
("Watched red by ablation — `root_target_gap` disabled in `plan_gap` — since the
guard it pins predates it"). It had not actually been run. It has now.

## Confirmation

With the four production modules restored, all seven cases pass:

```
{'loop-observation-carries-the-step-screenshot': True,
 'loop-drill-observation-carries-an-element-screenshot': True,
 'loop-click-at-resolves-and-records-coordinates': True,
 's2-bare-value-loop-vision-path-answers': True,
 'click-at-without-a-screenshot-is-refused': True,
 'loop-click-at-from-a-drill-observation-is-refused': True,
 's2-bare-value-mode-b-root-reach-is-pinned': True}
```

## Declared republish cost

Adding seven cases to `fast` reddens the documents-of-record cases that read the
suite counts back — `published-band-matches-the-ledger` went red at
`{suite: fast, published_case_count: 229, actual: 236}` the moment the cases
landed on the rebased tree. That is the republish cost of growing a suite in
this repo (ADR-019 §2), not a defect, and it is closed by the band and
`ADR-029` numbers this milestone re-measures.

---

# Round 1 repairs (PR #70, 2026-08-28)

Two more cases, and unlike the seven above **these were watched red in-session,
as they were written, before the code that makes them green existed.** The
output below is each run's own, copied from the terminal, not paraphrased. Both
were run through `src/browser/eval_adapter.run_case` on the same probe path the
rebuild used, which writes no row to `evals/report/history.jsonl`.

## R3 — `postcondition-unverified-click-at`

The finding: `click_at`'s membership in `verifier.STATE_CHANGING` was pinned by
nothing. Deleting the string left the whole suite green, because every other
`click_at` case authors an `expected_state` and so is verified either way.
`press` and `go_back` were widened into that set by M42 *with* a behavioural
case each; `click_at` shipped without one.

The case is `loop-click-at-resolves-and-records-coordinates` minus its
`expected_state`, and nothing else — same fixture, same coordinates, same three
stub calls. The run is otherwise a success: the click lands, the readout paints
`7.41`, the extract grounds. It is failed anyway.

Red observed, with `"click_at"` deleted from `verifier.STATE_CHANGING`
(`STATE_CHANGING = {"click", "press", "go_back"}`):

```
=== postcondition-unverified-click-at: FAIL
  "checks": { "status": false, "trace_actions": true, "trace_postconditions": true },
  "audit": { "verdict": "PASS", "layer": 1,
             "checks": { ..., "actions_verified": true, ... }, "reason": null },
  "got": { "status": "success", "answer": "7.41", "reason": null }
```

Green with the string restored — the whole of the difference is
`actions_verified`:

```
=== postcondition-unverified-click-at: PASS
  "audit": { "verdict": "FAIL", "layer": 1,
             "checks": { ..., "actions_verified": false, ... },
             "reason": "answer is empty; state-changing step(s) [2] carried no
                        checkable postcondition" },
  "got": { "status": "failure:semantic", "answer": null,
           "reason": "verifier FAIL: state-changing step(s) [2] carried no
                      checkable postcondition" }
```

One honest note about that second block: the run's OWN reason names only the
unverified state change. `answer is empty` appears in the adapter's re-audit
because `assemble_result` nulls the answer of a verifier-rejected run before
the adapter re-verifies it — a consequence of the failure, not a second cause.
The trace records `extracted: 7.41` at step 3 either way.

## R1 — `loop-drill-capture-does-not-scroll-the-page`

The finding: a loop-mode drill's element-scoped capture used
`locator.screenshot()`, whose actionability check **scrolls the element into
view**. The harmlessness argument offered for it holds only for coordinate
frames. On a lazy-load or infinite-scroll page it fails: looking closer loads
content nobody acted for, and the run records that as a step that changed
nothing, because `observe` is in `agent.READ_ONLY_ACTIONS` so `page_changed`
stays null. An action classified read-only that produces a state change is the
shape this repo grades against, so the ruling was that the mechanism change is
not a substitute for a case. Both shipped.

New fixture `src/browser/fixtures/lazy-ledger.html`: a named status reading
`3 entries loaded`, 1400px of spacer, then an `Entry detail` region — and a
one-shot `scroll` listener that rewrites the status to `9 entries loaded`. The
drill target starts outside the 720px viewport; the step after it reads the
status.

Red observed, against the capture exactly as ADR-035 first shipped it
(`await loc.screenshot(...)`):

```
=== loop-drill-capture-does-not-scroll-the-page: FAIL
  "checks": { "status": true, "verdict": false, "trace_actions": true },
  "audit": { "verdict": "FAIL", "layer": 2, "ground_truth": true,
             "checks": { ..., "answer_matches": false },
             "reason": "answer '9 entries loaded' != expected '3 entries loaded'" },
  "got": { "status": "success", "answer": "9 entries loaded", "reason": null }
```

Note the shape of that red: `status: success`, every verifier check green, no
failed postcondition, no abandoned failure. The run reports a clean success and
answers the question wrong, because a read-only step moved the page. That is
precisely the failure mode the finding described, and it is why the declaration
in ADR-035 Decision 2 was not accepted as sufficient on its own.

Green after the capture became a viewport shot clipped to the element's box
(`page.screenshot(clip=...)`), which cannot move the page; an element lying
wholly outside the viewport now gets no crop at all, the same best-effort
degrade Decision 1 already takes when a capture fails. The four sibling cases
that grade the drill image were re-run against the new mechanism and are green
on the same assertions:

```
{'loop-drill-capture-does-not-scroll-the-page': True,
 'loop-drill-observation-carries-an-element-screenshot': True,
 'loop-observation-carries-the-step-screenshot': True,
 's2-bare-value-loop-vision-path-answers': True,
 'loop-click-at-from-a-drill-observation-is-refused': True}
```

## Republish cost, again

The two cases put `fast` at 238 and reddened the same three derived-number
checks the original seven did — `published-band-matches-the-ledger` at
`{published_case_count: 236, actual: 238, ledger_slowest_at_actual: 93.44}`,
`adr029-scope-matches-the-suites` at `236/236` vs `238/238`, and
`docs-numbers-are-derived` on the README and `docs/analysis.md` counts. Closed
by re-deriving, not by re-typing: ADR-013's rule over the ledger's slowest
238-case row gives 93.44 × 1.15 = 107.46 → **110**, the same ceiling the
seven-case tree derived. The rule produced the number; the count moved and the
answer did not.

---

# Round 2 repairs (PR #70, 2026-08-28)

Round 2's headline finding is about round 1: **the R1 repair introduced the
defect class R1 was about.** R1 replaced a capture that took a side effect
(`loc.screenshot()` scrolls) with one that took an unbounded wait
(`loc.bounding_box()` inherits Playwright's 30s default) — inside a block that
swallows every exception, so the wait would have been silent. A repair diff is
not safer for being small, and the two entries below are its falsification pass.

## R7 — the bound the repair dropped

Measured, not argued. Same locator, matching nothing, timed twice:

```
bounding_box() as shipped:                    30.0s  TimeoutError
bounding_box(timeout=SCREENSHOT_TIMEOUT_MS):   2.0s  TimeoutError
SCREENSHOT_TIMEOUT_MS = 2000
```

Both sibling captures in the same block already pass the constant; the one the
repair added did not. The comment ~300 lines below states the rule with its
receipts — 32s and 64s inside a suite ADR-002 budgets at 60s — and that
reasoning is now carried at this call site so the next edit does not undo it.

## R9 — the case pinned the answer and nothing else

`loop-drill-capture-does-not-scroll-the-page` asserted only that the answer was
`3 entries loaded`. That is red when the capture SCROLLS, and green for a build
that never emits a crop at all, and green for a build that emits one for an
off-screen element by some other means. The adapter already had the key, so the
case now also asserts `driver_screenshots: ["viewport", false, "viewport"]` —
the absent crop at the drill turn, and the viewport frames either side of it.

Watched red twice, on purpose, because the second red is the one that matters:

1. Against the original scrolling capture — `driver_screenshots: false` **and**
   `verdict: false`. Both conjuncts fire, which proves nothing about either.
2. Against a build that emits a crop for the off-screen element WITHOUT
   scrolling (`page.screenshot(full_page=True, clip=box)`), so the answer stays
   correct:

```
=== loop-drill-capture-does-not-scroll-the-page: FAIL
  "checks": { "status": true, "verdict": true, "trace_actions": true,
              "driver_screenshots": false }
```

`verdict: true`, `driver_screenshots: false` — the new conjunct discriminates on
its own rather than riding the answer. That is the property `M43-D1` records as
missing for `trace_values`, checked here before the case was called done.
