---
name: browser-domain
description: Domain knowledge for the browser-agent task — Playwright pitfalls, locator tier semantics, fixture + mutation map, postcondition patterns. Load when implementing or debugging anything under src/browser/ or writing browser eval cases.
---

# Browser-agent domain knowledge

## Locator tiers (resolver order + why)

1. **role + accessible name** — survives cosmetic change; needs decent ARIA.
2. **text/label** — robust; breaks on copy changes (`button-text-renamed`).
3. **stable attrs** (id, data-*, name) — precise; most brittle (`ids-renamed`).
4. **structural relations** — last resort; killed by `wrapper-nesting`.

Plans carry `SemanticTarget{role, name, text?, near?, index?}` — NEVER concrete
selectors (CLAUDE.md hard rule 6). `docs/evals/failure-taxonomy.md` describes
ranking by uniqueness × visibility × tier prior × cached history — **none of
that is built**: tiers are tried in order, a tier wins by resolving to exactly
one element (or by `index`/`near` naming which one), and there is no cache.
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
`indexOf` is -1 and everything ties), and no fixture has one.

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
- `?mut=<name>` applies deterministic HTML transforms:
  B-floor: `ids-renamed`, `button-text-renamed`, `wrapper-nesting`
  (each breaks exactly one locator tier — that's the point).
  B-strong: `classes-scrambled`, `element-reordered`, `duplicate-labels`,
  `render-delayed`, `overlay-modal`, `a11y-stripped`.

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
  check for dialog/modal roles before retrying anything.
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
