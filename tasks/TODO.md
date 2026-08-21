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
PR: #15 (mechanism, merged) + stage two (this branch) · ADR-010 · evidence in the PR bodies
Spec: ≥2-model OpenRouter ablation, cost/latency tradeoff table, ADR for the
default-model choice. Reviewer evidence: analysis (E4), E5 tradeoffs.
Acceptance: table built from committed report runs, not estimates. **Met** —
`evals/report/20260821-004617-ablation.json`, re-derived cell-by-cell into
`docs/analysis.md` §9 by `analysis-ablation-table-not-estimated`.
Result: every candidate tied on correctness across a ~17x price range, so
Decision 5's pre-committed rule fell to its cost tie-breaker and **the default
moved to `openai/gpt-5.6-luna`** from `anthropic/claude-sonnet-4.5` (ADR-010
Decision 18). The tie is *no observed difference*, not equivalence — the failed
sweeps flipped the same cells in both directions, so a second sweep would not
reproduce it cell-for-cell.
Two findings larger than the ranking: one task failed on **all four** models with
one signature (a `near:` capability boundary, D17 — counted against no model),
and the deployment could not sustain a 20-run sweep (five aborted, D18).
Guard inverted with the decision: it used to require the incumbent to be over
the ceiling, now requires the default to be a model the ablation measured.
Watched red four ways.
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
