# ADR-032: a tier is ONE match set, and the case-fold is how that set is chosen — not a second set beside it

Date: 2026-08-27
Status: accepted

**Ruling**: a name tier resolves to exactly ONE match set per document — the case-exact matcher counted first, the case-folded one used only when that is EMPTY (fallback, never union), with `near`, `index`, `many`, the `n == 1` uniqueness check and M38's ambiguity bookkeeping all reading that one set.
A page carrying an exact-case match therefore never consults the fold at all and resolves byte-for-byte as it did before T-M42-20; when the fold IS used the step's trace note says `narrowed: name-case-folded`.
**Because**: T-M42-20 relaxed case in the name tiers to close a real defect (two
engines computing an accessible name differently), and both attempts to express
that relaxation as an extra *set* produced a silent wrong-success in the same
mechanism — first by widening the set every selector reads (PR #60 R1), then by
letting two sets be indexed in turn (PR #60 R10). Selection rules that disagree
about what they are selecting from is the defect; one set is the fix.
**Enforced by**: `resolver-index-selects-from-one-match-set`,
`resolver-case-twin-index-picks-the-exact-spelling`,
`resolver-case-twin-near-picks-the-exact-spelling`,
`resolver-case-fold-is-recorded-in-the-trace`,
`resolver-folded-name-with-a-slash-resolves`, `resolver-substring-name`.

**Amends**: ADR-026 (rung 2's text conjunct is vacuous on the exact pass and
near-vacuous on the folded one — stated there, ruled here)

---

## Context

`observe()` reads accessible names from Chromium's `accessibility.snapshot()`,
which applies the page's CSS text-transform. Playwright's locator engine
computes its own name and does not. So an observation can hand the planner
`SELECT A COMMITTED FIXTURE` for a control the locator engine calls
`select a committed fixture`, and `get_by_role(..., exact=True)` — case-sensitive
whole-string — matches nothing. That is T-M42-20, and it is why matching had to
relax.

What it did NOT settle is the question this ADR exists for: **a tier used to be
one locator, and relaxing case gives you two. What is the match set now?**

Three rules read a tier's matches, and each answers a different question:

| rule | question | sensitive to |
|---|---|---|
| `n == 1` / ambiguity | is this the only match? | the SIZE of the set |
| `index: k` | which match, by position? | the SIZE and the ORDER |
| `near` | which match, by proximity? | the MEMBERSHIP |
| `many` (`extract_all`) | all of them | the MEMBERSHIP |

None of them is safe against a set that quietly changed shape, and two rounds of
review found exactly that, twice:

- **PR #60 R1.** The first attempt made the folded matcher *the* matcher. The
  set grew to include case twins, and every rule above read the bigger set:
  `{name: 'Add to cart', index: 0}` moved off a catalogue row CTA onto an
  `ADD TO CART` promo banner above it, `extract_all` enumerated both, and `near`
  picked a twin planted beside the anchor. No `ambiguous-match`, nothing in the
  trace.
- **PR #60 R10.** The second attempt made it two ordered passes and applied the
  rules to each in turn. `index` was then *re-based per pass*: with one exact
  match, `index: 0` returned it, and `index: 1` fell through to the folded pass
  and returned **the same element**. A task asking for the second link was
  answered, `success`, with the first. Base `6b016b5` raised
  `element-not-found` for that plan.

Both are the same shape — a selection rule reading a different set than the one
the plan was written against — and both were silent.

## Decision

**1. One set per tier, chosen before anything selects from it.** `scope_tiers`
carries the exact locator and, where a name is involved, a folded alternative.
`_resolve_in` counts the exact one once; if it is empty it swaps in the folded
one. Everything after that point sees a single locator and cannot tell how it
was chosen — which is the property that makes the three rules agree.

**2. Fallback, not union.** The alternative on the table was to union the two
passes and then select. It is rejected: a union contains the case twins, so
`index`, `near` and `many` read a set the plan was not written against — which
is R1 exactly, arriving by another route. Fallback has the stronger property:
*if the page spells the name the way the plan does, the fold is never consulted*,
so nothing about such a page changed when T-M42-20 landed, at any tier, for any
of the four rules.

**3. The fold is disclosed, on every path that can use it.** A folded resolution
is a looser reading of what the plan asked for, in the same sense M38's
narrowing rungs are, so it carries a trace note — `narrowed: name-case-folded` —
rather than being invisible. Relaxations COMPOSE: a rung and a fold are not
alternatives, so the note is every relaxation that was used, joined
(`resolver._note`). This sentence was false when first written — the rungs
returned their own label and never read `fold`, so a resolution that existed only
because the fold ran reported the rung alone (PR #60 R15). Pinned by
`resolver-case-fold-is-recorded-in-the-trace` (no rung) and
`resolver-narrowing-discloses-the-case-fold` (rung 1 plus the fold).

**4. Whole-string survives, in both passes.** Neither matcher is a substring
match. `resolver-substring-name` exists because substring matching once resolved
an absent target to a superstring sibling and reported the wrong element as a
success; the folded matcher is anchored (`^…$`) for exactly that reason, and
relaxes case and nothing else.

## Consequences

- The collision claim is conditional, and that is now the accurate statement:
  two names differing only in case collide as an ambiguity — and go to M38's
  rungs — **only when neither matches the plan's spelling exactly**. When one
  does, it wins outright.
- `index: k` on a page with one exact match and k > 0 is a loud
  `element-not-found`, as it was before T-M42-20.
- One extra `count()` per name tier per document. Every path except `near` was
  already paying it; `near` now pays it too, and that is the cost of proximity
  and indexing agreeing about what they select from.
- The fold is reachable only where the exact pass is empty, which is also what
  makes it *testable*: a case has to build a page that spells the name no other
  way, and `case-twins.html` is that page.

## What this does NOT settle

- **The role half.** Two engines can disagree about a control's ROLE as well as
  its name — `<input type="file">` is `button` to Chromium's snapshot and
  `textbox` to Playwright — and no fold fixes that. `T-M42-20-D4`,
  `docs/support-matrix.md` D32.
- **Anchors as a round trip.** `near`'s exact pass folds case (PR #60 R5), but
  nothing feeds an advertised string back as an anchor the way
  `observe-uppercase-label-name-resolves` feeds it back as a name. D32.
- **Composed disclosures, on the `near` branch only.** Decision 3 covers the
  narrowing rungs; the `near` branch still picks one label with an `or`, so a
  resolution that used both a loosened anchor and the case fold reports only the
  anchor. `resolver._note` is the one-line adoption and `T-M42-20-D10` is the
  debt — deliberately left, because it changes the shape of a graded string and
  every `trace_note_contains` expectation has to be re-read against it first.
