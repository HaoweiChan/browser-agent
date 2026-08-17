# 009 — M6: live breadth, and what a suite going green does not prove

**Date**: 2026-08-17 · **Milestone**: M6 (A-phase, first implementation
milestone since the reopen) · **Outcome**: `near:` implemented as the
`structural` tier; seven silent-wrongness defects closed; live *cases* 1 → 3
domains and 1 → 3 task classes, of which 2 domains and 2 classes are verified
green; fast suite 60 → 69 cases, all green.

## Context

`prompts/008` reopened Task 1 for A-level with **planning documents only** —
implementation was explicitly forbidden at that step. The first batch of M6
(commit `a482791`) then wrote five live cases and ran them *before* any
implementation: 3 green, 2 red, and the reds defined the work. This record
covers the second batch, where the implementation happened.

## The prompt (verbatim, condensed)

> continue A-level implementation refer to @tasks/TODO.md , create pr when you
> finished a milestone, don't merge without consent

Two decisions were escalated mid-milestone rather than defaulted, and both
answers changed what shipped:

1. **`OPENROUTER_API_KEY` is absent from the session env.** Owner: "it is on
   Zeabur's env, are you able to use it?" Answer given: not without extracting
   a live secret into a local shell and a transcript, which CLAUDE.md rule 8
   exists to prevent. The live-planner case ships **unrun and declared**, with
   two clean paths recorded (run it against the deployment after the merge, or
   export the key locally for a `full` run).
2. **openlibrary.org went unreachable mid-milestone** (curl timeout; HN and
   archive.org fine; the same cases passed at 02:42 the same day). Owner: keep
   retrying before the PR rather than declaring the outage or swapping the
   domain.

## The resulting decision

Three implementation steps, each driven by a case already watched red:

- **`near:`** — in the contract since M1, in no code path. Document-order
  proximity to a visible anchor, reported as tier `structural` (the first
  mechanism ever to emit it). Six rules by the end of the milestone; three of
  them added after the reviews.
- **Closed target schema** — an unknown key stops the run as `failure:task`
  instead of being dropped.
- **Fillability guard in the executor** — an element that cannot hold a value
  is the wrong element, so `locate`, not `act`.

Plus one live TC3 case (`live-books-detail-upc`), two new fixtures, and
`planner: "live"` dispatch in the eval adapter so the TC4 case fails loudly on
a missing key rather than executing an empty stub plan.

**Then the milestone was reviewed while green, and that is where most of its
value came from.** The owner was asked whether to run the mandated
`cold-reviewer` and `spec-drift` subagents (this session's harness defaults to
not launching agents) and said run both. Between them they produced four more
defects and seventeen drift findings in code and docs that had just passed 65
cases:

- Three inputs on which the new `near:` answered confidently and wrongly, with
  `status: success`, `verdict: PASS`, and nothing in the trace to suggest
  doubt. Each needed a page shape `shop.html` — the repo's only offline
  listing — happens not to have.
- One recovery rung that dropped the constraint it was recovering.
- An over-claim of mine: I had written "3 live domains, 3 task classes
  exercised live" into five files. Two of those domains are verified; the third
  went unreachable mid-milestone, and the live TC2 case has never once been
  green. Corrected everywhere, and B-floor criterion 2 is now "substantially
  closed, not fully met" rather than "met".

Full rationale and the deliberately-unset list: `specs/decisions/ADR-006-m6-live-breadth.md`.

## AI recommendation: accepted / rejected / modified

Accepted. The one recommendation of mine that was **rejected by evidence** is
worth recording precisely, because it is the milestone's real lesson: I judged
the implementation done and the coverage claim honest when the suite went
green, and proposed the reviews mostly as a checklist item. The reviews then
found seven things, three of them wrong answers reported as successes and one
of them an over-claim in my own prose. The suite going green is not a review
and never was — that is the second consecutive milestone where the highest-value
defects came from a reader rather than the cases.

The other correction was self-inflicted and caught the same way: the first
draft of `near`'s tie-break carried the comment "forward wins, because a label
precedes its value more often than it follows". True of labels; the anchor in a
listing query is a *value*, and the rule confidently returned "Add to cart" as
the product that costs $24.50. A heuristic whose justification does not survive
being written out is a guess with a comment on it.

## Assumption → Eval contradiction → Correction

- Assumed: proximity means visual proximity, so bounding-box distance is the
  natural implementation.
  Eval said: `live-hn-item1-submitter` — the subline element's box contains all
  39 links, so every candidate ties at distance zero.
  Corrected: document-order distance over `querySelectorAll('*')`. The
  tie-break that came with it ("forward wins") was itself wrong and is the
  subject of a later entry. Recorded in ADR-006 and the browser-domain skill.

- Assumed: "nearest match to the anchor text" is the whole rule.
  Eval said: `live-books-detail-upc` returned the answer `"UPC"` — a scope-less
  `<th>` computes as role `cell`, so the label was its own nearest neighbour,
  at distance zero, with no error anywhere in the run.
  Corrected: exclude the anchor from its own candidate set; new fixture + case
  `near-excludes-its-own-anchor`, so the fast suite holds it shut without the
  live site. The first version of this fix excluded the anchor's ancestors too,
  which was a larger rule than any case tested and broke a different query —
  see the cold-review entry below.

- Assumed: `Locator.is_editable()` answers "can this element hold a value".
  Eval said: `relocate-fill-non-editable` stayed red — 1.49 returns True for a
  `<button>`, because it means "enabled and not readonly".
  Corrected: an explicit tag/type predicate (`agent.FILLABLE_JS`); readonly and
  disabled inputs deliberately stay `act`, since the element is right and only
  its state is wrong.

- Assumed: the eval-side anchor check and the runtime anchor check agree,
  because they read the same evidence.
  Eval said: `live-books-detail-upc` passed at runtime and was graded FAIL —
  the anchor was on the page but outside the 2000-character window stored
  around the extracted value.
  Corrected: the evidence window keeps a slice around the anchor too
  (`evidence-window-keeps-the-anchor`). A false FAIL is the safe direction and
  still a defect: M7 is about to compute verifier precision from these
  verdicts, and in a report it is indistinguishable from a run that really did
  read its answer off the wrong entity's page.

- Assumed: `near` was finished when its four cases and 61 others went green.
  Eval said: three cold-review inputs, each a wrong answer reported as
  `success` with a `PASS` verdict — the anchor "Total" binding to "Subtotal"
  and returning the subtotal as the order total (`near-anchor-substring`);
  "which row costs $24.50" answered with a different product at a different
  price, because the fix that excluded the anchor's own element also excluded
  the container the query wanted (`near-prefers-the-container`); "which product
  costs $24.50" answered "Add to cart", because the tie-break guessed
  (`near-equidistant-is-ambiguous`).
  Corrected: exact-before-substring anchor matching with deepest-match
  collapsing; containment outranks adjacency; both kinds of ambiguity are loud
  `locate` failures instead of tie-breaks. Plus a fixture (`shop-order.html`)
  carrying the two page shapes the repo had never had.

- Assumed: a relocation rung is the same request expressed at a different tier.
  Eval said: `relocation-preserves-near` — `index` was carried onto every rung
  and `near` was not, so a failed target relocated to a *weaker* one, resolved
  a different element, and reported success. `resolver-unknown-target-key`
  surviving one layer down.
  Corrected: rungs carry every intent key forward, and the contract says which
  keys those are.

- Assumed: three live domains with cases means three live domains covered.
  Eval said: openlibrary.org stopped responding partway through the milestone;
  four committed live runs show both its cases failing `failure:nav` at
  `page.goto` while the other two domains answer normally in the same runs. The
  live TC2 case has never produced the diagnosis it grades — `failure:act`
  before the fix, `failure:nav` since.
  Corrected: every claim rewritten to separate cases from verification (2 of 3
  domains, 2 of 3 classes green), criterion 2 downgraded from "met" to
  "substantially closed", and the outage declared as its own support-matrix row
  rather than folded into a pass count.

- Assumed (by the fixture set): fixtures the eval suite already has can stand
  in for real pages.
  Eval said: two of the four defects above needed a page longer than 2000
  rendered characters and a `<th>` without `scope`, and no fixture had either —
  every one of them was found by a live site first.
  Corrected: `shop-lamp-spec.html`, the first fixture whose rendered text
  exceeds the evidence window, with the dependency written into the
  browser-domain skill so a future edit cannot silently disarm two cases.
