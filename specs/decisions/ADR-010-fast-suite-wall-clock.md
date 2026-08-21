# ADR-010: the `fast` gate's wall clock — one browser for the suite, and a guard that reads it

Date: 2026-08-21
Status: accepted

**Ruling**: ADR-002 Decision 4's 60s ceiling stands unchanged and is now *enforced* by an eval case; the `fast` suite gets one shared Chromium (each case still runs in its own BrowserContext) and measures 54.1-55.9s over 89 cases.
**Because**: 11.3s of the 67.0s breach was per-case browser process lifecycle — scaffolding, not evidence — and a budget nothing reads drifts from 13s to 68s without one run turning red.
**Enforced by**: `fast-wall-clock-budget` (the ceiling), `agent-launches-its-own-browser` (the production launch path the sharing would otherwise leave ungraded).

**Amends**: ADR-002 Decision 4 (breach closed, ceiling unmoved, enforcement added); ADR-009 Decision 6 and `docs/support-matrix.md` D8 (the declared breach they carry is resolved)

---

## Context

ADR-009 Decision 6 declared the `fast` gate over budget — 66.6-68.3s against
ADR-002 Decision 4's 60s — and named the parallel eval runner as the fix. It
also stated, correctly, that 10.6s of it is `l4-shop-overlay-modal` spending a
full Playwright click timeout, that this is the honest price of discovering
non-actionability, and that lowering the production click timeout to make an
eval cheap is the `MIN_EVIDENCE` anti-pattern (ADR-008 Decision 3).

What nobody had measured was the other 57s. This ADR measured it before
choosing anything.

## Measurement

Instrumented run of the pre-fix `fast` suite (87 cases, 67.0s total; the
per-call timings come from wrapping `async_playwright`, `Page.goto`,
`Page.screenshot`, `Page.wait_for_timeout`, `Page.wait_for_load_state`,
`Locator.click` and `Locator.fill`, so every number below is a sum of real
calls, not an estimate):

| Where the wall clock goes | Seconds | Calls | Reducible? |
|---|---:|---:|---|
| Playwright driver start | 6.4 | 58 | **yes** — one node driver per case |
| `chromium.launch` | 4.1 | 58 | **yes** — one Chromium per case |
| `browser.close` | 0.8 | 58 | **yes** |
| settle loop (`wait_for_timeout`, 200ms × `SETTLE_TRIES`) | 16.2 | 80 | no — the postcondition budget being spent |
| bounded `load` wait | 8.2 | 56 | no — 4 calls at the 2s bound (`slow-asset.html`), the other 52 cost 0.19s in total |
| `Locator.click` | 10.9 | 35 | no — one call at the 10s bound (`l4-shop-overlay-modal`), median 0.031s |
| `page.screenshot` | 13.8 | 117 | no — 4 calls at the 2s font bound (ADR-007), median 0.050s |
| `goto` + `fill` | 0.4 | 77 | no |
| everything else (observe, resolve, verify, JSON, temp dirs) | ~6.2 | — | no |

Read as three numbers: **42.2s is deliberate waiting at a bound the suite
exists to exercise**, **13.5s is real work**, and **11.3s (17%) is per-case
browser process lifecycle** — the same cost the M2 baseline table already
recorded in passing ("browser cases run 0.29-0.62s with a cold Chromium launch
each") when it was 30 cases and did not matter.

## Decision

**Route: remove the waste, keep the ceiling.** Moving a threshold while 17% of
the number is measured scaffolding is the goalpost-moving ADR-002 exists to
prevent. Nothing about the deliberate 42.2s was touched — no production
timeout, no case deleted, no case moved out of `fast`.

1. **One Chromium for the whole suite.** `run_task` takes an optional
   `browser`; production (gateway, CLI) leaves it `None` and gets a private
   browser per run, because two callers' tasks must not share a process. The
   harness (`src/browser/eval_adapter.py`) starts one driver and one browser on
   one event loop — a Playwright browser belongs to the loop that created it,
   so a shared browser needs a shared loop — and every case borrows it.
   Isolation is unchanged: `run_task` now opens its own `BrowserContext` per
   run on either path, so cookies and storage never cross between runs.

   This is not the `MIN_EVIDENCE` shape. That was a *production constant* bent
   so an eval would pass; this is an argument that production declines, whose
   default is exactly today's behaviour, and which changes what the harness
   spends rather than what the agent does. The evidence that no behaviour moved
   is that every derived figure reproduced across the change: 170 actions,
   recovery 7/7, mutation 9/11 with 6 recovered / 5 by relocating, diagnosis
   14/14, 4 replans, `fast` 1.000, `live` 9/9 against real sites.

2. **The ceiling is enforced, not asserted.** `fast-wall-clock-budget` reads
   the newest committed `evals/report/*-fast.json` and fails when
   `totals.wall_seconds` exceeds 60. A suite cannot measure itself from inside,
   so it grades the previous run — one run of lag, against the six milestones
   of lag the prose ceiling actually had. Deliberately not tagged `invariant`:
   invariants are absolute and machine-independent, and a wall clock is neither
   (ADR-009 Decision 6 records 66.6-68.3s here and 68.6s on a reviewer's
   machine).

3. **The un-shared launch keeps a case.** Sharing the browser on every case
   left `browser is None` — the branch every real caller takes — graded by
   nothing: it could be deleted and the suite stayed 1.000. That was watched,
   then closed by `agent-launches-its-own-browser`, one ~0.3s run that refuses
   the shared browser.

## Consequences

`fast` measures **54.1-55.9s over 4 runs, 89 cases** (up from 67.0-68.3s over
86-87), and the suite got two cases larger while getting 13s faster. Headroom
against the 60s ceiling is ~4-6s on this machine, which is real but not
generous: the 42.2s of deliberate waiting is the floor this route cannot touch,
and the growth trend ADR-009 Decision 6 described (13s → 48.6s → 55.4s → 67s)
has not been repealed, only set back. The next milestone that adds a handful of
browser cases will turn `fast-wall-clock-budget` red, and that is the point —
the choice at that moment (parallel runner, or a ceiling amended from a fresh
measurement) becomes a decision someone makes, instead of a drift nobody sees.

The parallel eval runner stays in the backlog on its own merits. It was named
in ADR-009 Decision 6 as *the* fix; it is now the *next* fix, and it addresses
the 42.2s this one deliberately left alone.
