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

### M9 — Cost/model ablation            [status: todo]
Spec: ≥2-model OpenRouter ablation, cost/latency tradeoff table, ADR for the
default-model choice. Reviewer evidence: analysis (E4), E5 tradeoffs.
Acceptance: table built from committed report runs, not estimates.

### M12 — Fast-suite wall-clock over budget            [status: in-progress]
Origin: PR #12, declared in support-matrix D8 (promoted from Debt 2026-08-20 —
M10 cannot exit green while a declared gate-budget breach stands)
Spec: `fast` is 68.2s against ADR-002 D4's 60s budget — 10.6s is one
deliberate click timeout, the rest a growth trend that crosses the budget
regardless of any one milestone. Acceptance: fast < 60s again, or ADR-002 D4
amended with the measured floor and why.
Resolved by acceptance branch 1 (`specs/decisions/ADR-010-fast-suite-wall-clock.md`):
per-call measurement put 11.3s of the 67.0s in per-case browser process
lifecycle, which the harness no longer pays; 42.2s of deliberate waiting was
left alone. `fast` is 54.1-55.9s over 90 cases and ADR-002 D4's 60s is unmoved.
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

### T-R6 — No sanctioned escape when the wall-clock ceiling is unreachable            [status: todo]
Origin: PR #20 R6 (LOW, routed debt — a repo-owner policy call, not a fix to improvise)
Spec: ADR-010 keeps the wall-clock ruling out of `invariant` because a wall
clock is machine-dependent, then hard-gates it anyway: since round 1 the repo
`evals/run.py` exits non-zero on any `fast` run over 60s, and `.githooks/pre-commit`
runs exactly that. ADR-009 Decision 6 records this same suite at 68.6s on a
reviewer's machine, CLAUDE.md rule 1 forbids `--update-baseline` to clear a
gate, and rule 5 makes `--no-verify` an emergency — so a contributor on slower
hardware has no sanctioned move. (Round 1 removed the accidental escape the
finding names: with the ceiling in the runner rather than in a report-reading
case, deleting a report no longer unblocks anything, and the failure is at
least loud — `OVER BUDGET: suite 'fast' wall clock …s > 60s` — instead of a
mysterious 89/90.) Acceptance: ADR-010 names the escape (documented env-var
override, per-machine calibration factor, or an explicit "run the gate on
reference hardware" rule), or the ceiling is re-expressed as something
machine-independent (summed deliberate-wait budget, per-case counts).

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence. M12 resolved without amending
ADR-002 D4 — it removed 11.3s of per-case browser launch and left the 42.2s of
deliberate waiting (settle loops, bounded load/screenshot waits, one 10s click
timeout) that only parallelism can hide. `fast` now sits at 54.1-55.9s with
~4-6s of headroom, so this is the next lever when `fast-wall-clock-budget`
goes red rather than an urgent one today (ADR-010).

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
