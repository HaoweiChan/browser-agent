# ADR-011: the `fast` gate's wall clock — one browser for the suite, and a ceiling that gates the run

Date: 2026-08-21 (Decisions 1 and 2 amended the same day, PR #20 round 1)
Status: accepted

**Ruling**: ADR-002 Decision 4's 60s ceiling stands unchanged, and `evals/run.py` now applies it to the run it just measured and exits non-zero; the `fast` suite gets one shared Chromium, re-launched if it dies, with each run in its own BrowserContext, and measures 56.6s over 95 cases after the M9 merge.
**Because**: 11.3s of the 67.0s breach was per-case browser process lifecycle — scaffolding, not evidence — and a budget nothing reads drifts from 13s to 68s without one run turning red.
**Enforced by**: `evals/run.py` `over_budget()` (the ceiling itself), `fast-wall-clock-budget` (the ruling it applies), `agent-launches-its-own-browser` and `shared-browser-relaunches-when-dead` (what sharing a browser would otherwise leave ungraded).

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
   **State** isolation is unchanged: `run_task` opens its own `BrowserContext`
   per run on either path, so cookies and storage never cross between runs.
   **Process** isolation is not, and that was missed until review (PR #20 R2):
   per-case launches contained a browser crash to the case that caused it, and
   `_browser()` returning a dead-but-not-`None` Chromium turned one death into
   twelve later cases failing with `TargetClosedError` attributed to themselves
   (measured: 77/90). `_browser()` now re-launches when `is_connected()` is
   false, pinned by `shared-browser-relaunches-when-dead`. What is still shared
   is a *wedged* browser — alive to `is_connected()`, unresponsive in fact —
   which only the per-action Playwright timeouts bound.

   This is not the `MIN_EVIDENCE` shape. That was a *production constant* bent
   so an eval would pass; this is an argument that production declines, whose
   default is exactly today's behaviour, and which changes what the harness
   spends rather than what the agent does. The evidence that no behaviour moved
   is that every derived figure reproduced across the change: 170 actions,
   recovery 7/7, mutation 9/11 with 6 recovered / 5 by relocating, diagnosis
   14/14, 4 replans, `fast` 1.000, `live` 9/9 against real sites.

2. **The ceiling gates the run that measures it.** `evals/run.py` holds the
   ruling (`WALL_BUDGET_S = {"fast": 60}` and the pure `over_budget()`), applies
   it to `totals["wall_seconds"]` of the run it has just finished, and exits
   non-zero with a named line — the same shape as the invariant-100% rule beside
   it. `fast-wall-clock-budget` grades both halves: the ruling (the boundary at
   60.00/60.01, and `fast` as the only key in `WALL_BUDGET_S`, compared as a set
   so a new suite name cannot be added past it) and the call site, by driving
   `evals.run.main()` over a stub result of a chosen duration and checking the
   exit code. The second half was added in review round 2 (PR #20 R8): the first
   version pinned the rule only, so deleting the five lines in `main()` that
   apply it left a 79.02s run — 32% over — reporting 90/90 = 1.000 at exit 0.
   The hole moved up a level each time it was closed, which is why the case now
   grades where the decision is applied and not only the decision. Precisely:
   it grades what `main()` RETURNS, in-process. The module tail that turns that
   into a process exit code — `if __name__ == "__main__": sys.exit(main())` — is
   the one line CI and the pre-commit hook actually read, and it is ungraded:
   changing it to a bare `main()` disables this ceiling, and the invariant and
   regression rules with it, with the case still green (PR #20 R13, Debt T-R13).

   The first version of this decision had the case read the newest report in
   `evals/report/` instead, and review falsified it (PR #20 R1). A report is
   written *after* the run and does not survive a CI workspace, so on the fresh
   clone `.github/workflows/eval.yml` builds, the newest file is always the one
   the branch committed: a tree measuring 77.23s — 28% over — still scored 89/89
   = 1.000 and the gate stayed green. "Enforced, not asserted" was itself an
   assertion. Re-run against the repaired tree, the same 0.25s-per-case
   slowdown now prints `OVER BUDGET: suite 'fast' wall clock 78.42s > 60s` and
   exits 1, on a `--no-report` run with no report file involved at all.

   Deliberately not tagged `invariant`: invariants are absolute and
   machine-independent, and a wall clock is neither (ADR-009 Decision 6 records
   66.6-68.3s here and 68.6s on a reviewer's machine). Three things this ADR
   does not settle, all open on purpose: what a contributor on slower hardware
   should do when the ceiling is genuinely out of reach there (PR #20 R6, Debt
   T-R6); what `--update-baseline` should do on an over-budget tree, since it
   returns before the ceiling is consulted and reports nothing (PR #20 R12, Debt
   T-R12); and the ungraded module tail above (PR #20 R13, Debt T-R13), which is
   not this ceiling's problem alone — it gates every rule in `main()` the same
   way.

3. **The un-shared launch keeps a case.** Sharing the browser on every case
   left `browser is None` — the branch every real caller takes — graded by
   nothing: it could be deleted and the suite stayed 1.000. That was watched,
   then closed by `agent-launches-its-own-browser`, one ~0.3s run that refuses
   the shared browser.

## Consequences

`fast` measures **56.61s over 95 cases** (`evals/report/20260821-143744-fast.json`),
against 67.0-68.3s over 86-87 before this ADR and 71.3-76.5s once M9's cases
arrived. Headroom against the 60s ceiling is ~3.4s on this machine, which is real
but not generous: the 42.2s of deliberate waiting is the floor this route cannot
touch, and the growth trend ADR-009 Decision 6 described (13s → 48.6s → 55.4s →
67s) has not been repealed, only set back. The next milestone that adds a handful
of browser cases will turn the ceiling red, and that is the point — the choice at
that moment (parallel runner, or a ceiling amended from a fresh measurement)
becomes a decision someone makes, instead of a drift nobody sees.

**The prediction above came true on the next merge, one day later, and the record
of what happened is worth more than the prediction.** Merging M9 took the suite to
63.3s and the gate exited 1 with `OVER BUDGET: suite 'fast' wall clock 63.3s >
60s` — a legitimate merge, 95/95 passing, stopped on wall clock alone. What it
caught was not the browser work anyone would have suspected: of M9's five new
cases, four cost 0.03s between them and one cost 8.08s, of which **8.03s was four
`time.sleep(2)` calls** in the ablation driver's completion poll
(`evals/ablation.py`), waiting on loopback runs that had each finished in under a
second. The same shape as this ADR's own 11.3s of per-case Chromium launches:
time in which nothing is being measured. The poll was given a backoff (0.1s
doubling to a 2s cap, bounded by the existing deadline, which leaves a real paid
sweep unchanged), the case fell from 8.08s to 1.67s, and the ceiling held without
being moved. Recorded because the ceiling's value is not that it was set
correctly — it is that it fired on something nobody would have gone looking for.

The parallel eval runner stays in the backlog on its own merits. It was named
in ADR-009 Decision 6 as *the* fix; it is now the *next* fix, and it addresses
the 42.2s this one deliberately left alone.
