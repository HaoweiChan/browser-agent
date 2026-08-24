# ADR-025: The T-M40-5 post-fix probe is pre-registered before it runs

Date: 2026-08-24
Status: accepted

**Ruling**: before any run of the T-M40-5 probe executes, this ADR freezes the six-task set (the four regressed task groups — x-rates.com, multpl.com, quotes.toscrape.com's author page, openlibrary.org — plus two controls, companiesmarketcap.com and bankofcanada.ca), the exact task text and start URL for each, the protocol (3 runs per task via `POST /tasks` on the deployed URL with no `model` override, every run's `run_id`/answer/terminal status/cost/wall time published regardless of outcome, ground truth independently re-verified by `curl` of the live page at probe time), and the pass/fail thresholds in §Thresholds below — so that the probe T-M40-5 requires cannot be graded against criteria chosen after its results are known.
**Because**: T-M40-2/ADR-024 shipped only the offline plan-lint refusal and deliberately deferred live confirmation to T-M40-5, because attributing a recovered row to the fix requires measuring a real deployed build post-merge, not the PR's own branch; D28's own history is the argument for freezing the criteria first — two of its three first-declared rows were withdrawn once already because the deployed build moved between probe and merge with no gate catching it (ADR-022 Decision 1a), and this repo's rule for a live-declared claim is that it is an engineering-judgment act with the evidence attached, not a threshold discovered after the fact.
**Enforced by**: no code — this is a protocol document, not a runtime change. Enforcement is procedural: the push timestamp below is the pre-registration evidence, and T-M40-5's own acceptance clause is the tracking hook that closes it.

---

## Context

PR #46 (T-M40-2, merge commit `3930934`) added the plan-lint clause ADR-024 rules on: a plan that `extract`s from the accessibility document root (`WebArea`/`RootWebArea`) is refused before execution. That clause is the fix candidate for the dominant failure shape D28 measured post-M32 — four of five previously-answering live task groups regressed to it. T-M40-2's own acceptance text ends "then the D28 rows re-declared from a post-fix probe of the same tasks", and splits that clause out as T-M40-5 because a post-fix probe reads the *deployed* build, which does not exist until after merge (`tasks/TODO.md:448-462`).

This ADR is that probe's pre-registration, written and pushed before any T-M40-5 run against the post-#46 deployment.

**ADR-number collision check.** Highest ADR on `origin/main` is `ADR-024-document-root-is-not-an-answer.md`; number 023 does not exist on `main` (reserved and unmerged on two branches — see below). `gh pr list --state open --json headRefName` (checked 2026-08-24, before this branch existed) returned four open PRs: `chore/todo-t-m40-2-done` (#50, no new decision file — matches `main` at 024), `task/M39` (#44, adds a decision file numbered 023, slug `m39-judge-retries-an-unreadable-completion`), `task/M38` (#42, adds a decision file *also* numbered 023, slug `m38-resolver-narrowing` — the two collide with each other at 023, not with this one), `task/T-M32-9` (#40, no new decision file). None of the four adds number 025. This ADR takes 025, the number after `main`'s current maximum.

## Frozen task table

Every row below is frozen as written. Where the exact phrasing used in a prior probe run is not recorded verbatim anywhere in this repo, a phrasing is fixed here and marked so — the prior row's pass/fail count still stands as evidence of the *shape* that failed, but was produced by an unrecorded prompt, not the one below.

| # | Group | Task (verbatim, frozen here) | Start URL | Ground truth | Prior post-M32 result (run_ids) |
|---|---|---|---|---|---|
| 1 | Regressed | `What is the current exchange rate from EUR to USD?` — **phrasing frozen here; the prior probe's phrasing is unrecorded.** (The prior recorded answer, `1.168361 USD`, carries USD as the *output* unit, which pins the direction as EUR→USD, not the USD→EUR direction named informally when this probe was requested; frozen to match the recorded evidence rather than the informal name.) | `https://www.x-rates.com/calculator/?from=EUR&to=USD&amount=1` | To be re-verified by `curl` at probe time. Prior value: `1.168361 USD` (pre-M32, 3/3: `570f4c04`, `0909909e`, `d9ad84b7`). | 0/3 — `b8b95067`, `133264ee`, `81155e22` (WebArea/document-root shape, D28) |
| 2 | Regressed | `What is the current S&P 500 P/E ratio?` — **phrasing frozen here; the prior probe's phrasing and page are unrecorded** (only that multpl.com split 3/6 pre-M32 across two adjacent pages, one via a "Table" link). | `https://www.multpl.com/s-p-500-pe-ratio` | To be re-verified by `curl` at probe time. No prior extracted value is recorded — pre-M32 only pass/fail is known (3/6: `97912676`, `434335eb`, `3ec2b4d5` pass; `a9d565b2`, `602d70be` fail on the adjacent page). | 0/2 — `bdc38f65` (container dump via a Table link), `c7fa2623` (three `observe` steps then a click, no extraction) |
| 3 | Regressed | `When was this author born?` — **recorded** (`docs/support-matrix.md`: "the domain's static author pages... 'When was this author born?' on /author/Albert-Einstein/"). | `https://quotes.toscrape.com/author/Albert-Einstein/` | To be re-verified by `curl` at probe time. Prior value: `Born: March 14, 1879 in Ulm, Germany` (pre-M32, 3/3: `b973e350`, `93085a40`, `14833919`). | 0/1 — `6811f8bf` (extracted "Quotes to Scrape", the site title; M36 judge rejected it) |
| 4 | Regressed | `Who is the author of this book?` — **recorded** in `src/browser/server.py`'s `EXAMPLES` and `prompts/016`; this is the only openlibrary.org task text present anywhere in this repo, so it is frozen here as the probe task. Not independently confirmed that run `a6797fbe` used this exact string — flagged, not silently assumed. | `https://openlibrary.org/books/OL7025919M` | To be re-verified by `curl` at probe time. No successful extraction is on record on this page: pre-M32 `ca0be024`, `015b6778`, `65af344f` all failed loudly; post-M32 `a6797fbe` hit the WebArea shape. | 0/1 — `a6797fbe` (WebArea/document-root shape, D28) |
| 5 | Control | `What is the market cap of this company?` — **recorded** in `src/browser/server.py`'s `EXAMPLES`. | `https://companiesmarketcap.com/apple/marketcap/` | Market cap is a live, continuously-changing figure — there is no fixed ground truth to freeze. To be re-verified by `curl` at probe time only. Prior value for context (not a target): `Market cap: $4.514 Trillion USD` (one of the 8/8 post-M32 runs). | 8/8 — `d0b63c7e`, `f2c8c624`, `65bb1028`, `03eedb79`, `2a058974`, `4cec8304`, `215e511a`, `f8925a42` (across six pages) |
| 6 | Control | `What is the current policy interest rate?` — **recorded** in `src/browser/server.py`'s `EXAMPLES`. | `https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/` | To be re-verified by `curl` at probe time. Prior value: `2.25` (post-M32, 3/3). | 3/3 — `e36edcc1`, `93fc8e6f`, `5125b503` → `"2.25"` |

**Correction to a figure quoted when this probe was commissioned.** The regressed set was described as "0/6 post-M32" in the request that produced this ADR. Recounting against the run ids actually cited in `docs/support-matrix.md` D28 and `tasks/TODO.md`'s T-M40-2 block gives **0/7**: x-rates.com 0/3 + multpl.com 0/2 + quotes-author 0/1 + openlibrary.org 0/1 = 0/7, not 0/6. This does not change the ≥50% threshold in §Thresholds below (frozen verbatim regardless), and is recorded here rather than silently fixed, on the same precedent D28 itself sets twice over (its first published run/domain counts were also wrong and both were caught by recount, `prompts/016`).

## Validity precondition

This probe counts **only** if run against the deployed build at merge commit `3930934` or a later commit on `main` that still contains ADR-024's refusal, **and only after** the `deploy-smoke` workflow run for that exact sha has succeeded. `deploy-smoke` triggers on `push` to `main` and on `workflow_dispatch`; it has no `/version` endpoint to compare against `GITHUB_SHA` (a known, already-declared ceiling — T-M40-4, `.github/workflows/deploy-smoke.yml`'s own header comment), so "the sha it verified" is read off the workflow run that followed this merge on the timeline, not confirmed by the deployment itself. If a later commit reaches `main` before the probe runs, the probe is run against *that* build and this ADR's validity precondition follows it forward — the frozen task table and thresholds do not change, only which build satisfies "post-fix."

## Protocol

1. Each of the 6 tasks in §Frozen task table is run **3 times** against `https://whaleforce-browser-agent.zeabur.app` via `POST /tasks`, with `url` set to the task's start URL and **no `model` field** (default model only) — 18 runs total.
2. For every run, record: `run_id`, the final `answer`, the terminal `status` (`success` / `failure:*`), cost, and wall-clock time, read from `GET /tasks/{run_id}`.
3. Ground truth for each task is independently re-verified by `curl`ing the real start URL at probe time — not taken from the "prior value" column above, which is context only and may be stale (exchange rates, P/E ratios and market caps move continuously; even the central-bank rates can change between declarations).
4. Every run_id is published in the results write-up (§Commitment), regardless of whether that run passed, failed loudly, or produced a wrong answer. No run is dropped from the record.

## Metrics — reported separately, never blended

- **Correct answer** — terminal `status: success`, judge-certified, and the answer matches the re-verified ground truth.
- **Loud failure** — any `failure:*` terminal status.
- **Wrong success** — terminal `status: success` (judge-certified) with an answer that does **not** match the re-verified ground truth. This is the shape D23/D28 both warn is invisible to every check except a human comparing the answer to the page.
- **Refusal** — the gateway rejects the task before a run starts (e.g. a blocked URL or model), or the run reports a defined refusal state distinct from the three above.

These four counts are reported as four separate numbers per task and per group. They are never combined into one pass rate.

## Pre-registered thresholds (fixed, verbatim)

(a) **HARD**: zero wrong-success across all runs. Any wrong-success = probe verdict FAIL regardless of other numbers.
(b) Regressed set (x-rates, multpl, quotes-author, openlibrary): correct-answer rate ≥ 50% of runs (was 0/6 post-M32). Below that = fix insufficient, verdict stated as such.
(c) Controls: correct-answer rate no worse than prior post-M32 rate (companiesmarketcap 8/8, bankofcanada 3/3) allowing at most one miss per control.
(d) Refusals are counted separately and never counted toward (b) or (c).

## Commitment

Whatever the outcome — verdict PASS, FAIL on (a), or "fix insufficient" on (b) — results land in `docs/analysis.md` as a new **§8a-4**, and the D28 rows in `docs/support-matrix.md` are re-declared from them, including declaring a row `unsupported` where the probe says so (T-M40-5's own acceptance text already commits to this). Every run_id from every one of the 18 runs is published in that write-up, not just the ones that support the eventual verdict.

## Consequences

- T-M40-5 cannot be closed by a probe run against any build before `3930934`, or by a probe that changes the task list, the thresholds, or "correct answer" after seeing which runs failed.
- The regressed-set threshold is deliberately looser than "recovers to the pre-M32 rate" — ≥50%, not the 100%/83% the pre-M32 runs actually hit — because T-M40-2's fix is explicitly a partial lever (T-M40-2-1/T-M40-2-2 name the two levers *not* shipped in PR #46, deferred for exactly this probe to attribute recovery correctly). A pass here does not mean the WebArea shape is fully closed; it means the offline refusal alone measurably helps.
- If the probe finds new failure shapes on the regressed set (as ADR-024's own §2 already anticipates for the mid-run replan path, T-M40-2-4), those are new adversarial cases per CLAUDE.md rule 2, not adjustments to this ADR's frozen task list.
