# ADR-035: M43 — loop mode looks: a screenshot on every turn, an element-scoped drill image, and a coordinate click that is closed-world about what was seen

Date: 2026-08-28
Status: accepted

**Ruling**: in loop mode every observation handed to the driver carries the viewport screenshot that is already the trace's step evidence — the same `step_N.png` `attempt` writes, referenced by filename, never a second capture and never inline base64 — and the one step that had no capture of its own (the pre-plan navigate) gets one as the loop starts, filling its existing `screenshot` field; a loop-mode drill (`observe` with a target) additionally captures an element-scoped image (`step_N_element.png`) attached to the scoped observation it discloses; the executor gains `click_at` — `value` is `"x,y"` in viewport CSS pixels, no target, state-changing so it joins `verifier.STATE_CHANGING` — refused at tool-call time unless the call was emitted from an observation bearing a VIEWPORT screenshot (an element-scoped drill image does not arm it: the arm reads the frame LABEL, and a crop taken to show a sub-region is labelled `element` — Decision 2 on why that is provenance and not origin arithmetic); `live_driver` sends the image as a data-URL `image_url` content part beside the unchanged text prompt; and **no model is added**: ADR-028's `anthropic/claude-opus-5` is already vision-capable, so `ALLOWED_MODELS` does not move and ADR-027 Decision 4's amendment rule has nothing to amend. The nine cases this adds put `fast` at 238, whose slowest recorded run derives a ceiling of 110, so the local `fast` wall-clock ceiling moves 105 -> 110 (Decision 7).
**Because**: postmortem S2 — "the answer is not the accessible name of any small element" (T-M40-2, D28) — is structural to ARIA-first observation and unfixable by better targeting, and production agents do not have the failure class because they look; ADR-027 Decision 3 assigned the fix to this milestone. The closed-world gate exists for the same reason unknown target keys are refused: a coordinate the model never saw is a plan quietly invented, and the only evidence it could legitimately come from is a screenshot this run actually took and kept.
**Enforced by**: `loop-observation-carries-the-step-screenshot`, `loop-drill-observation-carries-an-element-screenshot`, `loop-click-at-resolves-and-records-coordinates`, `click-at-without-a-screenshot-is-refused`, `loop-click-at-from-a-drill-observation-is-refused`, `s2-bare-value-loop-vision-path-answers` with `s2-bare-value-mode-b-root-reach-is-pinned` as the contrast pair — reds reconstructed post-hoc in `docs/evals/m43-red-first-ledger.md`, which states in those words that they were rebuilt after a session interruption rather than watched as each case was written — plus PR #70's two repair cases, `postcondition-unverified-click-at` (Decision 4's `verifier.STATE_CHANGING` membership, which nothing pinned: deleting the string left the suite green) and `loop-drill-capture-does-not-scroll-the-page` (Decision 2's capture, which must not move the page), both of them watched red in-session and recorded in the same ledger's "Round 1 repairs" section, plus the extended `opt-in-expect-keys-declared`, and `driver-tools-match-the-executor` / `contract-trace-schema-loop-mode`, which redden if the tool table and the executor drift or the trace grows a field; Decision 7's ceiling by `published-band-matches-the-ledger` and `fast-wall-clock-budget`.
**Amends**: ADR-019 Decision 2 (local `fast` ceiling 105 -> 110), itself last amended by ADR-029

---

## Context

ADR-028 shipped the loop cadence and deliberately left vision to this
milestone. The failure class it closes is the postmortem's S2: the sec-10k
inspector's status banner is a bare `<div>`, its item text a bare `<pre>`, both
`generic` in the accessibility tree and dropped by `SKIP_ROLES` — an agent that
plans from roles and names reaches for the document root instead (T-M40-2
measured four of five live tasks doing exactly that). A model that can SEE the
page does not need the value to be anybody's accessible name.

## Decision 1 — the observation screenshot IS the step evidence, one file

`attempt` already captures `step_N.png` after every step, bounded by
`SCREENSHOT_TIMEOUT_MS`, and ADR-022's reviewer UI already renders it. The loop
takes a fresh observation at the same moment, so the screenshot that describes
the observation and the screenshot that evidences the step are the same page
state — and are now the same FILE: `drive_loop` attaches the latest trace
step's `screenshot` filename to the observation (`screenshot`), plus an
absolute `screenshot_path` so the driver — which is handed no run directory —
can read the bytes, and `screenshot_frame: "viewport"`. The pre-plan navigate
record hardcoded `screenshot: None`; in loop mode the loop's first turn
captures one and fills that existing field. Mode B's pre-plan record is
untouched — nothing in mode B consumes a screenshot, and its suites pin its
shape.

Two consequences, both deliberate:

* **The trace gains no fields** (ADR-028 §7 stands; `contract-trace-schema-loop-mode`
  still grades it). Screenshots enter the run record exactly where they always
  did — the step's `screenshot` field and `evidence.screenshots` — as filenames
  into the run dir, the lazy option consistent with the existing trace storage.
  Inline base64 was rejected: a 40-step loop run at ~100KB a shot would put
  megabytes into `result.json` for artifacts the run dir already holds.
* **Capture failure disarms rather than lies.** `attempt`'s screenshot is
  best-effort; when it failed, the observation simply carries no screenshot,
  the model is not told an image is attached, and `click_at` is refused. The
  degraded turn is an ARIA-only turn, which is M42's whole behaviour.

Declared hazard, stated as the code behaves rather than as the first draft of
this paragraph guessed (PR #70 R2): when `look()` fails mid-run the loop reuses
the previous observation, but `see()` still runs against the CURRENT trace
record, so the reused observation is re-attached to the image of the step just
executed. The model is handed a FRESH viewport screenshot beside a STALE
element list. That is a MISMATCHED pair, not a stale one, and the two halves
fail in opposite directions: coordinates read off the image are correct, while
the element names beside them may name a page that is gone. The stale-image
case is narrower and needs BOTH captures of that step to fail — `attempt`'s and
`see()`'s retry — after which the reused observation keeps the screenshot keys
the previous turn wrote on it and stays armed on a genuinely old image. Both
are accepted on M42's terms for reusing the observation at all; what is not
accepted is describing the second and shipping the first.

## Decision 2 — the drill also looks, in its own frame, and that frame arms nothing

A loop-mode `observe` with a target already re-observes the subtree (ADR-028
§6b). It now also captures `step_N_element.png`, attached to the scoped
observation as its `screenshot` with `screenshot_frame: "element"` — so a
vision model drilling into a dense region sees that region's pixels, not the
whole page shrunk. The step's TRACE evidence remains the viewport
`step_N.png` `attempt` captures; the element crop is model input, on disk
beside it. Mode B's drill is unchanged (the capture is gated on
`mode == "loop"`): its planner consumes no images, and writing files mode B
never reads would be a behaviour change nothing asks for.

**The crop is a viewport shot CLIPPED to the element's box, never
`loc.screenshot()`** (PR #70 R1). Playwright's element screenshot runs an
actionability check that scrolls the element into view first, and a scroll is
not a free observation: on a lazy-load or infinite-scroll page it loads content
nobody acted for, and the run records that as a step which changed nothing,
because `observe` sits in `agent.READ_ONLY_ACTIONS` so `page_changed` stays
null. An action classified read-only that produces a state change is the shape
this repo grades against, so this is GRADED and not merely declared:
`loop-drill-capture-does-not-scroll-the-page` drills into a section 1400px down
and then reads a status the fixture rewrites on the first scroll event, and it
was watched red against `loc.screenshot()` — answer `9 entries loaded` where
the page said `3 entries loaded`. Clipping cannot move the page, so an element
lying wholly outside the viewport gets no crop at all: the same best-effort
degrade Decision 1 takes when a capture fails, and the deliberate alternative
to scrolling and scrolling back, which restores the offset but not what the
scroll loaded. A partially visible element is cropped to the visible
intersection.

An element-scoped image does NOT arm `click_at`, and the reason is the frame's
PROVENANCE, not arithmetic about its origin. The executor reads one thing —
`screenshot_frame == "viewport"` — and a crop taken to show a sub-region is
labelled `element` however its pixels happen to line up. For the ordinary crop
the two coincide: the origin is `max(box.x, 0), max(box.y, 0)`, some way into
the page, so a coordinate read off it lands somewhere else entirely when
replayed against the viewport. **The rule does not rest on that**, and PR #70
R10 is why the distinction is now written down: for an element whose box
COVERS the viewport — in both axes, not merely one large enough by area or tall
enough in one — the clip degenerates to the viewport itself, origin `0,0`, and
coordinates read off it would in fact be correct. The refusal is
still the right answer and is not weakened by the coincidence — a gate that
inspected the numbers instead of the label would have to be right about the
offset on every crop, forever, to buy back one degenerate shape. It is a
conservative rule about where an image came from, deliberately blind to
whether this particular one could have been trusted. The turn after a drill is
disarmed; the next full observation re-arms.

The correction above had to be made everywhere the reason is PUBLISHED, because
a rule's stated reason becomes true only at the sites that state it — PR #70 R12
found the first pass had fixed two and left five (this ADR's Ruling and Decision
2 were the two; `specs/decisions/INDEX.md`'s digest, three code comments in
`agent.py`, and `loop-click-at-from-a-drill-observation-is-refused`'s provenance
were the five). Two sites deliberately keep the geometric wording and are NOT
survivors: `planner.py`'s `TOOL_TABLE` entry and the `StepError` text
`agent.py` raises on refusal. Both are addressed to the model rather than to a
reader of this decision, both describe the shape a model would actually hit —
an ordinary sub-viewport crop, where the frames genuinely do differ — and
"your pixels are in a different frame" is the useful thing to tell a caller
whose call was just refused. Model-facing guidance is not published rationale,
and the distinction is recorded here so the next sweep does not read those two
as misses.

**Where that degenerate shape and the eval set disagree, the eval set is
authoritative and the gap is declared** rather than papered over. The adapter's
`driver_screenshots` grader defines an `element` frame as one whose pixel area
is *strictly smaller* than every viewport frame the run showed — the check that
makes "a viewport shot relabelled `element`" red. An element whose box covers
the viewport produces a crop of exactly viewport area, correct by this Decision and red by
that grader. No case exercises the shape (every drill fixture here targets a
sub-viewport region), so nothing is failing today; the rule stands as written
because relaxing it to `<=` would retire the relabelling guard, which is the
more valuable of the two. ADR-034 is the in-tree precedent for this shape of
answer: it closed by stating the guarantee it actually has — an accidental
context copy is caught — and declining the broader one a reader would prefer,
that `.git` cannot reach the image. Declaring the true, narrower ceiling is a
disposition this repo already takes; engineering the code until the roomier
sentence becomes true is not. Tracked as `M43-D6`, with the fixture that would
demonstrate it.

## Decision 3 — no new model, recorded so nobody re-litigates it

ADR-027 Decision 4 requires any `ALLOWED_MODELS` widening to extend the graded
exclusion in the same change. Nothing widens: ADR-028 chose
`anthropic/claude-opus-5` with M43 in mind — the frozen snapshot entry
(`evals/labels/openrouter-models-20260820.json`, read 2026-08-26) records
`_input_modalities: ["text", "image", "file"]` and its `_role` note says
"Vision- and tool-capable, which is what loop mode and M43 need". So
`LOOP_MODELS`, `ALLOWED_MODELS` and `gateway-model-reaches-planner` are all
untouched, and the amendment rule is satisfied vacuously. If a cheaper vision
model is ever wanted, it arrives by that rule, not by this ADR.

## Decision 4 — `click_at`: the schema, the gate, the postcondition

* **Schema**: `value` is `"x,y"` — viewport CSS pixels, origin top-left, the
  frame `page.screenshot` and `page.mouse.click` share. No `target`: the whole
  point is an element no tier can name. The coordinates therefore ride in the
  trace's existing `value` field, which is where every other action keeps its
  non-target payload (a URL, a key, a scroll delta) — recorded evidence with no
  schema change.
* **The closed-world gate**, at tool-call time like ADR-028's re-homed
  refusals: `execute` refuses the call unless the loop marked the observation
  it was emitted from as bearing a viewport screenshot. Mode B never arms it —
  its planning observation carries no screenshot — so a mode B plan containing
  `click_at` dies `failure:task` with the reason named, which keeps the
  executor shared without quietly giving mode B a capability its planner was
  never told about (`planner.SYSTEM` still advertises mode B's original six;
  the T-M42-1 ruling). The refusal is a refused trace step whose reason goes
  back to the model, which — the drill-refusal case shows — recovers on the
  next turn once it has a viewport frame again.
* **Postcondition**: a coordinate click is a click. It joins
  `verifier.STATE_CHANGING`, so one executed without an authored
  `expected_state` leaves `postcondition_ok: null` and the run is demoted as
  unverifiable, exactly as for `click`/`press`/`go_back`. Malformed
  coordinates (`value` not `"x,y"` numbers) are `failure:task` — a call the
  executor will not reinterpret. Out-of-viewport coordinates are deliberately
  NOT pre-checked: Playwright clicks where it is told, nothing is there, and
  the `expected_state` fails the step — the postcondition is the gate, the
  same ruling `click` lives under.

## Decision 5 — how the image reaches the model, and what the text says

`live_driver` sends `content` as two parts — the unchanged `build_driver_user`
text and one `image_url` data-URL of the PNG — whenever the observation names a
`screenshot_path`. A path the driver cannot read raises and ends the run
`failure:env` (rule 4: a run that silently dropped the image while the gate
stayed armed would be a run lying about what the model saw). `observe.render`
gains one line — `Screenshot: a <frame> screenshot ... is attached` — so the
text and the image agree about what was provided; mode B observations carry no
screenshot key and render byte-identically to before. The driver stays
stateless (ADR-028 §7): one image per call, the current view only, no image
history. Cost: roughly 1.1–1.6k tokens per 1280x720 shot on the frozen model's
tokenizer class, per turn — accepted by ADR-027's mandate, metered per run like
everything else.

## Decision 6 — what offline grades, and what only M44's live probes can

The stub-driven cases grade the PLUMBING at $0: the screenshot is captured,
attached to the observation the driver was actually shown (the adapter stats
the file and reads its PNG dimensions at call time), recorded as trace
evidence; the drill image is element-scoped (its pixel area is smaller than
the viewport frame's); `click_at` acts at the recorded coordinates and its
postcondition verifies; the gate refuses in both ungated shapes; a `click_at`
with no authored `expected_state` demotes the run as unverifiable, and the
drill's capture leaves the page where it found it. What no
offline case can grade is vision QUALITY — whether the live model reads the
right value off the pixels and chooses sensible coordinates. That is measured
the way this repo already measures planning quality: deployment probes with
published run ids, which are M44's (ADR-027 Invariants), plus this milestone's
own live smoke below. The S2 pair states the same split inside one fixture:
`s2-bare-value-mode-b-root-reach-is-pinned` pins mode B's documented reach for
the document root (T-M40-2's shape, scripted deterministically), and
`s2-bare-value-loop-vision-path-answers` pins that the loop's
screenshot + `click_at` + text-tier `extract` path assembles, verifies and
grades the answer — with a hand-written script standing in for the model's
eyes.

## The live smoke (the acceptance clause's other half — orchestrator's call, post-review)

M42's precedent (its live clause closed post-merge against the redeployed
build) applies verbatim. The command, once this branch is merged and the
deployment redeployed with `OPENROUTER_API_KEY` set:

```bash
BASE=https://<deployment>   # the Zeabur URL serving THIS build (check /readyz)
for i in 1 2 3; do
  curl -s -X POST "$BASE/tasks" -H 'Content-Type: application/json' -d '{
    "task": "What flux reading does the meter panel report?",
    "url":  "'"$BASE"'/fixtures/s2-nameless-readout.html",
    "mode": "loop"}'
done
# contrast arm, same URL, same task, 3 reps: omit "mode" (mode B default)
```

Publish every run id, status, answer, cost and action count; ground truth is
the fixture's own constant (`7.41`). The declared pass shape is loop 3/3
correct with mode B 0/3 — mode B's failure is part of the claim, not a
by-product. Runs are sequential (the gateway holds one run slot, D19), and
`RUNS` is in-memory, so record the evidence at probe time.

## Decision 7 — the local `fast` ceiling moves 105 -> 110, because the rule says so

Not a choice: ADR-013 Decision 3's rule applied to `evals/report/history.jsonl`.
Nine cases entered `fast` (four golden, five adversarial — Decision 6's set,
plus the two PR #70's repair round added), the suite is 238, and the ledger's
slowest run at that count is **93.44s** (ts `20260827-212200`), which gives
93.44 × 1.15 = 107.46 → **110**. The
committed 105 covered anything up to 91.30s. `WALL_BUDGET_S["fast"]` moves;
`invariant` (20s) and CI's two (125s / 25s, ADR-019 §5) do not, and nothing
here measured CI.

**Why a raise and not a trim.** ADR-021 ruled that per-case growth is answered
by removing waste and case-COUNT growth by re-deriving the ceiling. Nothing
here got slower per case, and the numbers are stated over EVERY committed row at
each count — dirty and clean alike, no date filter — so the comparison is one
query and not a selection (PR #70 R13; all three clauses previously published a
narrower population than they claimed, which is PR #29 R21's class and is
ungraded here because `published-band-matches-the-ledger` reads only ADR-019
§2's band-source bullet, never this paragraph). The same 229 cases ran
**89.33-91.30s** over 25 rows; 236 cases ran **91.72-93.26s** over 5; 238 cases
run **92.01-93.44s** over 5. The two rows at 229 that are CLEAN — the only ones,
`20260827-031817` at 90.80s and `20260827-160849` at 89.42s — sit inside that
range and change nothing, which is the point of quoting the whole population
instead: the previous version of this sentence took its low end from those two
and its high end from a dirty row, and called the result three clean runs.
Trimming
to fit would mean deleting cases from the milestone that adds them, and the
most expensive of the nine are the ones that drive a real Chromium
through the screenshot path — the same argument ADR-029 made when it declined
the same trade.

**This was already the rule's answer twice, and both times the answer was to
stay at 229** (ADR-019 §2: the 230-case rows derive 110 and PR #60/M44-P1 each
moved a case to `invariant` rather than raise). Recorded here so the third time
is visibly a different situation and not a drift: at 230 there was a case that
could move, because it was a `fast`-tagged sibling of four `invariant` cases. At
238 the nine cases ARE the milestone. Re-tagging one to dodge the boundary is
the thing ADR-019 §2 names as the band deciding a suite tag instead of a
reviewer, and it is refused for that reason and not for a cost one.

**"The cases ARE the milestone" is a claim about the ASSERTIONS, not about the
RUNS, and the next person republishing this band should not have to rediscover
that** (PR #70 R6): `loop-click-at-resolves-and-records-coordinates` and
`s2-bare-value-loop-vision-path-answers` carry byte-identical `input` — same
fixture, same task, same three stub calls — and differ only in what they
assert, so the suite pays for that run twice. Merging them would buy back one
run's wall clock and is deliberately not done, because two `expect` blocks in
one case cannot be watched red independently. It does not touch the
derivation either way: the reviewer re-attributed the arithmetic to
90.15 + 1.89 = 92.04, which is a **236-case** run (ts `20260827-202317`) and not
the 238-case row this band now cites — the clause said "the run that first
reached the new count" for a round, and the count moved under it (PR #70 R8).
The point survives the correction unchanged: even a merged pair leaves the
minimum at this count above anything 105 covers.

**What moves with the number**, so the raise is not prose: `evals/run.py`
`WALL_BUDGET_S`, ADR-019's Ruling line and §2 (band source, derivation,
restatement, and the 91.30s -> 95.65s boundary sentence), README's band table,
and `fast-wall-clock-budget`'s boundary rows — 105.00/105.01 become
110.00/110.01, and its `env_override` defaults with them. That coupling is
graded: `published-band-matches-the-ledger` item 6 (ruling) reddens if ADR-019
advertises a ceiling `evals/run.py` does not commit, and `fast-wall-clock-budget`
reddens if the case's declared `max_wall_seconds` and `WALL_BUDGET_S` disagree.

## What is NOT decided here

Whether the observation budget (`MAX_ELEMS`, text head) should shrink once a
screenshot is present — nothing measured says so yet; whether `click_at` needs
a device-pixel-ratio correction on a non-1x deployment viewport (Playwright's
default context is 1x and both capture and click use CSS pixels, so today the
frames agree by construction); and everything M44 owns — the matrix
re-declaration under loop mode and the vision-quality numbers.
