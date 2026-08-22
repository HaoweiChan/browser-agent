# ADR-016: M34 — responsiveness by site-invariance, not a fourth task-string regex

Date: 2026-08-22
Status: accepted

**Ruling**: `verify()` gains `not_page_furniture`: an extraction fails when its LOCAL CONTEXT (the value plus its immediate surrounding text, anchored to the actual DOM occurrence it was read from) is also verbatim on a different page the same run visited — structural evidence from the run's own navigation, never the task string. Demonstrated offline only; ADR-015 criterion 5 stays RED until the post-merge repeated-run confirmation against the redeployed build.
**Because**: D23/T-R31/T-R32 already named the ceiling of a fourth keyword screen, and the answers it needs to catch ("Warning!", "Travel") are genuine site chrome — the SAME repeated template fragment, neighbours included, on every page — which a coincidentally-repeated fact (a title, a price) is not, so comparing neighbourhoods rather than bare values separates them without reading the question.
**Enforced by**: `verifier-responsive-not-page-furniture`, `verifier-listing-detail-title-not-furniture`, `verifier-context-anchors-real-occurrence`, `tc2-shop-search-zh`, `trap-near-miss-entity`, `docs-numbers-are-derived`, `support-matrix-cites-real-cases`

---

## Context

`tasks/TODO.md` M34: `docs/analysis.md` §8a-3 and `docs/support-matrix.md`
D23 show the inviolable property (ADR-015 criterion 5) failing a THIRD time,
on a plain single-hop extraction with no aggregate/superlative shape for
M10's `aggregate_needs_comparison` guard to catch. The deployed build
answered "tell me the price of the first book in the Travel category" with
`"Warning!"` (books.toscrape.com's own demo-site banner, 3 of 4 post-merge
runs) or `"Travel"` (the sidebar category link, the fourth run) — never the
true £45.17 — `status: success`, `verdict: PASS`, every existing L1 check
green, on all four runs. The task brief was explicit that a fourth regex
over the task string (the shape `SCOPE_BLOCK` and `_AGGREGATE` both are,
each already falsified once by a rephrasing one step outside its pattern —
`T-R31`/`T-R32`) is very likely the wrong answer here, and to reason from
what actually distinguishes an answer from page furniture rather than
reaching for the familiar tool.

## Decision

**Mechanism: cross-page site-invariance, compared by local context.**
`agent.py` keeps `page_bodies: dict[url, body_text]`, one entry per distinct
page the run has actually loaded, updated at the pre-plan navigation and
after every navigate/click/extract. Each extraction records
`other_page_text` — every OTHER page's body text at the moment the value was
read, excluding the page the value itself came from. `verify()`'s
`not_page_furniture` check fails an extraction when its LOCAL CONTEXT — the
value plus `PAGE_CONTEXT_WINDOW` (20) raw characters either side of it,
taken from the page it was read from — is also a substring of
`other_page_text`, gated by `PAGE_INVARIANT_MIN_CHARS=4` (a 1-3 character
coincidence carries no signal either way). Comparing the surrounding
NEIGHBOURHOOD rather than the bare value is what lets one rule cover both
non-numeric chrome (a nav link, a banner) and an ordinary listing→detail
repeat (a title or price shown once in a catalogue row and again on that
item's own detail page): a repeated WIDGET is the same template fragment
everywhere it recurs, neighbours included, while a coincidentally-repeated
fact sits beside different neighbours each time it appears — a catalogue row
reads "Aurora Desk Lamp $39.00" (title beside its row's price), that
product's own detail page reads "Aurora Desk Lamp $39.00 LAMP-STD Anodised
aluminium..." (title beside its OWN SKU/Material), and the two windows
diverge within a few characters. `PAGE_CONTEXT_WINDOW` was swept at widths
10-60 against every demonstrated shape (chrome, a listing→detail title, two
listing→detail prices) — every width in that range agrees throughout, and
20 sits in the middle, not at either edge.

When the same value legitimately occurs more than once on the SAME page
(a decoy mention beside the real answer — `verifier-context-anchors-real-
occurrence`), a bare `str.find` would anchor on whichever occurrence comes
first in the text regardless of which one the resolver actually matched.
`agent.py` resolves this at the source: `TEXT_OFFSET_JS` reads an
approximate DOM offset for the resolved element (summing preceding
elements' text length up the ancestor chain to `<body>`), and
`_closest_occurrence` picks the occurrence of the value in the page's body
text nearest that hint. The resulting offset travels through
`evidence_window` (now offset-aware) and each extraction's own
`value_offset` field, and `verify()`'s `_context()` anchors on it directly
— validated against the stored `page_text` before use, falling back to
`find()` when absent or stale, which is also the correct behaviour whenever
a value legitimately occurs only once (most extractions).

**Why this over the alternatives the brief itself named:**

1. *Answer-type agreement* ("a price question expects a number") was
   rejected as the PRIMARY mechanism because deriving "this task expects a
   number" from the task string is itself a keyword scan over English
   phrasing — the exact shape being avoided, just relocated from a
   behavior gate to a type gate.
2. *Chrome-landmark role* (flag extractions whose resolved element sits
   inside `role=alert`/`banner`/`navigation`/`complementary`) was
   considered and measured against the real page: `curl` of
   books.toscrape.com shows the "Warning!" banner IS `role="alert"`, but
   the sidebar category list is a bare `<div><ul><li><a>`, no `<nav>`, no
   `role=`. A landmark check would have caught exactly one of the two
   documented failures on the real site. Site-invariance catches both,
   confirmed the same way: the sidebar (and the banner) are BOTH present,
   verbatim, on books.toscrape.com's home page as well as its Travel
   category page.
3. *LLM-judged responsiveness* (`cost-discipline` skill read first) was
   rejected on cost/complexity grounds, not principle: it adds a paid call
   to every run, a prompt-injection surface (page content entering a judge
   prompt), and a deterministic-fallback burden for the `fast` suite, for a
   shape a $0.00 structural check already covers from evidence the runtime
   already collects. Left as a future escalation rung if a probe
   demonstrates a violation the structural check does not catch
   (`docs/support-matrix.md` D24 names the current candidates).
4. *A value-shape exemption* (skip the check for numbers) was tried first
   and abandoned: it papered over the numeric half of the listing→detail
   repeat pattern (a price) while leaving the non-numeric half (a title)
   open, because the real discriminator was never "is this a number" —
   comparing neighbourhoods handles both with one rule.

**Criterion 5 stays RED.** M10 shipped ADR-015 claiming criterion 5 "green
offline, live confirmation pending" and M29 found that claim refuted on the
deployed build. This decision does not repeat that mistake: it cannot run
against the deployed build (no LLM key, the deployed URL still serves
`main`), so nothing here declares the deployed property fixed.
`docs/support-matrix.md` D24 and `tasks/TODO.md` M34 both say so in those
words; the post-merge repeated-run confirmation is out of this decision's
scope by construction, the same sequence M10's fix and M29's correction
both followed.

## Consequences

`src/browser/agent.py` gained `page_bodies` tracking, `other_page_text` and
`value_offset` on each extraction, `TEXT_OFFSET_JS`/`_closest_occurrence`,
and an offset-aware `evidence_window` — no new site-specific knowledge
(CLAUDE.md rule 6): the mechanism reads role-agnostic body text, DOM
structure and URLs the executor already touches, never a selector or a
literal site string. `src/browser/verifier.py` gained `not_page_furniture`,
`PAGE_INVARIANT_MIN_CHARS`, `PAGE_CONTEXT_WINDOW` and `_context()`.
`evals/adversarial/verifier-responsive-not-page-furniture.json`,
`verifier-listing-detail-title-not-furniture.json`,
`verifier-context-anchors-real-occurrence.json`, and the fixtures
`nav-heavy-home.html` and `shop-decoy-home.html`/`shop-decoy-detail.html`
are new. `docs/support-matrix.md` gained D24, naming the ceilings that
remain rather than leaving them implied.

**What this does not do.** It does not close D23 — D23 stays as the
historical record of the deployed-build violation, struck-not-deleted
convention unchanged. It does not touch M28 (extraction-quality) or M31
(planner-side superlative lint), both explicitly out of scope for M34. It
does not claim the deployed build is fixed. Round-by-round repair history
for this decision (what a reviewer found, what changed in response) lives
in `tasks/reviews/pr30-r*.json`, not here.
