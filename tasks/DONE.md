# Done — one line per merged task

Append-only index. Details live in each milestone's ADR/PR and
`tasks/pr-loop-ledger.jsonl`; the full milestone-table narrative is in git
history (`tasks/TODO.md` as of `98de1a6`, blocks as of `127bd58`).

- M0 — Harness (2026-08-15) — ADR-001
- M1 — Walking Skeleton (2026-08-15) — specs/001, prompts/002, run 09b21b3a
- M2 — Eval Backbone (2026-08-16) — ADR-002, docs/evals/scope-checkpoint.md
- M3 — Reliability (2026-08-16) — ADR-003
- M4 — Reviewer UI (2026-08-16) — ADR-004; M3+M4 cold review: ADR-005
- M5 — B-Freeze (2026-08-17) — docs/plans/completed/task1-b-level-plan.md, docs/analysis.md
- M6 — Live breadth & depth (2026-08-17) — ADR-006; post-M6 nav fix: ADR-007
- M7 — Verifier accuracy (2026-08-18) — ADR-008, PR #10, support-matrix D1–D4
- M8 — Mutation & hostility hardening (2026-08-19) — ADR-009, PR #12, support-matrix D5–D11
- M9 — Cost/model ablation (2026-08-21) — ADR-010, PR #15 (mechanism) + PR #19 (numbers), support-matrix D12–D19; default moved to `openai/gpt-5.6-luna`

## B-floor exit criteria — final status
All 6 met: criterion 2 (coverage/live breadth) was partial at the M5 freeze
and closed by M6 (3 live domains, 3 live task classes, live 6/6 after
ADR-007). Full criterion table with evidence: `tasks/TODO.md` at `98de1a6`
and `docs/plans/completed/task1-b-level-plan.md`. Standing qualification:
green live cases run hand-written plans, so live *planning* quality is
unmeasured (ADR-007) — the M5/M10 held-out probes are the counterweight.
