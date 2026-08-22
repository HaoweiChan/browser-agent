# ADR-016: M34 — responsiveness by site-invariance, not a fourth task-string regex

Date: 2026-08-22
Status: accepted

**Ruling**: `verify()` gains `not_page_furniture`: an extraction's LOCAL CONTEXT (value + 20 chars either side, from the page it was read from) matching verbatim on a DIFFERENT page this run visited fails the run — structural evidence from the run's own navigation, never the task string. Amended round 1 (PR #30 R1): the first cut compared the bare value and a numeric exemption, both replaced by the context compare, because the bare-value version flagged a correct listing->detail title as furniture. Fixed and eval-pinned offline only; ADR-015 criterion 5 stays RED until the post-merge repeated-run confirmation against the redeployed build.
**Because**: D23/T-R31/T-R32 already named the ceiling of a fourth keyword screen before this PR started, and the two real answers it needs to catch ("Warning!", "Travel") are genuine site chrome — the SAME repeated template fragment, neighbours included, on every page — which a coincidentally-repeated fact (a title, a price) is not, so comparing neighbourhoods rather than bare values separates them with one rule instead of a value-shape exemption.
**Enforced by**: `verifier-responsive-not-page-furniture`, `verifier-listing-detail-title-not-furniture`, `tc2-shop-search-zh`, `trap-near-miss-entity`, `docs-numbers-are-derived`, `support-matrix-cites-real-cases`

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

**Mechanism chosen: cross-page site-invariance.** `agent.py` now keeps
`page_bodies: dict[url, body_text]`, one entry per distinct page the run has
actually loaded, updated at the pre-plan navigation and after every
navigate/click/extract. Each extraction records `other_page_text` — every
OTHER page's body text at the moment the value was read, excluding the page
the value itself came from. `verify()`'s new `not_page_furniture` check
fails an extraction whose cleaned value is a substring of that
`other_page_text`, gated by `PAGE_INVARIANT_MIN_CHARS=4` (a 1-3 character
coincidence carries no signal either way) and exempting any value that
parses as a number (`_num_parts`, the same numeric parser `answers_match`
already uses — see Decision 2 below).

**Why this over the alternatives the brief itself named:**

1. *Answer-type agreement* ("a price question expects a number") was
   rejected as the PRIMARY mechanism because deriving "this task expects a
   number" from the task string is itself a keyword scan over English
   phrasing — the exact shape being avoided, just relocated from a
   behavior gate to a type gate. It survives here only as a narrow,
   evidence-motivated EXEMPTION (Decision 2), not as the thing doing the
   catching.
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
   rejected for this PR on cost/complexity grounds, not principle: it adds
   a paid call to every run, a prompt-injection surface (page content
   entering a judge prompt), and a deterministic-fallback burden for the
   `fast` suite, for a shape that a $0.00 structural check already covers
   from evidence the runtime already collects. Left as a future escalation
   rung if a probe demonstrates a violation neither structural check name
   catches (`docs/support-matrix.md` D24's numeric-furniture ceiling is the
   most likely candidate).

**Decision 2 — the numeric exemption.** Running the mechanism above against
the EXISTING `fast` suite (not a guess) surfaced two real false positives:
`tc2-shop-search-zh`'s `"$18.00"` and `trap-near-miss-entity`'s `"$59.00"`
both legitimately repeat between a catalogue listing row and that product's
own detail page — an ordinary listing+detail pattern, not furniture. The
SKU anchor that would otherwise disambiguate the two pages is, by fixture
design, only on the detail page, so no anchor-based exemption reaches this
case. A value that parses as a number is exempted from `not_page_furniture`
entirely: `_num_parts` classification, reused from `answers_match` rather
than reinvented (ponytail: shortest diff over new machinery). No case in
this repo's evidence shows a numeric string as furniture — this is a
declared ceiling (`docs/support-matrix.md` D24), not a proven-safe
generalization.

**Decision 3 — criterion 5 stays RED.** M10 shipped ADR-015 claiming
criterion 5 "green offline, live confirmation pending" and M29 found that
claim refuted on the deployed build. This PR does not repeat that mistake:
it cannot run against the deployed build (no LLM key, the deployed URL
still serves `main`), so nothing here declares the deployed property
fixed. `docs/support-matrix.md` D24 and `tasks/TODO.md` M34 both say so in
those words; the post-merge repeated-run confirmation is out of this PR's
scope by construction, the same sequence M10's fix and M29's correction
both followed.

## Consequences

`src/browser/agent.py` gained `page_bodies` tracking and `other_page_text`
on each extraction — no new site-specific knowledge (CLAUDE.md rule 6): the
mechanism reads role-agnostic body text and URLs the executor already
touches, never a selector or a literal site string. `src/browser/verifier.py`
gained `not_page_furniture`, `PAGE_INVARIANT_MIN_CHARS`, `PAGE_CONTEXT_WINDOW`
and `_context()` (the last two from the round-1 amendment below — see it for
why a bare-value compare was not the final shape).
`evals/adversarial/verifier-responsive-not-page-furniture.json`,
`evals/adversarial/verifier-listing-detail-title-not-furniture.json` and
`src/browser/fixtures/nav-heavy-home.html` are new. `docs/support-matrix.md`
gained D24, naming both declared ceilings (a run that never leaves one page;
the context-window width being swept on four shapes, not proven for every
shape) rather than leaving them implied. `README.md` and `docs/analysis.md`
case counts move 116→118 / 105→107 across both rounds (`docs-numbers-are-
derived`).

**What this does not do.** It does not close D23 — D23 stays as the
historical record of the deployed-build violation, struck-not-deleted
convention unchanged. It does not touch M28 (extraction-quality) or M31
(planner-side superlative lint), both explicitly out of scope for M34. It
does not claim the deployed build is fixed.

## Amendment (PR #30 round 1, R1, HIGH, repair)

**Finding.** The bare-value compare above flagged a CORRECT non-numeric
answer as furniture whenever it legitimately repeats between a catalogue
row and that item's own detail page — the exact listing→detail navigation
shape `tc2-shop-search-zh` and `trap-near-miss-entity` already exercise for
prices (both numeric, both exempted by the original cut), now shown for a
title with no exemption to catch it:
`verify(extractions=[{"value": "The Great Gatsby", "page_text": "The Great
Gatsby Price: £45.17", "other_page_text": "Category: Travel The Great
Gatsby £45.17"}])` returned `not_page_furniture: False`, `verdict: FAIL` for
the right answer. Reproduced as a real fixture-driven run, watched red
before this amendment: `verifier-listing-detail-title-not-furniture`
(shop.html → shop-lamp-std.html, extracting the product's own `<h1>`) —
`status: failure:semantic`, `verdict: FAIL`,
`checks.not_page_furniture: false`, reason naming `"Aurora Desk Lamp"` as
chrome.

**Fix.** `not_page_furniture` now compares `_context(page_text, value,
PAGE_CONTEXT_WINDOW=20)` — the value plus 20 raw characters either side of
it, taken from the page it was read from — against `other_page_text`,
instead of the bare value. Site chrome is one repeated template fragment,
so its NEIGHBOURS repeat with it everywhere it recurs; a coincidentally-
repeated fact does not: `shop.html`'s catalogue row reads "Aurora Desk Lamp
$39.00" (title beside its row's price) while the product's own detail page
reads "Aurora Desk Lamp $39.00 LAMP-STD Anodised aluminium..." (title
beside its OWN page's SKU/Material) — the window diverges within a few
characters. The numeric exemption is deleted outright, not narrowed: it was
covering for the mechanism being too broad, not for numbers being special,
and the same context compare handles `tc2-shop-search-zh`'s `$18.00` and
`trap-near-miss-entity`'s `$59.00` correctly with no special case — one
rule instead of two, and it closes the numeric-furniture ceiling D24
previously declared rather than widening it.

`PAGE_CONTEXT_WINDOW=20` is not a guess: swept at widths 10-60 against all
four known shapes (the title case, both price cases, and the original
"Travel"/"Warning!" furniture reproduced by `verifier-responsive-not-page-
furniture`) — every width in that range agrees on all four, 20 sits in the
middle, not at either edge (`/tmp` sweep script, not committed; the
agreement itself is what the choice rests on, not a specific script).
`nav-heavy-home.html` — the fixture landing page `verifier-responsive-not-
page-furniture` uses — was widened from a one-item sidebar to the full
35-item list identical to nav-heavy.html's, matching books.toscrape.com's
own shape (confirmed live by `curl`: the same ~50-category sidebar, same
order, on every page of the real site): a fixture where only the furniture
STRING repeated and not its neighbours could not have exercised a
context-window check honestly, and would have silently passed a check that
was actually checking nothing.

**Confirmed the original defect still fails loudly.** Both `verifier-
responsive-not-page-furniture` (the "Travel" shape) and the reviewer's own
repro against `verify()` directly were re-run after the narrowing:
`not_page_furniture` still returns `False` / `verdict: FAIL` for "Travel"
and for "Warning!" — the sidebar and banner carry their neighbours with
them precisely because they are the same repeated fragment, which is what
the context compare is built to catch. `tc2-shop-search-zh`,
`trap-near-miss-entity`, and the new
`verifier-listing-detail-title-not-furniture` all now pass. Full `fast`
suite: 106/107 (the one non-pass is `docs-numbers-are-derived`, the
expected doc-count drift this same case addition causes, not a regression).

**Ceiling named, not left implied** (`docs/support-matrix.md` D24, rewritten
in place since this is round-1 repair on an unmerged PR, not a retroactive
edit of settled history): a single-page run still has no comparison
evidence, unchanged; `PAGE_CONTEXT_WINDOW=20` is swept on four shapes, not
proven for every shape — furniture whose immediate neighbours genuinely
vary page-to-page (personalized chrome, a nav that highlights the current
item) could false-negative through the widened check the way the narrower
one used to false-positive, and a listing/detail pair whose immediate
neighbours happen to align by coincidence could still false-positive.
Narrower than the shape D24 previously declared, not proven closed. Neither
is guessed at ahead of a probe, per CLAUDE.md rule 2. Criterion 5 remains
RED throughout this amendment — nothing here touches the deployed-build
question.
