# ADR-013: the `fast` gate's wall clock — one browser for the suite, and a ceiling that gates the run

Date: 2026-08-21 (Decisions 1 and 2 amended the same day, PR #20 round 1;
Decision 3 added on first contact with CI; Decision 4 amended the local
ceiling to 70 on the M9-stage-2 merge, then amended it back to 60 the same
day, on PR #20 round 5 review, when the band that justified 70 did not
reproduce — all the same day)
Status: accepted

**Ruling**: ADR-002 Decision 4's `fast` wall-clock ceiling is per-environment and each number is measured as the slowest observed run +15% (CI) or as the slowest *reproducible* run (local, since round 5 — see Decision 4) — 60s locally, 80s on CI via `EVAL_WALL_BUDGET_S` — applied by `evals/run.py` to the run it just measured, exiting non-zero; the suite gets one shared Chromium, re-launched if it dies, with each run in its own BrowserContext.
**Because**: 11.3s of the 67.0s breach was per-case browser process lifecycle — scaffolding, not evidence — and a budget nothing reads drifts from 13s to 68s without one run turning red.
**Enforced by**: `evals/run.py` `over_budget()` (the ceiling itself), `fast-wall-clock-budget` (the ruling it applies), `agent-launches-its-own-browser` and `shared-browser-relaunches-when-dead` (what sharing a browser would otherwise leave ungraded).

**Amends**: ADR-002 Decision 4 (breach closed, ceiling per-environment, enforcement added, local number unchanged at 60 — Decision 4 below tried 70 and withdrew it the same day); ADR-009 Decision 6 and `docs/support-matrix.md` D8 (the declared breach they carry is resolved)

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
timeout, no case deleted, no case moved out of `fast`. "Keep the ceiling" is
the route, not a promise the digits never change again: the local number
stayed 60 through Decisions 1-3; Decision 4 below re-measured it to 70 after a
later merge made the suite straddle it, and that re-measurement was itself
withdrawn later the same day, on round-5 review, when the band it rested on
turned out not to reproduce. The number that ships is 60 — unchanged from
Decision 1 — but arrived at only after two measurements and one retraction,
not asserted blind either time.

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
   ruling (`WALL_BUDGET_S = {"fast": 60}` at the time this decision was
   written, and still the number shipping today: Decision 4 below re-measured
   it to 70 after a later merge crossed the line, then withdrew that
   amendment on round-5 review when the band behind it did not reproduce) and
   the pure `over_budget()`, applies
   it to `totals["wall_seconds"]` of the run it has just finished, and exits
   non-zero with a named line — the same shape as the invariant-100% rule beside
   it. `fast-wall-clock-budget` grades both halves: the ruling (the boundary,
   60.00/60.01 today, and `fast` as the only key in `WALL_BUDGET_S`, compared as a set
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
   66.6-68.3s here and 68.6s on a reviewer's machine). Decision 3 below is the
   machine-dependence answered rather than declared. Two things this ADR still
   does not settle, both open on purpose: what `--update-baseline` should do on
   an over-budget tree, since it returns before the ceiling is consulted and
   reports nothing (PR #20 R12, Debt T-R12); and the ungraded module tail above
   (PR #20 R13, Debt T-R13), which is not this ceiling's problem alone — it
   gates every rule in `main()` the same way.

3. **The ceiling is per-environment, and both numbers are measured.**
   `WALL_BUDGET_S = {"fast": 60}` is the local ruling at the time this
   decision was written — Decision 4 below re-measures it to 70, then withdraws
   that on round-5 review, so 60 is also the number enforced today. `EVAL_WALL_BUDGET_S`
   overrides it, `.github/workflows/eval.yml` sets it to **80**, and anything
   that is not a positive number — unset, empty, `banana`, `60s`, `0`, `-5` —
   falls back to the committed local number (60 today). `fast-wall-clock-budget` grades all of that,
   including the value the workflow declares, because an override nothing reads
   is the R8 defect again and an override that silently disables the ceiling is
   the R1 defect again.

   **Why two numbers.** CI ran on this branch for the first time on 2026-08-21
   (the PR had been CONFLICTING, and GitHub silently runs nothing on those) and
   came back red at 64.61s. The useful part is the run beside it: `main`'s own CI
   run `32385032004` does `fast` in **89.62s over 92 cases** — CI had been ~50%
   over the 60s ceiling for its entire existence, invisibly, because nothing
   checked. This branch did not make CI slow; it made CI measurable, and cut
   89.62s to 59.8-64.7s while adding three cases. That is finding D6/R6 arriving
   with a trigger hours after being filed as debt without one.

   **The CI number, and what it rests on.** First measured at 95 cases (commit
   `09b9740`, run `32455716866` and three re-runs): **59.77 / 60.84 / 64.61 /
   64.67s**, a 4.90s spread — 8% of the fastest — on byte-identical code. Then
   re-measured after the M9-stage-2 merge, because 75 had been derived from code
   that no longer existed: four runs at 97 cases (`7a2869a`, runs `32465066308`
   and `32465584897` with two re-runs) gave **64.29 / 67.51 / 68.94 / 68.96s**, a
   4.67s spread — 7% — reproducing the same variance on a suite ~3.5s heavier.

   **The rule, applied to both environments: the slowest observed run plus 15%,
   rounded up to a multiple of five.** 68.96 × 1.15 = 79.3 → **80s** on CI;
   60.16 × 1.15 = 69.2 → **70s** locally (Decision 4). Unlike the first
   measurement, this band does **not** straddle its ceiling — 68.96s against 80s
   — where the first CI band straddled the old 60s on three of its four runs
   (59.77/60.84/64.61/64.67). What each number rests on is a band, not a
   distribution, and the CI band is not even one commit's worth: run
   `32465066308` (attempt 1) is `94f1a42`, `32465584897`'s three re-run
   attempts are all `7a2869a` — one run at the pre-merge sha plus three at the
   post-merge one, not four runs of one commit (PR #20 R22). Nothing about any
   runner class other than `ubuntu-latest` either way. ADR-009 Decision 6
   published a single-run number and had to be corrected to a band, which is why
   the count is stated rather than implied.

   **What was rejected, so the alternatives are visible.** One ceiling raised
   until CI fits would put ~18s of drift room in front of the local gate, which
   is the only place the number is currently tight — the exact drift this ADR
   exists to stop. Making the check advisory in CI would retire it precisely
   where the hardware is slowest and the drift shows first. `--no-verify` and
   moving cases out of `fast` are not on the table at all: both are ways of not
   measuring. A threshold that varies by environment is a decision, and this
   repo records decisions rather than quietly widening one.

4. **The local number is re-measured to 70s when the M9-stage-2 merge crosses
   60, then the re-measurement is withdrawn on round-5 review and it ships at
   60s.**
   Merging `origin/main` at `80870f0` (PR #19 readiness + PR #22 report policy)
   brought `readyz-tracks-the-run-slot` into `fast`, and the suite measured
   **59.35 / 59.39 / 59.80 / 59.83 / 59.88 / 60.11 / 60.16s over seven runs** —
   *straddling* the 60s line, four under and three over. A ceiling the suite
   crosses on half its runs is a coin flip, not a gate, and saying so plainly
   matters more than which side the median lands on.

   **The excess is evidence, not waste, and that was measured before it was
   claimed.** Per-call over the merged suite: settle 16.23s (80 × 200ms),
   screenshot 14.11s (122 calls, four at the 2s font bound), click 11.07s (35
   calls, one at the 10s overlay bound), bounded `load` 8.20s (63 calls, four at
   the bound), `time.sleep` 5.08s, browser lifecycle 1.39s, goto+fill 0.35s. Every
   `time.sleep` was attributed to its call site: 3.46s is
   `readyz-tracks-the-run-slot` — 1.0s sampling `/readyz` *while* the slot is
   held, then 2.45s polling a 3.0s hold at 0.2s granularity — and 1.63s is the
   ablation driver's backoff. The ablation poll is proportionate (0.1s-first
   backoff on ~0.35s runs, same shape this ADR already fixed once). The
   `readyz` hold was not: **review found a third reducible shape here (PR #20
   R14)**, and "the sweep above found no third" below was false when it was
   written. The graded contract is idle→busy→idle, the *transition*, not how
   long busy lasts — a hold long enough that `/readyz` reliably samples inside
   it is coverage; extra seconds past that are the same per-case waste this
   ADR removed twice already, just measured in a fixture constant instead of a
   browser launch. It does not follow that any hold works: the sample is taken
   `min(1.0, hold/3)` seconds after submission, and that gap has to clear the
   real *start-race* — the time between the submission returning and the
   stubbed planner actually acquiring the run slot, which 15 in-process trials
   measured at 4.3-5.2ms typically with one 62ms outlier (cold interpreter
   state, not a per-run cost once the suite has warmed up). `hold=1.0s` (the
   value review measured passing) gives a 0.33s sample gap — already 5x the
   worst outlier seen — but the margin was picked to clear a start-race, not
   to hit a duration, so it is derived independently rather than copied:
   `hold=2.0s` gives a 0.67s gap, ~10x the worst outlier, without re-adding
   the browser-lifecycle-shaped waste a 3x-larger hold would. Recovered:
   ~1.0s per suite run (case cost 3.55s → 2.51s, five in-process trials at
   `hold=2.0` all landing `during_latency_s` under 0.01s).

   Re-measured after the fix, seven runs: **58.69 / 58.79 / 59.05 / 59.27 /
   59.96 / 60.44 / 60.59s**, published here as still straddling 60s (two of
   seven over), and treated as ruling out branch 1 (`fast < 60s again`): the
   honest band's ceiling, by the same rule as Decision 3 — the *slowest
   observed run* plus 15%, rounded up to a multiple of five — was
   60.59 × 1.15 = 69.7 → **70s**. `WALL_BUDGET_S` moved to 70 on that basis.

   **It does not reproduce, and round-5 review (PR #20 R24) caught it.**
   Neither of the two runs over 60s — 60.44, 60.59 — showed up again anywhere
   else this band was checked. The reviewer measured 8 runs on the shipping
   tree: 59.00-59.87s. The orchestrator independently measured 6 runs at a
   load average of 3.19: 58.97-59.22s, plus its own committed gate run at
   59.15s. Asked to substantiate the two outliers as loaded-machine runs
   before dropping them — the most likely honest explanation, since this
   machine was doing other work at the time — the round-5 repair ran 7 more:
   6 at load average 2.3-4.9 (58.97-59.41s), and one built specifically to
   test the load hypothesis — 8 processes pinned at 100% CPU each, load
   average driven to 8.4 on a 14-core machine, concurrent with the suite —
   which measured **58.96s**, the low end of the range, not the high end.
   Heavy CPU contention did not slow the suite down, because the suite's wall
   clock is dominated by fixed sleeps and Playwright timeout bounds (§
   Measurement above), not CPU cycles — there are cores to spare underneath
   those waits, so "the machine was busy" does not explain a slowdown here
   the way it might for a CPU-bound job. The load hypothesis was tested, not
   assumed, and it failed.

   Across three independent measurers — reviewer, orchestrator, and this
   repair, idle runs and one deliberately loaded run alike — roughly 22 runs
   land at **58.96-59.87s**. The two outliers this Decision originally
   published are not in that range and nobody, including a dedicated attempt
   under load, has reproduced them. They are dropped as unsubstantiated
   rather than kept, averaged away, or rationalized.

   That reopens the acceptance criterion's **first branch**
   (`fast < 60s again`), not the second: **`WALL_BUDGET_S` reverts to 60**,
   unchanged from Decision 1. The cost of taking it is stated plainly rather
   than buried — headroom against the max reproducible run (59.87s) is
   **~0.13s**, nothing like the ~10s of margin the pre-breach suite had. A
   suite this close to its own ceiling will very likely turn red on the next
   case `fast` gains, cheap or not; that is the coin-flip-gate problem this
   Decision already named once, arrived at again from the opposite direction.
   The alternative — keeping 70 on the argument that the suite "clears 60
   idle, exceeds it under load" — was considered and rejected here on the
   evidence actually measured: the loaded run did not exceed 60, or come
   close to it, so there is no reproducible loaded condition to build that
   argument on. If one is found later, that is a fresh amendment with its own
   runs behind it, not a reason to keep 70 on this record.

   ADR-002 Decision 4's local number, amended from 60 to 70 earlier the same
   day, is amended back to 60 here. What is *not* claimed: that 60s is
   generous. It is the slowest reproducible run plus 0.13s, and the parallel
   eval runner (M14) remains the only lever that would put real headroom back.

5. **The un-shared launch keeps a case.** Sharing the browser on every case
   left `browser is None` — the branch every real caller takes — graded by
   nothing: it could be deleted and the suite stayed 1.000. That was watched,
   then closed by `agent-launches-its-own-browser`, one ~0.3s run that refuses
   the shared browser.

## Consequences

`fast` measured **60.51s over 97 cases** (`evals/report/20260821-170854-fast.json`)
at the point this section was first written, against 67.0-68.3s over 86-87
before this ADR and 71.3-76.5s once M9's cases arrived — wall clock falling as
scaffolding left the suite, not growing with it. That snapshot predates both
the readyz-hold fix and the round-5 correction above; the reproducible band
today is **58.96-59.87s** (Decision 4). Headroom against the **60s** local
ceiling — reverted, not re-measured, in Decision 4's round-5 correction — is
the number to read now: **~0.13s** against the slowest reproducible run, a
fraction of the ~10s this section could once claim while 70s was the shipping
ceiling. The 42.2s of deliberate waiting is the floor this route cannot
touch, and the growth trend ADR-009 Decision 6 described (13s → 48.6s → 55.4s →
67s) has not been repealed, only set back further than a straddling ceiling
suggested. The next case added to `fast` — even a cheap one — is now likely to
turn the ceiling red, and that is sharper than it was: the choice at that
moment (parallel runner, or a ceiling amended from a fresh measurement)
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

**And then it fired again the same day, on the first CI run this branch ever
got.** Both firings found something real and neither was the thing predicted: the
first a completion poll, the second an environment where the ceiling had never
run at all. `T-R6` — "no sanctioned escape when the ceiling is unreachable",
filed as debt on the grounds that it had no demonstrated trigger — had one within
hours, and is closed here by the per-environment ceiling rather than left open.
The escape it asked for is now named and measured instead of improvised:
`EVAL_WALL_BUDGET_S`, set from observations, graded by a case. What it does not
answer is a contributor whose own machine cannot make 60s; that person now has a
documented mechanism, but pointing it at a number nobody measured would be the
drift this ADR is about, so the honest move there is still an amendment with its
own runs behind it.

The parallel eval runner stays in the backlog on its own merits. It was named
in ADR-009 Decision 6 as *the* fix; it is now the *next* fix, and it addresses
the 42.2s this one deliberately left alone.
