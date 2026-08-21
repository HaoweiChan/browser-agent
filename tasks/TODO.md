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

### M9 — Cost/model ablation            [status: pr]
PR: #15 · evidence pack in the PR body · ADR-010
Spec: ≥2-model OpenRouter ablation, cost/latency tradeoff table, ADR for the
default-model choice. Reviewer evidence: analysis (E4), E5 tradeoffs.
Acceptance: table built from committed report runs, not estimates.
State: **the mechanism ships; the table ships empty and graded.** The key lives
only in Zeabur and `POST /tasks` could not vary the model, so the numbers cannot
exist until this merges and redeploys. `analysis-ablation-table-not-estimated`
holds the gap shut: while §9 declares itself pending it must carry zero data
rows, and once it names a committed report every cell must equal what the
driver's formatter derives from that report.
Ceiling: the **model** `deepseek/deepseek-v4-pro`, not a number — its list price
moved $1.44/$2.88 → $1.60/$3.20 per M inside one working session (two reads, two
hours apart), so `PRICE_CEILING` was deleted and the eval derives the ceiling
from the snapshot entry. No cell measures the incumbent `claude-sonnet-4.5`
($3/$15, priced out), so the question is now "which affordable model replaces
the default", with the ceiling an owner input, not a measurement (D14).
Loop: 5 review rounds, 24 findings (4H/12M/8L), none rejected, 0 gate failures,
$0.00 spent. Gate at merge: invariant 27/27, fast 91/91.
Stage two after merge+redeploy: `python3 -m evals.ablation` → commit the report
→ paste the table under `<!-- ablation-table -->` → name the report in §9.

### M12 — Fast-suite wall-clock over budget            [status: pr]
Origin: PR #12, declared in support-matrix D8 (promoted from Debt 2026-08-20 —
M10 cannot exit green while a declared gate-budget breach stands)
Spec: `fast` is 68.2s against ADR-002 D4's 60s budget — 10.6s is one
deliberate click timeout, the rest a growth trend that crosses the budget
regardless of any one milestone. Acceptance: fast < 60s again, or ADR-002 D4
amended with the measured floor and why.
Resolved by acceptance branch 1 (`specs/decisions/ADR-011-fast-suite-wall-clock.md`):
per-call measurement put 11.3s of the 67.0s in per-case browser process
lifecycle, which the harness no longer pays; 42.2s of deliberate waiting was
left alone. `fast` is 56.47s over 95 cases and ADR-002 D4's 60s is unmoved as
the local number; CI got its own measured 75s (ADR-011 Decision 3) after its
first run showed main had been at 89.62s against the same 60s, unchecked.
Review round 1 (PR #20) falsified the first enforcement — a case reading the
newest committed report cannot go red on a fresh CI clone — so the ceiling now
lives in `evals/run.py` and gates the run it measured.

### M10 — A-Freeze            [status: todo]
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
on a tree that is over the ceiling and says nothing. ADR-011 Decision 2 describes
the ceiling as "the same shape as the invariant-100% rule beside it" — which sits
at line 162 and is bypassed by the same early return, so the shape does match, but
the resulting silence is undocumented. Repro: the 0.25s-per-case injection used
for R8, run with `--suite fast --update-baseline --baseline /tmp/b.json` → exit 0,
no OVER BUDGET line; drop `--update-baseline` → `OVER BUDGET: suite 'fast' wall
clock 79.02s > 60s`, exit 1. Acceptance: either the over-budget line is printed
(as a warning) on the `--update-baseline` path too, or ADR-011 Decision 2 names
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

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence. M12 resolved without amending
ADR-002 D4 — it removed 11.3s of per-case browser launch and left the 42.2s of
deliberate waiting (settle loops, bounded load/screenshot waits, one 10s click
timeout) that only parallelism can hide. `fast` now sits at 56.47s with
~3.4s of headroom after the M9 merge, so this is the next lever when the ceiling
goes red rather than an urgent one today (ADR-011).

### M15 — Verifier-accuracy dashboard UI            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M16 — Visual fallback            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M17 — Per-IP rate limiting            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

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
