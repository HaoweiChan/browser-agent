# docs/ — what is here and which parts are still live

Two kinds of document live here. **Living** ones are refreshed at milestones
and cross-checked by invariant cases (`docs-numbers-are-derived`,
`support-matrix-cites-real-cases`, `report-citations-resolve`). **Records** are
frozen at the moment they describe and are not updated afterwards — read the
date, not the tense.

| File | Kind | What it answers | Current to |
|---|---|---|---|
| [`analysis.md`](analysis.md) | living | The numbers: suites, cost, latency, coverage, verifier accuracy, the two held-out probes (§8a, §8a-2), the model ablation (§9), not-measured list | M10 (2026-08-22) |
| [`support-matrix.md`](support-matrix.md) | living | Per-site / per-task-class status and every declared limitation D1–D22, each citing a case id; rendered live by the frontend from the same file | M10 |
| [`architecture/task1-overview.md`](architecture/task1-overview.md) | living | Why architecture B (deterministic execution + LLM evolving-prefix planning) over A/C; components; step schema; ops | M9 (default model) |
| [`evals/evaluation-methodology.md`](evals/evaluation-methodology.md) | living | What is measured, how, and what was dropped with reasons; suite definitions; verifier layers | M9 |
| [`evals/failure-taxonomy.md`](evals/failure-taxonomy.md) | living | The seven failure classes, correction vs maintenance, locator tiers, mutation catalogue | M6 |
| [`product/assignment-requirements.md`](product/assignment-requirements.md) | living | Requirement matrix T1–T10 / E1–E5 with evidence status per row | M7 |
| [`product/problem-definition.md`](product/problem-definition.md) | record | Operational problem definition and MUST/SHOULD/BACKLOG scope, written before code | M0 |
| [`evals/scope-checkpoint.md`](evals/scope-checkpoint.md) | record | The 12 observed failures that chose the two recovery families before M3 | M2→M3 |
| [`plans/completed/task1-b-level-plan.md`](plans/completed/task1-b-level-plan.md) | record | B-phase plan and exit criteria, final status | M5 |
| [`plans/completed/task1-a-level-plan.md`](plans/completed/task1-a-level-plan.md) | record | A-phase plan and the six exit criteria the freeze walked | M10 |
| [`ui.png`](ui.png) | asset | README screenshot — a real run on the deployment (`b3773c6e`, 2026-08-22, dark scheme) | — |

Where the rest lives: decisions are `specs/decisions/ADR-*.md` (digest in
`INDEX.md`); the working contract is `CLAUDE.md`; the milestone queue is
`tasks/TODO.md`; the AI-collaboration record is `prompts/`.
