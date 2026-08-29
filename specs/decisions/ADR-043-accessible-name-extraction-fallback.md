# ADR-043: Extract an image link's accessible name when rendered text is empty

Date: 2026-08-30
Status: accepted

**Ruling**: `extract` reads rendered text first and, only for an image-bearing
link whose text is empty, reads that same link's browser-computed accessible
name.
**Because**: Open Library repeatedly resolved a unique image link whose
accessible name carried the requested author, then failed because the executor
read only `innerText`.
**Enforced by**: `extract-falls-back-to-accessible-name` and
`trap-empty-extraction`.

## Decision

1. Keep rendered text as the primary source. The fallback runs only for a
   single `extract` whose resolved image link returned empty rendered text;
   `extract_all` is unchanged.
2. Read Playwright's ARIA snapshot for that locator. This is the same
   browser-computed accessibility view that made the target observable and
   resolvable. Require the resolved role to be `link` and the element to carry
   an `img[alt]`: an arbitrary control's accessible name can be only its label,
   as `trap-empty-extraction` demonstrates, and must not become an answer.
3. Append a fallback value only to that extraction's evidence window. It does
   not become rendered page text, cannot satisfy a postcondition, and does not
   alter page-change detection. If the accessibility read is unavailable or
   empty, retain the existing loud `failure:extract`.
4. Add no selector, DOM path, site name, retry, model call or dependency to
   production code.

## Evidence and scope

The minimal authored fixture contains one uniquely named image link with no
rendered text. Before the fix it resolved at the `role` tier and ended
`failure:extract` with `extraction returned empty text`; after the fix it
returns `Ana Soto`, is grounded in the locator's ARIA evidence and passes the
verifier.

This closes only the deterministic empty-extraction mechanism seen on Open
Library (`bdd9ebf7`, then ADR-042 runs `4947a902`, `e1dece67`, `095e81c2`). It
does not claim the full live task now passes: that page's accessible name is a
long cover description and the live judge still has to decide whether it
answers the author question. It does not address quotes.toscrape.com's distinct
label-without-value planner target, and it does not close T-M40-5-3's broader
rep-level nondeterminism.
