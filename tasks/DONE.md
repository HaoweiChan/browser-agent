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
- M12 — Fast-suite wall-clock over budget (2026-08-21) — ADR-013, PR #20; ceiling is per-environment now, ADR-002 D4 ends unmoved at 60s
- M18 — TinBoker reviewer UI restyle (2026-08-21) — ADR-014, PR #23, trace in tasks/reviews/pr23-r*.json
- M10 — A-Freeze (2026-08-22) — ADR-015, PR #25, trace in tasks/reviews/pr25-r*.json; probe #2 ran RED on the inviolable property, fixed in-PR for the aggregate shape only — criterion 5 reopened as M29/M34 by the post-merge live verification
- M30 — Interview demo execution UI (2026-08-22) — PR #24
- M29 — criterion 5 is red on the deployed build, record corrected (2026-08-22) — ADR-015 amended, PR #28, trace in tasks/reviews/pr28-r*.json
- M34 — an answer that is page furniture can no longer be reported as success (2026-08-22) — ADR-016, PR #30, trace in tasks/reviews/pr30-r*.json; closed the aggregate/furniture shape offline, but the post-merge confirmation refuted it on the real site (6 wrong-answer-as-success in 9 runs) — ADR-015 criterion 5 stays RED, follow-up is M36
- M31 — Plan lint + `extract_all` (2026-08-22) — ADR-018, ADR-019, PR #29, trace in tasks/reviews/pr29-r*.json; 5 rounds, 2 circuit breakers
- M36 — Responsiveness judged by an LLM, last rung of the ladder (2026-08-22) — ADR-017, PR #33, trace in tasks/reviews/pr33-r*.json
- M35 — Visitor-facing console: verified example prompts, plain-language limits, no-URL guard (2026-08-23) — PR #32, trace in tasks/reviews/pr32-r*.json
- T-R34 — the band's slack becomes a declared ceiling (2026-08-23) — ADR-019, PR #35, trace in tasks/reviews/pr35-r*.json; 4 rounds, 1 circuit breaker

## B-floor exit criteria — final status
All 6 met: criterion 2 (coverage/live breadth) was partial at the M5 freeze
and closed by M6 (3 live domains, 3 live task classes, live 6/6 after
ADR-007). Full criterion table with evidence: `tasks/TODO.md` at `98de1a6`
and `docs/plans/completed/task1-b-level-plan.md`. Standing qualification:
green live cases run hand-written plans, so live *planning* quality is
unmeasured (ADR-007) — the M5/M10 held-out probes are the counterweight.
