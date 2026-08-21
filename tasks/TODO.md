# Task 1 milestones — pr-loop queue

Working set only (groundwork GW-004): Queue + Debt here, merged work is a
one-liner in `tasks/DONE.md`. Block format and protocol: the groundwork
plugin's `pr-loop` skill; list unblocked tasks with
`python3 "$CLAUDE_PLUGIN_ROOT"/skills/pr-loop/scripts/ready.py` (repo root).
Milestone-level only (ADR-001) — micro-tasks stay in the session. Reviewer
evidence tags reference `docs/product/assignment-requirements.md` §E1–E5.
A-phase hour guard: +12h (Reopen note below). Dependency rule: a block with
no `Depends:` line is unblocked — any set of unblocked Queue tasks can run as
parallel pr-loop sessions on their own `task/<id>` worktree branches.

## Queue

### M10 — A-Freeze            [status: in-progress]
Depends: M9, M12
Spec: analysis/README/support-matrix refresh, prompts curated, second
held-out probe vs the deployed URL (mandatory gate, raw results committed).
Depends on M12 because the A-exit walk checks the gate against ADR-002, and
the declared D4 wall-clock breach must be fixed or amended before the walk
can be honestly green.
Acceptance: A-exit criteria in `docs/plans/active/task1-a-level-plan.md` all
green → owner decides submission/public.

## Debt

### M11 — Live-drift snapshot replay            [status: todo]
Origin: M8's SHOULD item, left open at the M8 merge (PR #12)
Spec: replay committed live-page snapshots so live-site drift is detected
without network. Acceptance: a drifted snapshot turns a case red offline.

### T-ADR-NUM — ADR numbers are allocated by "next free", and this branch has been renumbered three times            [status: todo]
Origin: PR #20 (no finding id — discovered by doing it, three times)
Spec: an ADR takes the next free number when it is *written*, and concurrent
branches all see the same next free number, so whichever merges last renumbers.
This branch's wall-clock ADR was written as ADR-010 and shipped as ADR-013:
010 -> 011 when M9's ablation ADR merged first, 011 -> 012 when the readiness
ADR (PR #19) merged, 012 -> 013 when the report-policy ADR (PR #22) merged —
three forced renames in one PR, each while the branch was otherwise finished.
Each rename rewrites the same string across ~12 files: the ADR itself, ADR-002
(status header, Amended-by, Ruling, Enforced-by, Decision 4), ADR-009's closure
note, `specs/decisions/INDEX.md`, `README.md`, `docs/analysis.md`,
`docs/support-matrix.md`, `tasks/TODO.md`, two eval case files, and comments in
`evals/run.py`, `src/browser/eval_adapter.py`, `src/browser/agent.py`.
The part that makes this worth a block rather than a shrug: **once several
renames have layered, a sweep is no longer verifiable by grep alone.** Every hit
for the old number looks plausible because the text around it was written by an
earlier sweep, and the tree now contains three live ADR numbers within two of
each other (011 readiness, 012 report policy, 013 wall clock) whose references
are told apart only by reading each line. Verifying the third sweep meant
classifying every `ADR-01[123]` hit by hand against which ADR it means. A
mechanical check would not have to.
Acceptance: a number-allocation rule plus a gate-time guard, not one or the
other — reserve-on-open (a branch claims its number when the PR opens) or
date-based ids remove the collision, and an `adr-header-and-index` extension
that refuses a duplicate number, a gap in the sequence, or an INDEX entry whose
number does not match its file makes a botched sweep red instead of plausible.
Do not design it in this PR.
Fourth instance, and the first outside ADR numbers: PR #23's tinboker ADR was
written as ADR-013 and shipped as ADR-014 (PR #20's wall-clock ADR took 013
first), and the *task id* collided the same way — PR #21 R1 logged a soak debt
as M18 while PR #23's branch, PR title and review artifacts were already M18,
so the debt block was renumbered to M27 on merge. "Next free" fails for every
id sequence in this repo, not just `specs/decisions/`; whatever rule lands here
should cover `tasks/TODO.md` ids too.

### T-R13 — the module tail that turns `main()`'s return into an exit code is ungraded            [status: todo]
Origin: PR #20 R13 (LOW, routed debt by the reviewer, which approved alongside it)
Not specific to M12's ceiling: the same tail gates the pre-existing invariant and
regression rules identically, and nothing in PR #20's diff made it worse. The
wording half of its acceptance was taken in PR #20; this is the mechanism half.
Spec (claim): the R8 repair grades `main()`'s return value but not the module
tail that turns it into a process exit code, so `evals/run.py:179` changing from
`sys.exit(main())` to `main()` silently disables the wall-clock gate (and the
invariant and regression gates with it) while `fast-wall-clock-budget` stays
green. Evidence: `evals/run.py:178-179` is the only thing CI and
`.githooks/pre-commit` (`python -m evals.run --suite fast`) actually read, and
`src/browser/eval_adapter.py` `_main_exit_code` calls `R.main()` in-process,
never the `__main__` guard. Measured in a scratch copy: with
`WALL_BUDGET_S = {"fast": 60, "invariant": 0}` and the tail unmodified,
`python -m evals.run --suite invariant --no-report` exits 1; with the tail
changed to a bare `main()` the same over-budget run exits 0, and
`run_case(fast-wall-clock-budget)` still returns
`{'passed': True, 'main_exit': [{54.35, exit 0, got 0}, {79.02, exit 1, got 1}]}`.
Repro: cp -a the worktree to a scratch dir; `sed -i '' 's/sys.exit(main())/main()/'
evals/run.py`; `python -m evals.run --suite fast --no-report; echo $?` on an
over-budget tree -> 0, and
`python -c "import json,src.browser.eval_adapter as A; print(A.run_case(json.load(open('evals/adversarial/fast-wall-clock-budget.json')))['passed'])"`
-> True. Acceptance: the case drives the process — one
`subprocess.run([sys.executable, '-m', 'evals.run', ...])` over-budget probe
reading `returncode` — rather than calling `main()` in-process.

### T-R12 — `--update-baseline` records a baseline over the wall-clock ceiling, silently            [status: todo]
Origin: PR #20 R12 (LOW, routed debt — what should happen there is a repo-owner call)
Spec: `evals/run.py:157-161` writes the baseline and `return 0` at line 161; the
`over_budget` check is at line 166. A `fast` run measuring 79.02s therefore exits
0 with only `[eval] baseline['fast'] = 1.000 (recorded)` on stdout and no
`OVER BUDGET` line anywhere, even though the same run without the flag exits 1.
So the one command CLAUDE.md sanctions for a deliberate baseline move records it
on a tree that is over the ceiling and says nothing. ADR-013 Decision 2 describes
the ceiling as "the same shape as the invariant-100% rule beside it" — which sits
at line 162 and is bypassed by the same early return, so the shape does match, but
the resulting silence is undocumented. Repro: the 0.25s-per-case injection used
for R8, run with `--suite fast --update-baseline --baseline /tmp/b.json` → exit 0,
no OVER BUDGET line; drop `--update-baseline` → `OVER BUDGET: suite 'fast' wall
clock 79.02s > 60s`, exit 1. Acceptance: either the over-budget line is printed
(as a warning) on the `--update-baseline` path too, or ADR-013 Decision 2 names
`--update-baseline` as a path where the ceiling is not reported.

### T-R5 — Borrowed-browser context leak on a failed new_page            [status: todo]
Origin: PR #20 R5 (LOW, routed debt — unreachable from any committed case)
Spec: `src/browser/agent.py:311-312` creates the `BrowserContext` and its page
before the `try:` whose `finally: await ctx.close()` is the only close, so a
failure inside `ctx.new_page()` leaks that context for the life of the eval
process. The own-browser path is swept by the exit stack; the borrowed path has
no `stack.push_async_callback(browser.close)` to fall back on. Not reachable
from a committed case — a full `fast` run in reverse case order leaves
`len(_BROWSER.contexts) == 0` — and reachable only by making `ctx.new_page()`
raise on the shared path. Acceptance: `ctx` created inside the exit stack
(`stack.push_async_callback(ctx.close)`) or inside the `try`, so both paths
close it on any failure, with a case that leaks before the fix.

### T-R19 — `report-citations-resolve` only checks citation->file, never file->citation            [status: todo]
Origin: PR #20 R19 (MEDIUM, routed repair; the reverse-direction guard itself is
logged here as debt rather than built, since it is more than a "prune to fix" fix)
Spec: the merge at `94f1a42`/`7a2869a` re-added 41-46 uncited routine `fast`/
`invariant` report dumps that GW-008/ADR-012 had just pruned, and no case caught
it because `_run_report_citations_case` (`src/browser/eval_adapter.py:1014`)
is one-directional: it resolves citation -> file, never enumerates
`evals/report/*.json` and asks whether each file is cited by anything. The
uncited dumps were deleted by hand in this round (38 files: 20 `fast`, 18
`invariant`), not caught by a guard. Acceptance: `report-citations-resolve`
(or a sibling case) additionally enumerates `evals/report/*.json`, excludes the
policy-exempt kinds (`-live.json`, `-soak.json`, `-ablation*.json` — ADR-012
Consequences: "non-prunable by policy regardless of citation"), and fails if any
remaining file is cited by nothing in `REPORT_CITATION_SCOPE`. Watch it fail
first by re-adding one of the 38 pruned files uncited.

### T-R21 — the over-budget-counts-as-red report-write clause is ungraded            [status: todo]
Origin: PR #20 R21 (LOW, routed debt — reviewer's own routing)
Claim: the `or over_budget(args.suite, totals["wall_seconds"])` clause added to
`red` in `evals/run.py:217-219` is correct but ungraded — no case goes red if
that clause is deleted.
Evidence: `evals/run.py:217-219` adds `or over_budget(args.suite,
totals["wall_seconds"])` to `red`. Verified working (stubbed 99.0s fast run:
exit 1, report written, OVER BUDGET line), but `fast-wall-clock-budget`'s
`applied_in_main` probes pass `--no-report`, so they can never observe the
write policy, and no other case inspects it.
Repro: Stub main() with a 99.0s result and no --no-report; assert a report file
appears.
Acceptance: one row driving main() without --no-report on an over-budget stub
and asserting a report file appeared — or recorded as debt with the ADR saying
it is unpinned.

### T-R23 — the ADR-013 renumber sweep's commit-message tally is off by one            [status: todo]
Origin: PR #20 R23 (LOW, routed debt — classification (the thing that matters)
is correct and was verified by hand, only the published tally is wrong)
Claim: the ADR-013 renumber sweep is correct, but its published tally is off by
one: the commit message claims "four `ADR-012` hits"; there are three.
Evidence: Classified by hand: ADR-011 4 hits, all main's readiness ADR, correct.
ADR-012 3 hits (header, INDEX.md:21, evals/run.py:216), all main's report-policy
ADR, correct. ADR-010 all main's M9 ablation plus two deliberate "written as
ADR-010, shipped as ADR-013" notes. No stale ADR-013 reference in src/, evals/,
docs/, README.md or .github/.
Repro: `grep -rn 'ADR-012' --exclude-dir=.git --exclude-dir=report .` -> 3 lines.
Acceptance: the PR body / ledger tally reads 3, or drops the count in favour of
the classification.

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence. M12 resolved without amending
ADR-002 D4 — it removed 11.3s of per-case browser launch and left the 42.2s of
deliberate waiting (settle loops, bounded load/screenshot waits, one 10s click
timeout) that only parallelism can hide. `fast` now typically sits under
59.5s against a local 60s ceiling with only a thin, inconsistent margin (a
straddling band briefly pushed the ceiling to 70s, round-5 review could not
reproduce it and withdrew it, then post-commit verification found the
suite clears 60 in 20 of 21 further real runs, not all of them — ADR-013
Decision 4), so this lever is close to urgent: the next case `fast` gains,
even a cheap one, is likely to turn the ceiling red on top of the residual
noise already there.

### M15 — Verifier-accuracy dashboard UI            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M16 — Visual fallback            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M19 — ADR-011 quotes a readiness latency no report supports            [status: todo]
Origin: PR #21 R8
Spec: ADR-011 Decision 4 says "Measured in the case: 5 ms, mid-run". The eight
committed reports carrying `readyz-tracks-the-run-slot` record `during_latency_s`
of 0.001-0.007 and never 0.005. The substance holds (all <=7ms); the figure is
unsourced.
Acceptance: the ADR quotes a value that appears in a named committed report, or
states it as a range.

### M20 — ADR-011's "invariants, all graded" overstates what the case asserts            [status: todo]
Origin: PR #21 R9
Spec: Decision 3 lists five invariants as graded. Invariant 5 (starts nothing,
spends nothing) is asserted nowhere, and every sample comes from a single
submission — so moving `ACTIVE_RUN = run_id` out of `async with SEM` to
submit-time leaves `readyz-tracks-the-run-slot` PASSING, i.e. `active_run_id`
non-null while `busy` is false is undetectable. The reviewer confirmed the
seven-ablation claim in Decision 5 does reproduce; this is the eighth mutation.
Acceptance: either the ADR narrows "all graded" to what the case asserts, or the
case adds a second in-flight submission so the state is detectable — watched red.

### M21 — the soak's mid-run readiness probe is one instant, not a series            [status: todo]
Origin: PR #21 R10
Spec: `soak.py` captures `mid` once, ~2s after submission, in runs lasting
4.7-13.7s — and at ~2s the run is provably inside an await (playwright launch,
navigate, observe, the awaited planner call). D20 and ADR-011 D7 say "measured
ten times", which is ten single instants, not ten runs observed throughout. Both
documents already hedge ("narrowed, not eliminated"), which is why this is LOW.
Acceptance: the probe samples repeatedly across the run and the report carries
the series, or both documents say "one probe per run, taken ~2s in".

### M22 — ADR-011 D8 overclaims that the retry ledger is pinned            [status: todo]
Origin: PR #21 R12
Spec: the retry probe asserts `"URLError" not in json.dumps(report)`, a substring
search the per-row `retries` list already satisfies — so `summarize` can drop
`transport_retries` entirely and the case stays green. R3's acceptance is met at
the row level; the count and phase live only in the unasserted ledger field.
Acceptance: the probe asserts `transport_retries` content (count + phase at
least) so emptying the ledger reddens, or ADR-011 D8 narrows its wording.

### M23 — a retry-exhausted attempt is published as "retried through"            [status: todo]
Origin: PR #21 R13
Spec: `_http` appends the final attempt to the out-list before re-raising, with
no success marker, so a connect failure that never succeeded appears in
`transport_retries` with `count: 3` and prints under the banner "connect-phase
failures that retried through". The same event is reported twice, once with the
wrong label — on the exact distinction the ledger was added to make.
Acceptance: only attempts followed by a success are recorded, or the entry
carries `retried_through: bool` and the banner reflects it; a case pins that a
fully-failed connect produces an empty ledger.

### M25 — RETRY_SLEEPS sits under a comment describing the socket timeout            [status: todo]
Origin: PR #21 R15
Spec: `evals/ablation.py` — the "30s was too tight ... raised to ~4x the worst
observed stall" block documents `timeout: int = 120`, and `RETRY_SLEEPS = (5, 10)`
was inserted between the comment and the `def`, so the comment now reads as
describing the backoff tuple.
Acceptance: the constant sits above its own one-line comment, or the existing
block names the timeout it describes.

### M26 — the soak's swept-surface inventory omits `results`            [status: todo]
Origin: PR #21 R17
Spec: `summarize` returns 13 keys; the round-2 inventory accounts for 12 and
omits `results` — the per-row evidence body every committed soak report and
D20's row-level recomputation rest on. Blanking it leaves the case green, and
the retry probe's substring check still passes because `transport_retries`
carries the string, so nothing reddens when the artifact loses all its evidence
rows. The case's triage note also calls `transport_retries` "the remaining
published field" when five are unasserted.
Acceptance: a `want` dict asserts `len(report["results"]) == len(rows)`, or the
inventory and the triage sentence name `results` and the passthrough group so
the sweep claim is honest about what it does not cover.

### M27 — The soak cannot separate a bad deployment from a bad third-party site            [status: todo]
Origin: PR #21 R1 (logged there as M18; renumbered on the PR #23 merge — both branches allocated M18 by "next free", the T-ADR-NUM failure mode applied to task ids)
Spec: `summarize` now borrows `ablation.is_measurement` to decide what a
completion is, so a live task ending `failure:nav` because the site itself was
down drops `demo_ready` to false and reads as if the deployment failed. That is
the safe direction to be wrong in and it is why it shipped, but it is still a
conflation: "we could not measure this run" and "this deployment could not
complete it" are different verdicts. Acceptance: a case injects a terminal
`failure:nav` on the live task and pins that the report distinguishes it from a
deployment fault without ever letting it count as a clean completion.

### M17 — Per-IP rate limiting            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### T-R24 — nothing grades which browser an eval case is allowed to use            [status: todo]
Origin: PR #23 R7 (LOW, routed debt by the reviewer)
Spec (claim): the N1 repair is narrower than the premise it was accepted on, and
the resolution artifact overstated it: the `invariant` suite still needs a real
Chromium in six cases, so "invariant is pure code, no browser" is not restored —
only the newest violation was retagged, and nothing grades the rule.
Evidence: `tasks/reviews/pr23-r3-resolution.json` claimed the fix retains
coverage "without an invariant Playwright import". With a broken browser path the
invariant suite drops to 28/34: `ablation-env-failure-is-a-result`,
`contract-trace-schema`, `observe-content-survives-chrome`,
`readyz-tracks-the-run-slot`, `supersede-never-dangles` and
`url-guard-holds-after-navigation` all fail. `_check_supersede_dangling`
(`src/browser/eval_adapter.py`) calls `_run_agent` without `own_browser`, which
routes to `_browser()`. These six are inherited from main, but they make the
resolution's green sentence untrue of the suite, and no case reddens if
`ui-rendered-narrow` is retagged back into `invariant`.
Repro: PLAYWRIGHT_BROWSERS_PATH=/nonexistent-browsers python3 -m evals.run --suite invariant --no-report 2>&1 | grep -E "^\[FAIL\]|suite 'invariant'"
(reproduced in PR #23 R4 repair: 28/34, exactly those six).
Acceptance: a case grades the invariant suite's purity so the retag cannot
silently reverse. The R3 resolution's `green` text was narrowed in the R4 repair,
which is the honesty half; this block is the graded half.
Same family, same gap, found in the same round: ADR-013 Decision 1 says the suite
shares one Chromium, and `ui-rendered-narrow` owned its own for a whole review
round with nothing red (PR #23 R5). `agent-launches-its-own-browser` did NOT miss
it — that case grades `run_task(browser=None)`, the production launch branch, and
`ui-rendered-narrow` never routes through `run_task`. Do not widen that case:
what is missing is a check on the eval harness's own renderers, not on the agent.

### T-R25 — INDEX.md's ADR-002 line still publishes the withdrawn 70s local ceiling            [status: todo]
Origin: PR #23 R8 (LOW, routed debt by the reviewer)
Spec (claim): `specs/decisions/INDEX.md`'s ADR-002 line still publishes the
withdrawn 70s local ceiling, contradicting ADR-002 itself and INDEX's own ADR-013
line.
Evidence: `specs/decisions/INDEX.md:11` — "fast wall clock ≤ each environment's
own measured ceiling (70s local, 80s CI — ADR-013 Decisions 3 and 4)" vs
`INDEX.md:22` "60s locally (a straddling band briefly moved it to 70s, withdrawn
the same day ...)", `specs/decisions/ADR-002-performance-thresholds.md:4` "60s
locally, 80s on CI", and `evals/run.py:80` `WALL_BUDGET_S = {"fast": 60}`.
Inherited: byte-identical to `git show fcdc6b0^2:specs/decisions/INDEX.md` line
11, so the hand resolution did not introduce it — but INDEX.md was one of the
three hand-resolved files in this diff and `adr-header-and-index` only checks
numbers, never the prose.
Repro: sed -n '11p;22p' specs/decisions/INDEX.md && sed -n '80p' evals/run.py
Acceptance: INDEX.md:11 reads "60s local, 80s CI", matching ADR-002:4,
INDEX.md:22 and `WALL_BUDGET_S`. Held out of PR #23 deliberately: the one-word
edit is not the point, a guard that reads the ceiling out of `WALL_BUDGET_S`
instead of out of prose is.

### T-R26 — two review artifacts route to task ids that no longer resolve            [status: todo]
Origin: PR #23 R9 (LOW, routed debt by the reviewer)
Spec (claim): task-id bookkeeping around the M18/M27 renumber leaves two
artifacts pointing at ids that no longer resolve.
Evidence: `tasks/reviews/pr21-r1-resolution.json:32` still routes the soak
finding to `{"id": "M18", "origin": "PR #21 R1"}` while that block is now
`tasks/TODO.md` `### M27`; TODO.md documents the renumber but the artifact is not
cross-linked, so a reader following pr21-r1-resolution lands on the TinBoker
restyle. Separately, `tasks/reviews/pr21-r2-resolution.json:11` routes R14 to
`debt_id: "M24"` and no `### M24` block exists in `tasks/TODO.md` on this branch
or on `fcdc6b0^2` (inherited from main).
Repro: grep -n '"M18"\|M24' tasks/reviews/pr21-r*.json && grep -nE '^### (M24|M27)' tasks/TODO.md
Acceptance: pr21-r1-resolution.json's debt id reads M27 (or carries a
`renumbered_to` field), and M24 either exists in TODO.md or the pr21-r2 routing
is corrected. Same root cause as T-ADR-NUM's fourth instance — fix them together
or the next renumber re-opens this.

### T-R27 — in a git worktree the pre-commit gate runs the MAIN checkout's hook script            [status: todo]
Origin: PR #23 R4 repair (discovered mid-task, no finding id)
Spec (claim): `core.hooksPath` is repo-level and absolute
(`/Users/willy/Documents/browser-agent/.githooks`), so a commit made in a
pr-loop worktree executes the hook script as it exists in the MAIN checkout's
working tree, not the one on the branch being committed. The hook then `cd`s to
`git rev-parse --show-toplevel` — the worktree — so it grades the right tree
with the wrong script.
Evidence: this round's second commit attempt was blocked by the gate on a 60.18s
fast run (`evals/report/history.jsonl` ts 20260822-011326, sha c947008,
102/102 = 1.000, `"report": null`) and left no per-case report, even though
`evals/run.py:219-222` puts `over_budget` into `red` precisely so an
over-budget run writes one — verified directly:
`over_budget('fast', 60.18)` is True, and a stubbed 99s run writes
`<ts>-fast.json` and records it in the history line. The reason is that
`/Users/willy/Documents/browser-agent/.githooks/pre-commit:14` (the main
checkout, on an older `main`) still passes `--no-report`, while both
`origin/main` and this branch carry the version that does not. Every commit made
from any worktree therefore silently ran the older gate.
Repro: git config core.hooksPath; diff /Users/willy/Documents/browser-agent/.githooks/pre-commit .githooks/pre-commit
Acceptance: the enforcement layer stops depending on which checkout the hook
file happens to live in — the hook execs the script from the tree being
committed (`git show :.githooks/pre-commit` or `$(git rev-parse --show-toplevel)/.githooks/pre-commit`),
or `pr-loop` sets `core.hooksPath` per worktree when it creates one. Same family
as the venv gap already known for worktrees: enforcement that a branch changes
is not the enforcement its own commits get.

### T-R28 — `_run_ui_rendered_case` leaks a BrowserContext when the case errors            [status: todo]
Origin: PR #23 round-5 verification (out-of-scope note, no finding id)
Spec: the R5 repair moved the case onto the shared Chromium, but its `go()`
closes the context only on the success path, so an exception inside
`page.evaluate` leaks a BrowserContext onto the shared browser for the rest of
the suite. Its sibling `_run_observe_case` (`src/browser/eval_adapter.py:466`)
already uses the try/finally pattern this one needs.
Evidence: reproduced by renaming `stepEl` in the PAGE source — the case raises
and `len(_BROWSER.contexts) == 1` afterwards; on the clean pass path four
consecutive warm invocations leave `len(_BROWSER.contexts) == 0`. Reachable
only when the case is already erroring, which is why it did not block PR #23.
Acceptance: `go()` wraps its context in try/finally, and a case asserts the
shared browser holds no contexts after a deliberately-erroring render.

### T-R29 — `docs-numbers-are-derived` asserts substring presence, so a contradicting line beside a correct one stays green            [status: todo]
Origin: PR #23 round-5 verification (out-of-scope note, no finding id)
Spec: the R4 repair made README's "Where it stands" block recompute from the
report files it cites, but the assertion is `expected_string in readme`. A
README that keeps the correct line and adds a contradicting one next to it is
still green — the same class of drift R4 was filed for, one step removed.
Acceptance: the check pins the block's content rather than the presence of
strings within it — parse the fenced block and compare it whole, or assert that
no other line in it parses as a competing figure for the same field.

## Notes

### Reopen — A-phase (2026-08-17)
Owner decision, recorded in `prompts/008-a-level-reopen.md`: B-baseline
accepted; repo does not go public yet; Task 1 reopened for A-level before
submission. Task 2 start deferred by the same decision; the A-phase carries
its own +12h hour guard. M6–M10 are the A-phase roadmap, ranked by
reviewer-value ÷ effort against the two gaps the freeze measured (live
breadth, verifier accuracy).

Plans: `docs/plans/active/task1-a-level-plan.md` ·
`docs/plans/completed/task1-b-level-plan.md` ·
Methodology: `docs/evals/evaluation-methodology.md` ·
Architecture: `docs/architecture/task1-overview.md`
