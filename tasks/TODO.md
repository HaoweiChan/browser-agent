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

### M12 — Fast-suite wall-clock over budget            [status: todo]
Origin: PR #12, declared in support-matrix D8 (promoted from Debt 2026-08-20 —
M10 cannot exit green while a declared gate-budget breach stands)
Spec: `fast` is 68.2s against ADR-002 D4's 60s budget — 10.6s is one
deliberate click timeout, the rest a growth trend that crosses the budget
regardless of any one milestone. Acceptance: fast < 60s again, or ADR-002 D4
amended with the measured floor and why.

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

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence; M12 (now in Queue) is the
motivating symptom — if M12 resolves by amending ADR-002 D4, M14 loses urgency.

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

### M18 — The soak cannot separate a bad deployment from a bad third-party site            [status: todo]
Origin: PR #21 R1
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
