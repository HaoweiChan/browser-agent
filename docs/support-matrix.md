# Support matrix — Task 1

**Report-assisted, human-declared** (see `docs/evals/evaluation-methodology.md`):
the latest `full`-suite eval report suggests a status; a human declares the
final status with a reason; README and the frontend render this same data.
A pass-rate does not threshold itself into "supported" — declaring is an
engineering-judgment act, and the reason column is the graded honesty evidence.

Entry shape (also served as JSON to the frontend):

```json
{
  "domain": "wikipedia.org",
  "task_type": "TC2 search-then-extract",
  "eval": "7/8",
  "declared_status": "unreliable",
  "reason": "Disambiguation pages still misroute the extraction step (case tc2-wiki-004)."
}
```

## Current matrix

Declared from the M5 baseline (`evals/report/20260816-210730-fast.json`, 59/59, plus the `live` run).
Every status below rests on **offline fixtures with the planner stubbed** —
this table measures the resolver/executor/verifier path, not planning quality
and not any live site. Empty cells are shown, not hidden.

| Domain | TC1 | TC2 | TC3 | TC4 | TC5 |
|--------|-----|-----|-----|-----|-----|
| shop fixture | supported | supported | supported | supported | — |
| forms fixture | — | — | — | — | supported |
| hello fixture | supported | — | — | — | — |
| books.toscrape.com (live) | — | — | unreliable | — | — |
| wikipedia.org | — | — | — | — | — |

Statuses: `supported` / `unreliable` / `unsupported` / `—` (not yet evaluated).
Unsupported and unreliable rows must cite a concrete failing case id.

## Declared limitations (M5)

| Limitation | Evidence | Status |
|---|---|---|
| Live TC3 on books.toscrape.com is `unreliable`, not `supported` | `live-books-travel-price` passes with a **stubbed** plan; the same task with the **real** planner failed on the deployment (run `cd7121fc`) | `unreliable` — the two results disagree, and the disagreement is the finding. With a hand-written plan the resolver/executor/verifier path handles the live DOM; with the live planner the run failed loudly at `failure:locate`. Declaring this `supported` on the strength of the stubbed case would be exactly the flattery this table exists to prevent |
| The live planner emits target roles that are not ARIA roles | deployed run `cd7121fc`: `{"role": "text", "name": null, "text": null}` → `ResolveError: no tier resolved` → `failure:locate` | `unreliable` — the planner reaches for a `text` "role" when it wants to read text. The agent fails loudly with the right class and no fabricated answer, and relocation correctly finds nothing to climb to (a target with neither name nor text has no rungs), so the cost is a failed run rather than a wrong one |
| Live extraction from a table is positional | `live-books-travel-price` targets `{role: cell, index: 5}` | `unreliable` — ARIA makes `rowheader` a subclass of `cell`, so label and value cells interleave and the price is reached by counting. The semantic form, `near:`, is advertised in the `specs/001-browser-contract.md` target schema and **never implemented in the resolver** — spec-drift, recorded rather than fixed at the freeze |
| Capability is about one hop deep | T9 held-out probe: 2 correct answers in 8 answer-seeking tasks. Second hops, aggregates and comparisons all failed | `unreliable` — the two successes were single-hop extractions whose answer string was already in the pre-plan observation. There is no compare/rank/filter step in the plan vocabulary, so "which is cheapest" is planned as "extract the whole list" |
| Values that exist only in an HTML attribute cannot be read | T9 probe #1 and #6: listing titles are CSS-truncated to `A Light in the ...`, with the full string only in `title=`/`alt=` | `unsupported` — extraction reads element text, so the run fails loudly (`failure:semantic` on the identity anchor, or an empty extraction) rather than returning the truncated string |
| With no start URL, the planner plans blind | T9 probe #7: step 1 came back `note: null`, `postcondition_ok: null` — no observation happened; the plan emitted `{"role": "article"}` and failed `locate` | `unreliable` — commit `ed1f774` ("the planner never plans blind") covers only the URL-supplied path, where there is a page to observe. Spec drift found by the probe, declared rather than fixed at the freeze |
| The keyword scope screen over-refuses on non-instrumental phrasing | `l5-refuse-login-contracted` (the row deliberately removed from it): "What is the sign in the shop window?" is refused | `unreliable`, in the safe direction — the words in "sign in the shop window" and "sign in to my account" are identical and only intent differs, which no keyword screen can separate. First eval evidence that the deferred LLM screening has a real job |
| An answer is never checked for being *responsive* to the question | T9 probe #5: a 20-book page dump was returned as the answer and rejected only by `grounded`, on a whitespace mismatch | `unreliable` — the verifier checks that an answer is grounded, anchored and matches ground truth where available, but nothing asks whether it addresses the task. In that run the no-fabrication guarantee held by luck |
| Planning quality unmeasured | every `fast` case stubs the planner at the module boundary | by design (cost-discipline); the `full` suite is the only measurement |
| Values in ARIA name-prohibited elements (`<dd>`, `<dt>`, `code`, `time`…) cannot be targeted | `observe-name-prohibited-roles` | `unsupported` — the observation no longer advertises them, so the agent fails loudly instead of planning an unresolvable target |
| A locator broken at **both** reachable tiers is not recovered | `l4-shop-button-text-renamed` recovers text → role+name, `l4-recover-name-to-text` the reverse | `unreliable` — relocation has exactly two rungs to climb between, because `role` and `text` are the only tiers any run has ever emitted. The `attrs` and `structural` tiers exist in the taxonomy and in no code path, so a mutation that kills both reachable tiers has nowhere to go |
| An identity anchor can be satisfied by evidence from a discarded attempt | `verifier-superseded-not-a-loophole` pins the trace half only | `unreliable` — supersede hides a failed attempt from trace grading, but `evidence_text` is still built from every extraction, including the superseded one (ADR-005) |
| A replan is refused when the failed action changed nothing on the page | `replan-cannot-launder-noop-action` vs its benign twin `recovery-replan-postcondition` | `supported`, with a ceiling: the test is whole-body text equality, so an action whose only effect is visual or off-page reads as no change and its recovery is refused — loud, and in the safe direction |
| Relocation rung 1 ignores the target's role | no case yet; found by cold review (ADR-005) | `unreliable` — a target `{role: link, text: X}` can relocate onto a same-named heading, which is a common listing-page shape |
| The progress stream is graded on the executor's hook, not on the SSE endpoint | `stream-shows-every-step` installs its own `on_step` and compares step ids only | `unreliable` — the gateway's own emitter and its copy semantics are untested, and a stream that stripped step *contents* would still pass (ADR-005) |
| Recovery is reported as a floor, not a rate | 3 injected cases assert recovery; 6 rungs were tried to produce them | by design (ADR-003) — three cases is not a population. It stays `x/y` with the denominator printed until a live suite gives it one |
| Near-miss entity whose name contains the target's name | `trap-near-miss-entity` | caught only with external ground truth; a live run's runtime anchor passes it |
| Identity anchors on aggregate pages (listings, search results) | `trap-search-not-executed` | `unreliable` — every candidate entity is in the page text, so the anchor certifies the wrong answer too. The larger of the two anchor holes, and it sits exactly where TC2/TC4 live. |
| The `fast` suite never runs observe → plan → resolve | all fixture cases inject a stub plan at the planner boundary | by design (cost-discipline), but it means the L4 self-maintenance passes are measured on plans hand-authored against the mutated DOM. Only the `full` suite closes this. |
| A click whose effect cannot be asserted | `postcondition-unverified-click` | `unsupported` by choice: the run fails loudly rather than reporting an unverified state change as success |
| ZH support is character-level, not planning-level | 7 ZH cases, all with stubbed plans | `unreliable` until a ZH case runs in the `full` suite |
