# Task 1 problem definition — generalized browser automation agent

Operational definition of what we are building, precise enough to evaluate.
Scope tags: **MUST** = B-floor, **SHOULD** = B-strong (time permitting),
**BACKLOG** = post-freeze. Rubric cells per `docs/product/assignment-requirements.md`.

## Goal

Accept one natural-language task description and execute it in a real browser
against websites the agent has no site-specific code for, returning a verified,
evidence-backed result — or a loud, classified, honest failure.

## User-visible behavior

- **Input**: one NL task (English or Chinese) + optional starting URL.
  No cross-task session memory at B-level.
- **Output** (full contract lands as `specs/001-browser-contract.md` at M1 —
  task id is `browser`, so cases carry `"task": "browser"` and the adapter lives
  at `src/browser/eval_adapter.py`; `browser-agent` is not a valid Python module
  path for the runner's import):

```json
{
  "status": "success | partial | failure:<class> | unsupported",
  "answer": "extraction / confirmation / null",
  "evidence": { "trace": "steps.jsonl", "screenshots": [], "final_state": {} },
  "budgets_spent": { "actions": 0, "tokens": 0, "usd": 0.0, "ms": 0 }
}
```

- **Pre-flight scope screening** [MUST → honesty]: tasks requiring login/auth,
  CAPTCHA, payment, destructive/irreversible actions, or file downloads are
  answered `unsupported` with the reason, before any browsing. Reviewers will
  probe out-of-scope; the crisp refusal is graded honesty evidence.

## Action vocabulary

navigate, click, fill, select, scroll, wait-for, extract, read-accessibility-tree.
Excluded: file download/upload, multi-tab fan-out, browser-profile mutation.

## Task taxonomy

Candidate list critiqued: "element relocation after UI changes" is a robustness
*dimension* (any task class can face it), not a task class; "search" and
"filtering" are kept as separate classes because their failure modes differ
(query formulation vs stateful control verification).

| Class | Definition | Example |
|-------|-----------|---------|
| TC1 single-page extraction/QA | Read/answer from one page | "What is the founding year listed on this page?" |
| TC2 search-then-extract | Formulate query → pick result → read | "Find the author of the book 'Sapiens' on Open Library" |
| TC3 multi-step navigation | Reach a target state through ≥2 page transitions | "From the HN front page, open the comments of the top story" |
| TC4 filter/sort/configure | Operate stateful controls, verify resulting state | "Sort the catalogue by price ascending and name the cheapest item" |
| TC5 form interaction | Fill + submit non-destructive forms | "Submit the contact form with these details" (fixture) |

Orthogonal robustness dimensions (cross any TC): dynamic rendering, ambiguity,
DOM perturbation (mutations), expected-failure handling.

## What "generalized" means here

One policy over generic observations (accessibility tree + DOM). Enforced by
CLAUDE.md hard rule 6 (knowledge-placement):

- The **production execution policy** contains no site-specific selectors, DOM
  paths, or navigation recipes — greppable, hence testable.
- **Eval/fixture code MAY use site-specific selectors** strictly for ground-truth
  verification and controlled fault injection, and must never feed them to the
  executor.
- Per-site data allowed anywhere: start URL, rate limit, ground-truth API endpoint.

cold-reviewer enforces this boundary across `src/`, config, and `evals/`.

## Initial domains

| Domain | Type | Why chosen | Ground truth |
|--------|------|-----------|--------------|
| shop fixture (self-hosted) | MUST | mutation-controllable, deterministic | authored by us |
| forms fixture (self-hosted) | MUST | verifiable submissions | `/state` endpoint |
| Wikipedia | MUST (≥1 live at B-floor from this row down) | structured, stable, legal | public API cross-check |
| Hacker News | SHOULD | list/rank semantics | Firebase API |
| books.toscrape.com | SHOULD | built for scraping practice | stable static content |
| Open Library | SHOULD | search + facets | public API |
| one hostile JS-heavy site | SHOULD | div-soup, weak ARIA — chosen at M2 by testing candidates | none; feeds the unsupported list honestly |

Live sites selected for: legal/polite to automate, no auth needed, structurally
diverse, and (Wikipedia/HN/Open Library) an **independent public API usable as
ground truth** so the verifier does not depend on the browser path.

## Success / partial / failure / silent failure

- **Success**: OutcomeVerifier confirms the user's goal from evidence
  (deterministic predicates first; see `docs/evals/evaluation-methodology.md`).
  The executor never grades itself.
- **Partial**: only for enumerable multi-item tasks — correct subset delivered
  plus an explicit statement of what is missing.
- **Failure**: exactly one top-level failure class attached
  (`docs/evals/failure-taxonomy.md`), loud, with evidence.
- **Silent semantic failure** (the distinction the assignment grades): executor
  claims success but ground truth / verifier disagrees. Execution failure is
  detected *by* the agent; semantic failure must be detectable *despite* the
  agent. We measure it with trap cases and the disagreement log, and design the
  verifier so claimed success is never the input to its own verification.

## Non-goals

Login/auth flows · CAPTCHA (also prohibited by policy — encountering one is a
classified stop, never evasion) · payments · destructive/irreversible actions ·
downloads · long autonomous multi-site browsing · exhaustive SPA coverage
(dynamic UI is supported to the degree the eval set demonstrates, no further
claim). Each non-goal gets ≥1 Level-5 case asserting graceful refusal.

## Assumptions

Public sites only (R7) · polite request rates · Chromium via Playwright ·
tasks solvable in ≤ ~30 actions · one task at a time per browser context ·
deployment reachable by reviewers for the whole grading window.

## Open questions

- Live-site drift cadence: how often to re-verify `full`-suite expectations
  (current answer: at each manual full run; API-snapshot ground truth limits
  exposure).
- ZH task parity depth: EN and ZH cases for every TC, or ZH sample per TC?
  (current answer: ZH sample per TC at B-floor.)

## Acceptance criteria for this definition

- Every TC has ≥2 base golden cases on at least one domain [MUST].
- Every non-goal has ≥1 L5 refusal case [MUST].
- The knowledge-placement grep (`grep -ri` for live-domain names + selector
  literals in `src/`) returns only allowed per-site data [MUST].
- Every case's `expect` names its ground-truth source (`provenance`) [MUST].
