---
name: browser-domain
description: Domain knowledge for the browser-agent task — Playwright pitfalls, locator tier semantics, fixture + mutation map, postcondition patterns. Load when implementing or debugging anything under src/browser/ or writing browser eval cases.
---

# Browser-agent domain knowledge

## Locator tiers (resolver order + why)

1. **role + accessible name** — survives cosmetic change; needs decent ARIA.
2. **text/label** — robust; breaks on copy changes (`button-text-renamed`).

**Both name tiers match WHOLE-STRING and CASE-INSENSITIVELY** (`_whole_string`,
T-M42-20). Not `exact=True`, which buys the whole-string refusal
(`resolver-substring-name`) and a case-sensitivity promise nothing can keep:
`observe()` reads the accessible name from Chromium's `accessibility.snapshot()`,
which APPLIES CSS `text-transform`, and Playwright's locator engine computes its
own name and does not. A `<label>` under `text-transform: uppercase` therefore
reaches the planner shouting and comes back unresolvable — that is how M42's
live clause died 3/3 in both modes on a control the page rendered perfectly.
The regex is anchored, so substring ambiguity is still refused; whitespace is
collapsed to `\s+` because Playwright normalises whitespace for STRING matching
but tests a regex against the element's RAW text. Two names differing only in
case now collide as an ambiguity and go to M38's narrowing rungs, which is the
honest outcome. Pinned by `observe-uppercase-label-name-resolves`, the only case
that closes the `observe` -> `resolve` loop instead of grading each end alone —
and the reason it existed to be broken for a milestone is that no other case
does (debt: `T-M42-20-D1`).
3. **stable attrs** (id, data-*, name) — precise; most brittle (`ids-renamed`).
4. **structural relations** — last resort; killed by `wrapper-nesting`.

Plans carry `SemanticTarget{role, name, text?, near?, index?}` — NEVER concrete
selectors (CLAUDE.md hard rule 6). `docs/evals/failure-taxonomy.md` describes
ranking by uniqueness × visibility × tier prior × cached history — **none of
that is built**: tiers are tried in order, a tier wins by resolving to exactly
one element (or by `index`/`near` naming which one, or by an M38 narrowing
rung), and there is no cache.
Those five keys are the whole schema; a sixth stops the run as `failure:task`
rather than being dropped (`resolver-unknown-target-key`).

**`near:` (M6) is how tier 4 is reached.** Among a tier's matches, take the one
closest to a visible anchor string. Six rules, each bought with a case — and
three of them bought *after* the mechanism shipped green on four cases of its
own, because every one needed a page shape `shop.html` does not have. Touching
this function without re-reading them is how it went wrong the first time.

- **Document order, not pixels.** A Hacker News subline's bounding box contains
  every link in it, so geometric distance ties at 0 for all of them
  (`live-hn-item1-submitter`). `all.indexOf()` over `querySelectorAll('*')`
  separates them.
- **The anchor is not its own neighbour.** A scope-less `<th>` computes as role
  `cell`, so `{role: cell, near: "UPC"}` answered `"UPC"` — the label cell, at
  distance zero (`near-excludes-its-own-anchor`).
- **…but a candidate that wraps the anchor beats every neighbour.** Excluding
  ancestors as well as the anchor (the obvious first fix for the rule above)
  breaks the commonest proximity query there is — the row or card holding the
  value — and hands back the *next sibling* container instead
  (`near-prefers-the-container`). Only `c === anchor` is excluded outright.
- **Match the anchor exactly first.** `get_by_text` is a case-insensitive
  substring match, so `"Total"` binds to `"Subtotal"`
  (`near-anchor-substring`). Substring is the fallback, because a `near` anchor
  is usually a fragment of a longer line ("points by").
- **Refuse, don't tie-break.** Two anchor matches that don't contain one
  another, or two candidates at equal distance, are a loud `locate` failure.
  The original "forward wins, a label precedes its value" heuristic is a fact
  about labels applied to a value, and it answered "Add to cart" as the product
  costing $24.50 (`near-equidistant-is-ambiguous`).
- **Not a relocation rung, but rungs carry it.** No rung is *built* from
  `near` — a rung comes from the failed target's own strings and a proximity
  anchor is a different element's text. But a rung must carry `near` (and
  `index`) forward, or it answers an easier question than the one that failed
  and reports success for it (`relocation-preserves-near`).

Known holes, both declared in the support matrix: `near` degenerates inside
shadow DOM (`querySelectorAll('*')` doesn't pierce open shadow roots, so
`indexOf` is -1 and everything ties). **A fixture now has one** —
`frames-host.html`, added by M42 — so the second half of that sentence is no
longer the reason it is unfixed; `NEAREST_JS` simply has not been touched.

**Frames (M42, ADR-028).** A locator never crosses a frame boundary and
`page.accessibility.snapshot()` stops at one, so before M42 an iframe's contents
were in no observation at any budget and resolved at no tier. `observe()` now
continues into every child frame via Playwright's own `aria_snapshot()`, and
`resolve()` builds the same tiers in each scope, main frame first. `near` is
scoped to the frame its candidates are in.

**Shadow roots are two different questions, and only one was broken.** An open
shadow root is already in the accessibility tree and already resolvable —
`observe` listed the button and `resolve` clicked it before M42. What was blind
was the EVIDENCE: `page.inner_text("body")` does not traverse shadow roots, so a
correct read was failed as ungrounded, `text_visible` could never hold over
shadow content, and `page_changed` could not see a shadow-only mutation. Read
the page through `observe.page_text(page)` — never `page.inner_text("body")` —
and that stays fixed.

**Narrowing (M38, ADR-026) is where an ambiguity goes before it fails.** Same
warning as `near:` — three rungs, each bought with a deployment run, and the
guards are the whole thing. They run AFTER the tier loop, never inside it: a
clean single match at the text tier outranks a narrowed one at the role tier.

- **Two shared refusals gate rungs 1-2**, and they are about whether the
  ambiguity may be settled at all: the step must READ (`extract`), and the task
  must ask for ONE thing. Narrowing a click presses a control nobody named
  (`resolver-refuses-narrowing-a-click` — the only case that pins this;
  `l4-shop-duplicate-labels` does NOT, whatever three documents said before
  PR #42 R2, because its two buttons also differ in text). A plural ask answered
  from one match is wrong by omission, and this test sat inside rung 2 for one
  round, so rung 1 answered plural asks with an anchor
  (`resolver-refuses-plural-with-anchor`).
- **Rung 1, `anchor-proximity`.** The step's identity anchor reused as a `near`.
  Opportunistic, so unlike `near` an anchor that names two places falls through
  to rung 2 instead of raising — loudness belongs to what the plan asked for
  (`resolver-narrows-by-anchor-proximity`).
- **Rung 2, `document-order`.** The first match, under four conjuncts: no
  `index` (structural), the two shared refusals, and matches interchangeable in
  role AND rendered text. The two halves of "interchangeable" are not redundant
  — role is vacuous on the role tier and text is vacuous on the text tier
  (whole-string; near-vacuous rather than vacuous since T-M42-20 made it
  case-insensitive), so each is the whole guard on the other's tier:
  `resolver-refuses-mixed-roles` (role), `resolver-refuses-different-readings`
  (text). Interchangeability gates rung 2 ONLY — rung 1 is *for* candidates
  that differ.
- **Every conjunct is pinned by ablation, not by argument.** Each guard case is
  red when and only when its own conjunct goes; check that whenever you touch
  one, because three of the original five cases passed for reasons unrelated to
  the guard they named — a degenerate anchor, a second conjunct masking the
  first, a fixture whose document order matched the right answer.
  `_PLURAL_ASK` is three English shapes plus boundary-free CJK markers (`\b`
  never matches inside a CJK run), one case per phrasing; D29 carries the rest
  of the ceiling.
- **Rung 3, `near-normalised` / `near-prefix`.** Two more anchor passes after
  exact and substring: typographic quote/dash variants with whitespace runs
  collapsed, then the anchor's first 40 characters
  (`resolver-near-normalises-typography`).
- **The rung is named in the trace `note`, and wears no `recovery` label** —
  nothing failed and no ladder ran (the ADR-020 ruling). Graded through the
  existing `trace_note_contains` expect key.

## Fixture map

Served by the same FastAPI app (`GET /fixtures/{name}`); the eval adapter
starts that app on a loopback port, so eval and production share one serving
path. `src/browser/mutate.py` is the transform layer.

- `/fixtures/shop.html` — catalogue: search box, sort control, 4 products,
  detail pages (`shop-lamp-std|lamp-pro|clock|rug.html`). Ground truth:
  authored content. `Aurora Desk Lamp` / `Aurora Desk Lamp Pro` are a
  deliberate near-miss pair; SKUs (`LAMP-STD`, `LAMP-PRO`, …) are the
  distinguishing identity anchors.
- `/fixtures/forms.html` — multi-field form + server-rendered confirmation.
  Ground truth: `GET /fixtures/forms/state` returns the last submission;
  `POST /fixtures/forms/reset` clears it before a case.
- `/fixtures/hello.html` — M1 walking-skeleton page, still the cheapest case.
- `/fixtures/late-options.html` (T-M42-20) — a `<select>` that is in the DOM at
  `load` with ZERO `<option>`s, filled from `fetch('/fixtures/late-options.json')`,
  an endpoint that sleeps `server.LATE_OPTIONS_DELAY_S` (1.0s) so the page waits
  on the NETWORK rather than on a page-side timer. The only fixture of that
  shape — `loop-lab.html` paints late but on a click, from a timer, and its
  `<select>` is fully populated in the document — and its absence is why 213
  green cases missed the S1 half M42 was built for. The delay is squeezed from
  both sides: shorter and the options land before the select step's first read
  (measured at ~0.1s after `goto`), so the case passes and grades nothing;
  longer and it is pure wall clock inside a published band. Case:
  `action-select-option-waits-for-fetch-painted-options`.
- `/fixtures/slow-asset.html` — references `/fixtures/hang.png`, an endpoint
  that sleeps 120s, so the `load` event never fires while the document is
  complete in milliseconds. openlibrary.org's edition pages behaved exactly
  like this. Do NOT write an `observe`-kind case against it: that harness has
  its own `goto` and still waits for `load`, so it would hang for 20s. Cases:
  `nav-load-event-never-fires`, `nav-action-load-event-never-fires`.
- `/fixtures/shop-order.html` (M6) — order summary + a one-line catalogue, the
  two shapes that broke `near` in cold review. "Total" is a *suffix* of
  "Subtotal" (anchor matching), and the order line ends in "Add to cart" so the
  product link and the CTA sit equidistant from the price (tie handling).
  Labels are `<td>`, not `<th>`, so the cases cannot pass on a role-computation
  accident. Cases: `near-anchor-substring`, `near-equidistant-is-ambiguous`.
- `/fixtures/shop-lamp-spec.html` (M6) — the label/value spec table, plus the
  only fixture whose rendered text passes `agent.PAGE_TEXT_KEEP` (2000 chars).
  Two things depend on both facts: `<th>` carries no `scope`, so the label
  computes as role `cell` like the value beside it, and the serial line sits
  past the evidence window from the table. Lengthening or reordering that page
  silently disarms `near-excludes-its-own-anchor` and
  `evidence-window-keeps-the-anchor`.
- `/fixtures/forum-thread.html` (M38) — the ambiguity page: two links sharing
  an `aria-label` and reading differently, three identical `<small>` author
  matches, a featured quote rendered with typographic quotes and truncated
  before the plan's `near` string ends, and one string ("4.7") in a `<strong>`
  and an `<em>` — same reading, different roles, the shape rung 2 must refuse.
  Layout is load-bearing twice: rung 1 and `near` both decide by DOCUMENT-ORDER
  distance, so inserting an element between a byline and its subline, or
  between the featured quote and its credit line, moves which candidate is
  nearest and silently disarms two cases.
- `?mut=<name>` applies deterministic HTML transforms (`src/browser/mutate.py`
  has the full table). B-floor, one locator tier each: `ids-renamed`,
  `button-text-renamed`, `wrapper-nesting`. B-strong (M8), admitted on "breaks
  a capability a plan stands on" rather than "is a tier": `duplicate-labels`
  (role+name *uniqueness* → the catalogue's only `ambiguous-match`),
  `a11y-stripped` (button → div; text tier survives, and the submit shim keeps
  the fixture's own form alive), `element-reordered` (positional `index`;
  **nothing recovers it** and the wrong row is reported as success),
  `render-delayed` (content 10s late; the resolver never waits), `overlay-modal`
  (resolves fine, cannot be clicked → the act/replan family).
  `classes-scrambled` is **dropped, not missing** — no class tier exists, so it
  would break nothing (ADR-009).

**A fixture must survive its own mutations.** `ids-renamed` renames every
`id`/`for`/`data-testid`, so fixture scripts resolve their own elements by
tag/aria-label, never by id — otherwise the mutation breaks the page instead
of the agent's stable-attr dependency, and the L4 case measures nothing
(learned the hard way: `l4-shop-ids-renamed`, guarded by
`mutation-catalog-integrity`).

Fixture code may know its own DOM; it must never leak selectors to the
executor (rule 6 boundary — cold-reviewer checks this).

## Roles that are addressable (verified against Playwright 1.49)

Nameable and resolvable: `heading`, `link`, `button`, `searchbox`, `textbox`,
`list`, `listitem` (unnamed, use `index`), `group`, `status`, `cell`,
`rowheader`. **Not** nameable: `definition`, `term`, `code`, `emphasis`,
`strong`, `caption`, `time` — ARIA prohibits an author name on these, so
Chromium's snapshot shows a name that `get_by_role(..., name=)` will never
match. `observe()` blanks those names for exactly that reason.

## Postcondition patterns (expected_state)

Prefer, in order: `url_contains` / `url_matches` · element with role+name
visible · form-field value readback · fixture `/state` assertion ·
page-text-contains (identity anchor: the task's entity string).

Every *click* should carry a machine-checkable `expected_state` — but note
where that is enforced: the executor records `postcondition_ok: null` and
carries on, and it is the **verifier** that fails the run for an unverified
state-changing step (`postcondition-unverified-click`). A `fill` verifies
itself by field readback. An `extract` has no step postcondition at all; the
"value appears in the page text" check is the verifier's `grounded` predicate at
grading time, not something the executor asserts.

## Playwright pitfalls worth remembering

- Use the accessibility snapshot (`page.accessibility.snapshot()` /
  `aria` locators) as the primary observation; raw DOM dumps blow token budgets.
- Auto-waiting hides `render-delayed` bugs in dev but not under mutation —
  always assert the postcondition, never sleep.
- `strict` mode violations (multiple matches) are a `locate/ambiguous` failure,
  not an excuse for `.first()`.
- Overlay interception surfaces as a timeout on click — classify as `act`,
  check for dialog/modal roles before retrying anything. Measured at M8 and no
  longer just advice: `l4-shop-overlay-modal` costs a full 10s click timeout,
  classifies `act`, and is rescued by replan, not by relocation. Relocation is
  useless here on purpose — the element was found.
- **`page.goto` defaults to `wait_until="load"`**, which waits for every image,
  stylesheet and subframe — none of which any locator tier reads. One hanging
  subresource then makes a fully rendered page `failure:nav`. Navigate through
  `agent.navigate()`: `domcontentloaded` plus a *bounded* 2s wait for `load`.
  Don't reach for `networkidle` — it is stronger for hydration and costs 500ms
  on every navigation, healthy or not (+34s on the fast suite, measured).
- **`page.screenshot()` waits for fonts**, and on a page whose `load` never
  fires that wait runs to its 30s default — per step. Always pass an explicit
  `timeout`. More generally: a `try/except` whose comment says "best-effort" is
  a place to check for an unbounded wait, not a reason to skip it. That comment
  is why this one survived a close review of the same block.
- `Locator.is_editable()` answers "enabled and not readonly" and returns **True
  for a `<button>`** (1.49). It cannot be used to ask whether an element can
  hold a value — that needs an explicit tag/type check (`agent.FILLABLE_JS`),
  or a fill onto the wrong element reports `act` for a `locate` root cause
  (`relocate-fill-non-editable`).
- Headless Chromium in Docker needs `--no-sandbox` in most PaaS images; memory
  ≈ 300–500 MB per context — the semaphore is not optional.
- Bot-block/challenge pages (Cloudflare et al.): detect → classify `env` →
  stop + mark unsupported. Never attempt evasion.

## LLM calls (OpenRouter)

Planner default `anthropic/claude-sonnet-4.5`, planning/replanning only.
Every call goes through the budget counter (tokens + $ from the response
usage fields) and is stubbed at the module boundary in the `fast` suite.
