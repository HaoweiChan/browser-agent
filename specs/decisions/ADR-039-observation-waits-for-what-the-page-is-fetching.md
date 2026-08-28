# ADR-039: the observation waits for what the page is still fetching, and a refused anchor is a replan

Date: 2026-08-28
Status: accepted

**Ruling**: two changes, one failure. (1) `navigate` no longer hands the planner a page that is still waiting on the network: after the bounded `load` wait it waits, bounded by the same `SETTLE_BUDGET_MS` a postcondition gets, for the requests that were in flight at `load` to finish. The signal is an in-flight request SET maintained by listeners attached before `goto`, not `networkidle` — a static document's set is empty at `load` and it pays one emptiness test. (2) `failure:semantic` joins `failure:act` in the executor's replan family: the identity-anchor refusal — "the value I read was not on a page about the entity you asked about" — is the most informative signal a run produces, and it was the one signal the recovery ladder discarded. The anchor check moves ahead of the `answers`/`extractions` appends so a refused read cannot be carried into the replan's answer, and the laundering guard is scoped to a failed step that was supposed to change the page, which an extraction never was.
**Because**: both halves were measured on one real run against a real deployment, not imagined. Task `use extractor to get 10k report of intel 2025` against `https://whaleforce-sec10k.zeabur.app/`, run `46883372`, mode B, model `openai/gpt-5.6-luna`: `failure:semantic`, `replans: 0`, `$0.0024`. The page's committed-fixture `<select>` offers 42 filings, `intc-2002` among them, and it is painted from `/api/meta` AFTER `load` — so the pre-plan observation the planner was given contained a `combobox`, a `MenuListPopup` and zero `option` elements (26 elements; 60 with the options, measured both ways). Blind to the one control that could answer the task, the planner did the only other thing the page offers and invented an EDGAR accession number (`.../000005086325000010/intc-20241228.htm` — Intel's CIK and document name are real, the accession is not). EDGAR refused it, `doc_status` went to `failed`, the `extract` read the fixture list, and the anchor `Intel` was correctly absent. The verifier was right and the run was honest; what it was not was recoverable. Both defects are the same shape from opposite ends — the planner could not see the page, and the executor would not look again.
**Enforced by**: `planner-sees-a-fetch-painted-select` (the observation half, on `late-options.html`, whose `<select>` is empty in the document and filled from an endpoint that sleeps server-side; watched red with every other check on the case green — `status`, `verdict` and `trace_actions` all true and `planner_saw` alone false, which is what a silent failure looks like) and `replan-after-a-refused-anchor` (the recovery half, on `shop.html`, an anchor absent from the page followed by a plan that reads correctly; watched red at `status failure:semantic`, `replans 0`, exactly the deployed run's shape).

---

## Context

The 2026-08-24 postmortem named this shape S1 (fetch-then-render) and this repo
has carried it as a declared, measured, unfixed limitation ever since:
`live-sec10k-authored-wait-reaches-the-doc-status`'s claim (1) says in as many
words that "the deep link removes the click, not the race". The limitation was
declared honestly and it was still a limitation, and it then cost a real run
against a real site — which is the argument for closing declared limitations
rather than re-declaring them.

`observe`'s own element budget was the suspected culprit before it was
measured, and it was not the culprit: on the deployed page the observation ran
to 26 elements, well inside `MAX_ELEMS = 60`. The options were not cut off;
they did not exist yet. `sec10k-item-text-region-is-past-the-observation-cap`
grades the genuine cap defect on a static snapshot and is untouched by this ADR
— a committed snapshot is post-render by construction, which is the same
reason that case could never have caught this one.

## Decision

### 1. The wait is on in-flight requests, not on network idleness

`networkidle` is the obvious mechanism and it was rejected twice, both times on
a measurement rather than a preference:

| mechanism | fast-suite wall clock | verdict |
|---|---|---|
| `networkidle`, every navigation (ADR-002) | +34s | rejected |
| `networkidle`, gated on the document carrying a `<script>` | 93.5s → 144.9s (+51.4s, over the 110s ceiling) | rejected, measured in this ADR's own first draft |
| in-flight request set, bounded by `SETTLE_BUDGET_MS` | see ADR-019 §2's band bullet | accepted |

`networkidle` charges every navigation 500ms of quiet to protect the few pages
that need it. The in-flight set asks the narrower question the defect is
actually about — *is this page still waiting on something?* — so a document
whose script has already finished, and every script-free fixture, pays a set
emptiness test.

Listeners are attached before `goto` because the requests that matter are the
ones a page issues while it parses: a `fetch` in an inline script is in flight
before `load` fires, which is the only reason the question can be asked at
`load` time at all. They are removed in a `finally`, because `navigate` is
called once per hop on a page that outlives the run.

### 2. What this does NOT close

A page that issues its fetch from a `setTimeout` **after** `load` has an empty
in-flight set at the instant this is asked, and is read early exactly as
before. This is deliberate: the fix is not a quiescence window, and a
quiescence window is what would cost every page again. Upgrade only when a case
demonstrates that shape — `tasks/TODO.md` T-A39-1.

**And the cost, measured on the page this ADR was written for.** Waiting for the
paint means the planner now SEES the fixture `<select>` — which is the whole
point — and on `?fixture=aapl-2025&run=1` its 49 options fill `MAX_ELEMS = 60`
before the observation reaches `status — 'doc_status'`. Before ADR-039 that page
observed 26 elements and the status line was comfortably inside the budget. So
this ADR trades a paint race for a cap. That is the better direction — a
drill-down can reach capped content, and nothing can reach content that does not
exist yet — but it is a trade, recorded rather than absorbed: `tasks/TODO.md`
T-A39-3, with the two live cases carrying the evidence as an assertion
(`lacks: ["status — 'doc_status'"]` where they used to assert `has`). The
executor is unaffected — `resolve` is not capped and both live cases still pass
on `status` — and that split is the point: this is planner visibility alone.

`live-sec10k-authored-wait-reaches-the-doc-status`'s `planner_saw.lacks:
["18 extracted"]` still holds after this change and its stated reason no longer
does, which is T-A39-2. The reason has now moved TWICE, and both moves are
recorded because each one made the case green for something different from what
it claims. First: the extraction round trip does land by observation time after
the settle, so "the deep link removes the click, not the race" stopped being
why, and `observe.TEXT_HEAD`'s 300-character cap on the page text became why.
Then, once the target's fixture list reached 49 options, the ELEMENT budget
became why as well — the status line no longer reaches the observation at all,
which is the paragraph above. A clause whose reason has moved twice while the
clause held is the definition of a green that cannot falsify its own claim, and
T-A39-2 is the block for re-pointing it rather than re-explaining it a third
time.

### 3. `semantic` replans, and the two things that had to move with it

The one-word change `cls == "act"` → `cls in ("act", "semantic")` is wrong on
its own, twice over:

* **the rejected read is already recorded.** `answers.append(...)` and the
  `extractions` loop ran BEFORE the anchor check, which was harmless only while
  a semantic failure ended the run on the spot. With a replan behind it, the
  refused value would be carried into the run's answer — turning a scalar into
  a list, or answering with the very read the anchor refused. The check moves
  ahead of both appends.
* **the laundering guard refuses every semantic replan.** `drops_action and
  changed_nothing(rec)` exists to stop a replan that drops a failed ACTION and
  reads the page as if it had worked. A failed extraction was never supposed to
  change the page, so "the replan only reads" is not evidence of laundering
  there — it is the correct recovery. The guard is scoped with
  `not reads_without_acting([step])`, reusing the predicate that already
  answers exactly this question about a plan.

`MAX_REPLANS` is unchanged, so the new path spends from the same budget of 2
and the no-progress guards (identical plan, re-issued step, plan lint) all
apply to it unaltered.

### 4. `EVAL_PROBE=1`, because this ADR's own drafting poisoned the ledger

The band ADR-013's rule derives is `max(wall_s)` over every ledger row at the
current case count. A row is therefore permanent in the direction that matters:
one slow measurement raises the derived ceiling forever, and nothing about the
row says what code produced it.

Drafting §1 produced three such rows — 144.87s at 239 cases (`networkidle` on
every navigation), 100.61s and 100.86s at 240 (an in-flight set counting every
request type). All three measured mechanisms this tree does not contain, and
all three would have set the band. They were removed before `history.jsonl` was
committed, and this paragraph is the record of that rather than a silent
truncation of a committed file — which is the shape T-M38-5 objects to.

The mechanism, so the next probe needs no paragraph: `EVAL_PROBE=1` routes the
history line to `evals/report/history-probe.jsonl` (gitignored) instead of the
committed ledger. Deliberately a redirect and not a drop — a probe that leaves
no trace is a probe nobody can audit, and T-M38-5's complaint is about
measurements whose provenance went missing, not about measurements existing.
It does NOT cover a probe run without the variable set; that is still the
operator's discipline, and it is the residual T-M38-5 keeps.

### 5. The ceiling moves 110 → 115, and not under ADR-021's licence

Stated plainly because the previous four raises on this line were all
case-count growth and this one is not. Two cases entered `fast` and cost ~0.2s;
the rest of 93.44 → 96.02 is per-case cost from §1's settle. ADR-021 answers
per-case growth by removing waste, so that was done first, twice, and both
attempts are on the record in ADR-019 §2: narrowing the in-flight set to
`fetch`/`xhr` returned 4.8s of a 7.3s regression (most of it Chromium's own
`/favicon.ico` 404 on every navigation), and dropping the poll tick 20ms → 5ms
returned 0.25s and falsified the theory that rounding dominated. What remains is
the page being waited on. The raise buys a capability and the trade is written
down rather than absorbed.

### 6. Observation budgets the options of a control, not the elements of a page (2026-08-28)

§1's settle bought correctness and charged for it in a currency this ADR did
not price: once the sec-10k inspector's committed-fixture `<select>` actually
PAINTS, its 49 `option`s enter the accessibility tree, and the page-level
observation fills at `observe.MAX_ELEMS` several elements before
`status — 'doc_status'`. The status line had been visible to a planner the day
before. T-A39-3 recorded that as the measured cost of §1, and it is the shape
this repo keeps meeting: 49 siblings under one `combobox` are ONE control, not
49 things a planner needs enumerated.

`observe.MAX_OPTIONS = 8`, applied PER combobox/listbox/menu subtree — the
shape `MAX_CHROME` has had per landmark since M32. A drill-down onto the
control gets the whole page budget, the same exemption chrome has, so the
options a planner actually needs are one `observe` away rather than gone.

Raising `MAX_ELEMS` is refused here for the third time, on the reason
`observe.py`'s own comment gives: it moves the cliff to the next larger page
and spends planner tokens on a dropdown nobody asked about.

What this bought is larger than what it restored. The named extracted-text
region that `sec10k-item-text-region-is-past-the-observation-cap` had DECLARED
unreachable-by-observation since M41 is now inside the cap, so that case is
inverted: it asserted the region was past the cap and now asserts the status
line, the region and the combobox are present together. A declared limitation
removed rather than documented further — the second this month, and the reason
the standing preference is a guard in the grader over a sentence in a note.

The change surfaced a second thing, which is recorded here because it was found
by this work and answered somewhere else. With 41 element slots freed, the
observation began advertising elements that `resolve` cannot reach directly:
Chromium's accessibility snapshot calls six visible `<th>` `columnheader` and
`<summary>` `DisclosureTriangle`, while `get_by_role` answers 0 for
`columnheader` (against 2/18/54 for table/row/cell) and knows no such role as
`DisclosureTriangle`. Two role oracles, one page. Both targets ARE reached, by
the relocation ladder the executor already runs on a locate failure, so the
executor was never wrong; the observe case was asserting a property the
executor does not need. It now reports `advertised_needed_relocation` instead
of failing, so the cost is visible rather than silent.

A resolver-side fix was tried first and is rejected on measurement, not taste:
a name-as-text fallback tier resolved the sec-10k targets and ALSO resolved
`l4-shop-a11y-stripped`, `l4-forms-a11y-stripped`, `l4-recover-name-to-text`
and `l4-shop-duplicate-labels` — the mutation suite's recovery metric went
green with no recovery performed. Narrowing the tier to "no element of this
role exists anywhere" did not separate the two either, because stripping a11y
removes the role from the page as well. The ladder is the right layer.
