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

Declared from the M2 baseline (`evals/report/20260816-002725-fast.json`, 41/41).
Every status below rests on **offline fixtures with the planner stubbed** —
this table measures the resolver/executor/verifier path, not planning quality
and not any live site. Empty cells are shown, not hidden.

| Domain | TC1 | TC2 | TC3 | TC4 | TC5 |
|--------|-----|-----|-----|-----|-----|
| shop fixture | supported | supported | supported | supported | — |
| forms fixture | — | — | — | — | supported |
| hello fixture | supported | — | — | — | — |
| wikipedia.org | — | — | — | — | — |

Statuses: `supported` / `unreliable` / `unsupported` / `—` (not yet evaluated).
Unsupported and unreliable rows must cite a concrete failing case id.

## Declared limitations (M2)

| Limitation | Evidence | Status |
|---|---|---|
| No live domain evaluated at all | no `full`-suite case exists yet | blocks the B-floor "≥1 live domain" criterion; scheduled for M5 |
| Planning quality unmeasured | every `fast` case stubs the planner at the module boundary | by design (cost-discipline); the `full` suite is the only measurement |
| Values in ARIA name-prohibited elements (`<dd>`, `<dt>`, `code`, `time`…) cannot be targeted | `observe-name-prohibited-roles` | `unsupported` — the observation no longer advertises them, so the agent fails loudly instead of planning an unresolvable target |
| A locator broken at the tier the plan is standing on is not recovered | `l4-shop-button-text-renamed` (expects `failure:locate`) | `unsupported` until the M3 relocation loop |
| Near-miss entity whose name contains the target's name | `trap-near-miss-entity` | caught only with external ground truth; a live run's runtime anchor passes it |
| Identity anchors on aggregate pages (listings, search results) | `trap-search-not-executed` | `unreliable` — every candidate entity is in the page text, so the anchor certifies the wrong answer too. The larger of the two anchor holes, and it sits exactly where TC2/TC4 live. |
| The `fast` suite never runs observe → plan → resolve | all fixture cases inject a stub plan at the planner boundary | by design (cost-discipline), but it means the L4 self-maintenance passes are measured on plans hand-authored against the mutated DOM. Only the `full` suite closes this. |
| A click whose effect cannot be asserted | `postcondition-unverified-click` | `unsupported` by choice: the run fails loudly rather than reporting an unverified state change as success |
| ZH support is character-level, not planning-level | 7 ZH cases, all with stubbed plans | `unreliable` until a ZH case runs in the `full` suite |
