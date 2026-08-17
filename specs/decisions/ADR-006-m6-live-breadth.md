# ADR-006: What M6 (live breadth) implemented, and what live evidence still cannot say

Date: 2026-08-17
Status: accepted

## Context

The B-freeze met 5 of 6 exit criteria. Criterion 2 was partial for one reason:
one live domain, one task class, and a held-out probe that scored 2/8 on
answer-seeking tasks. `docs/plans/active/task1-a-level-plan.md` ranked live
breadth first because the gap was measured rather than suspected.

M6 was written eval-first in two batches. The first (commit `a482791`) added
five live cases and ran them before any implementation existed; three passed,
two were red, and the reds named the work. This ADR records the second batch —
the implementation — and what the resulting numbers do and do not license.

## Decision 1 — `near:` is implemented, and it is the `structural` tier

`near:` had been in the target schema since M1 and in no code path. The
resolver dropped it. Live breadth is what made that expensive: on a real site
the interesting value usually has no name of its own, only a label beside it —
a submitter after "N points by", a price in a spec table. Positional `index`
reaches those by counting, which is the form `live-books-travel-price` uses and
the support matrix declares `unreliable`.

The rule: among a tier's matches, take the one closest **in document order** to
a visible anchor string. Six properties are load bearing, and every one of them
cost a red case — three of those cases written after the first implementation
shipped and was cold-reviewed, each describing a run that reported a confident
wrong answer with `status: success`, `verdict: PASS` and nothing in the trace
to suggest doubt.

- **Document order, not layout.** Hacker News' subline is one element whose
  bounding box contains all 39 links in it; geometric distance ties at zero for
  every one. Document order separates them (`live-hn-item1-submitter`).
- **The anchor is not its own neighbour.** A `<th>` without `scope` computes as
  role `cell`, so `{role: cell, near: "UPC"}` returned `"UPC"` — the question
  restated as its own answer, at distance zero, with no error anywhere in the
  run (`near-excludes-its-own-anchor`, found by `live-books-detail-upc` on its
  first run).
- **A candidate that wraps the anchor outranks every neighbour.** The first fix
  for the point above excluded the anchor *and all its ancestors*, which is a
  strictly larger rule that no case tested — and it breaks the commonest use of
  proximity there is, the row or card that contains the value. Worse than
  unreachable: the next sibling container won instead, so "which row costs
  $24.50" answered with a different product at a different price
  (`near-prefers-the-container`).
- **The anchor is matched exactly before it is matched loosely.** `get_by_text`
  is a case-insensitive substring match, so an anchor of `"Total"` bound to
  `"Subtotal"` and returned the subtotal as the order total
  (`near-anchor-substring`). The role tier had carried this exact lesson since
  M1 (`exact=True`, `resolver-substring-name`); the anchor side shipped without
  it. Substring remains the fallback, because a `near` anchor is usually a
  fragment of a longer line.
- **Ambiguity refuses instead of guessing, on both sides.** Two anchor matches
  that do not contain one another mean the string names two places on the page;
  two candidates equidistant from the anchor mean the plan did not identify an
  element. Both are loud `locate` failures. The original tie-break — "forward
  wins, because a label precedes its value more often than it follows" — states
  a fact about labels and was applied to values: on a listing row the product
  link sits one element before the price and the call-to-action one element
  after, so it answered "Add to cart" as the product costing $24.50
  (`near-equidistant-is-ambiguous`).
- **It is not a relocation rung, but it survives one.** A rung is *derived*
  from the failed target's own strings, and a proximity anchor is a different
  element's text, so no rung is ever built out of `near` — `structural` is
  reachable only when a plan asks for it, and the "locator broken at both
  reachable tiers is not recovered" limitation stands unchanged. But a rung
  must carry `near` forward, exactly as it already carried `index`: dropping it
  let a rung answer an easier question than the one that failed and report
  success for it (`relocation-preserves-near`, found by the M6 drift audit).

This is the first mechanism in the project to emit `structural`. `attrs`
remains named in the taxonomy and implemented nowhere.

**The reviews are the reason this section is six bullets and not three.** The
first implementation was green on 65 cases, including four written specifically
for `near`. A cold read of that green code produced three inputs on which it
answered confidently and wrongly, and every one of them turned on a shape the
repo's only offline listing (`shop.html`) happens not to have: a label that is
a suffix of another label, a row with anything after the price, a container
worth asking for. That is the M5 lesson repeating — an eval set written by the
author of the code is blind where the author was already looking — and it is
now the second consecutive milestone where the highest-value defects came from
a reader rather than the suite.

## Decision 2 — three ways a run was quietly wrong, all fixed at the shared path

M6's live cases found three defects that fixture cases had never produced. All
three are the same family — the run reports on something other than what it
did — and all three are fixed once, where every caller routes through, rather
than at the site that happened to expose them.

| Defect | Was | Now | Case |
|---|---|---|---|
| An unimplemented target key is dropped | `{role: link, near: X}` ran as `{role: link}`; the plan's meaning evaporated silently | any key outside the five-key schema stops the run as `failure:task`, naming the key | `resolver-unknown-target-key` |
| A fill onto an element that cannot hold a value is `act` | relocation "rescued" an unresolvable searchbox onto the literal text "Search", a submit button; the fill error read `act` for a `locate` root cause, steering the wrong ladder | the executor checks fillability before filling and raises `locate`; a readonly or disabled input is the right element in the wrong state and stays `act` | `relocate-fill-non-editable` |
| A correct run graded FAIL on stored evidence | the identity anchor was checked against a 2000-char window around the value; on a product page with a long description the title falls outside it | the window keeps a slice around the anchor as well | `evidence-window-keeps-the-anchor` |

The guard for the second one deliberately sits in the executor's fill path, not
in the relocation rung that exposed it: a first-attempt plan targeting a
non-fillable element is the same defect, and only a shared guard covers both.

`Locator.is_editable()` is not that guard. It answers "enabled and not
readonly" and returns True for a `<button>` (Playwright 1.49) — the first
attempt at this fix passed its own case for the wrong reason until the eval
said otherwise.

## Decision 3 — hard rule 6 has a carve-out, and it is written down now

The cold review asked a fair question the repo had never answered: `stub_plan`
hands the executor a specific site's accessible names and URL slugs
(`live-books-detail-upc` passes `"full-moon-over-noahs-ark"` as a postcondition),
and CLAUDE.md rule 6 forbids feeding site-specific recipes to the executor.

**Ruling: a `stub_plan` is injected planner *output*, not execution policy, and
the rule governs policy.** The boundary rule 6 protects is that nothing in
`src/browser/` decides what to do by knowing a particular site; a plan is
exactly the artifact that is allowed to name page-specific things, because a
real planner produces one by reading the page. Substituting a recorded plan for
a model call is the same substitution the whole `fast` suite is built on
(cost-discipline), and it changes who authored the plan, not what the executor
is permitted to know.

Two conditions keep the carve-out honest, and both hold today: no fixture or
case data reaches `src/browser/` outside a plan, and every case that stubs a
plan is measuring the resolver/executor/verifier path, never planning quality —
which is why the support matrix declares planning unmeasured on every domain
including the live ones. A stub plan that encoded a *recovery* recipe rather
than a first attempt would breach this; none does.

## Decision 4 — what stays declared rather than fixed

Three findings from the same review are real, reproducible, and deliberately
not fixed in M6. Each is now a row in `docs/support-matrix.md`; none can
produce a wrong answer reported as success.

- **`near` degenerates inside shadow DOM.** Playwright's locators pierce open
  shadow roots; `document.querySelectorAll('*')` does not, so an anchor or
  candidate inside one scores `indexOf === -1` and distance becomes
  meaningless. No fixture in the repo uses shadow DOM, so a fix would ship
  untested — which is how the first three `near` defects got here.
- **A fill into a contenteditable dies on readback.** `FILLABLE_JS` admits
  `isContentEditable`, and the field-readback check calls `input_value()`,
  which throws on anything that is not a form control. The fill *worked*; the
  run is failed `act`. Loud and in the safe direction, but it is a wrong class
  on a successful action — the same family M6 just fixed twice — and it wants a
  contenteditable fixture before it wants a code change.
- **The rung count is inflated by element-identical rungs.** A relocation rung
  is guaranteed to be a different *tier*, never a different *element*: a failed
  `{text: "Search"}` relocates to `{role: button, name: "Search"}`, provably the
  same button, and is counted in `recovery_rungs`. It cannot create a false
  green (the run still fails), but every "N rungs tried" figure this project
  publishes is an upper bound, not a count of genuinely distinct attempts. This
  sharpens ADR-005's "relocation rung 1 ignores the target's role" rather than
  replacing it.

## Decision 5 — what the M6 numbers license

**Coverage now.** Live cases exist for three domains (books.toscrape.com,
news.ycombinator.com, openlibrary.org) and three task classes (TC1, TC2, TC3),
against one domain and one class at the freeze. What is *verified* is smaller
than that, and the smaller number is the one that counts:

| | Cases | Green against the M6 implementation |
|---|---|---|
| Live domains | 3 | **2** — books.toscrape.com, news.ycombinator.com |
| Live task classes | 3 | **2** — TC1, TC3 |

**Stated plainly, because the case count flatters otherwise:**

- **openlibrary.org has not been reached since the implementation landed.**
  `live-ol-edition-title` passed once, in the committed pre-implementation run
  `evals/report/20260817-024235-live.json`; from ~11:00 on 2026-08-17 the host
  stopped responding entirely (four committed live runs, both OL cases
  `failure:nav` at `page.goto`, while books.toscrape.com and
  news.ycombinator.com answered normally in the same runs). The third domain is
  therefore *evidenced but not currently verified*, and no claim here rests on
  it.
- **The live TC2 case has never been green.** It grades a diagnosis: Open
  Library's search field is invisible to both the accessibility tree and the
  light DOM, and the pipeline must say `failure:locate` and fabricate nothing.
  It ran twice — `failure:act` before the fix (the laundering bug it was
  written to expose) and `failure:nav` since the outage. The mechanism it
  drives is fixed and proven offline by `relocate-fill-non-editable`; the live
  half is owed. Exercising a class, diagnosing it correctly, and supporting it
  are three different claims.
- Every green live case still runs a **hand-written plan**. The live planner
  has never been measured on any of the three domains. `live-books-cheapest-travel`
  is the case that would change this and it is **unrun**: it needs
  `OPENROUTER_API_KEY`, and the adapter now dispatches `planner: "live"` for
  it rather than silently executing an empty stub plan (CLAUDE.md rule 4).
  Until that run exists, live coverage means the resolver/executor/verifier
  path handles the real DOMs it has reached — nothing about planning quality.
- The one-hop-deep capability ceiling from the M5 probe is **untouched by M6**.
  Nothing here adds compare, rank or filter to the plan vocabulary.

**Still unset, deliberately.** Verifier precision/recall (M7 owns it; M6's
evidence-window defect is precisely the kind of false FAIL that would corrupt
it if measured today), the full mutation catalog (M8), and any cost or latency
number for live planning (M9).

## Consequences

- `specs/001-browser-contract.md` documents `near` and the closed schema; the
  `structural` tier is no longer described as unreachable.
- B-floor criterion 2 moves from *partial* to **substantially closed, not
  fully met**: three domains and three task classes have live cases, two of
  each are green. It stays open until openlibrary.org is reachable and the
  live TC2 case produces its diagnosis, which is the first thing M7 or M8
  should re-run.
- Four support-matrix limitations move to **closed at M6**, each citing the
  case that proves it; two M5 rows are corrected rather than deleted, because
  the older positional cases still exist and still count.
- Live cases remain `full`/`live`-tagged and never gate a commit. The gate is
  the `fast` suite, which is where every M6 mechanism also has a case — the
  live sites found the defects, the fixtures hold them shut.
