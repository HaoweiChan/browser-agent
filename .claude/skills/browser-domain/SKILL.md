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

Plans carry `SemanticTarget{role, name, text?, near?}` — NEVER concrete
selectors (CLAUDE.md hard rule 6). The Resolver ranks candidates by
uniqueness × visibility × tier prior × cached history.

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
page-text-contains (identity anchor: the task's entity string). Every action
step MUST carry a machine-checkable `expected_state`; an extraction step's
postcondition is "extracted value appears in page text".

## Playwright pitfalls worth remembering

- Use the accessibility snapshot (`page.accessibility.snapshot()` /
  `aria` locators) as the primary observation; raw DOM dumps blow token budgets.
- Auto-waiting hides `render-delayed` bugs in dev but not under mutation —
  always assert the postcondition, never sleep.
- `strict` mode violations (multiple matches) are a `locate/ambiguous` failure,
  not an excuse for `.first()`.
- Overlay interception surfaces as a timeout on click — classify as `act`,
  check for dialog/modal roles before retrying anything.
- Headless Chromium in Docker needs `--no-sandbox` in most PaaS images; memory
  ≈ 300–500 MB per context — the semaphore is not optional.
- Bot-block/challenge pages (Cloudflare et al.): detect → classify `env` →
  stop + mark unsupported. Never attempt evasion.

## LLM calls (OpenRouter)

Planner default `anthropic/claude-sonnet-4.5`, planning/replanning only.
Every call goes through the budget counter (tokens + $ from the response
usage fields) and is stubbed at the module boundary in the `fast` suite.
