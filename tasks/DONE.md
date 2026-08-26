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
- M37 — Swap the HN Try example for one that reproduces on the deployed build (2026-08-23) — PR #37, efb2711
- T-R56 — the band subsystem's documents and its own strings say what the code does (2026-08-23) — ADR-019, PR #36, trace in tasks/reviews/pr36-r*.json; 5 rounds, 1 circuit breaker; bundles T-R45/46/47/48/49/52/54/55
- M28 — a verifier-rejected run carries no answer: the dump stays in evidence, the reason cites it by preview (2026-08-23) — PR #38
- M32 — Observation drill-down: the planner can ask for a deeper view of the page (2026-08-23) — ADR-020, ADR-021, PR #34, trace in tasks/reviews/pr34-r*.json; 6 rounds, 1 circuit breaker, 7 merges of main; ADR-020 written then reverted as superseded
- T-M32-13 — the ledger's `ts` becomes a valid ordering key: stamped UTC, not naive local (2026-08-23) — found and root-caused on `task/M32` from PR #34's CI red; closed by T-R44 on both halves (UTC stamp + per-row `env`), ADR-019 §7, cases `ledger-ts-orders-real-time` and `band-is-graded-against-its-own-environment`
- T-R78 — §7 stops claiming §5 names a demonstrating mutation for every graded item (2026-08-24) — PR #41 R17, the fifth instance of the class; the pointer now names `ci-numbers-are-derived`'s `watched_red`, closed in T-R44's merge commit

- T-M40-1 — a browser check takes the run slot instead of reading it (2026-08-24) — PR #45, trace in tasks/reviews/pr45-r*.json; 3 rounds, 1 circuit breaker (human ruled option B: R8/R9 shipped as T-R89/T-R90). Nine debt items T-R82..T-R90, renumbered from T-R73..T-R79 after the final merge found seven ids defined differently on both sides with tasks/TODO.md auto-merging clean
- T-M40-2 — the document root is not an answer: the plan lint refuses it at both adoption points (2026-08-24) — ADR-024, PR #46, trace in tasks/reviews/pr46-r*.json; 3 rounds, approved
- M38 — Resolver disambiguation: a target with several matches is narrowed, not failed (2026-08-24) — PR #42, trace in tasks/reviews/pr42-r*.json; 6 rounds, approved
- M39 — a malformed judge completion is retried once, then fails closed exactly as before (2026-08-24) — ADR-023, PR #44, trace in tasks/reviews/pr44-r*.json; 5 rounds, 2 circuit breakers, 12 findings (2 HIGH / 4 MEDIUM / 6 LOW), 13 debt items T-M39-1..T-M39-13, gate green at every commit. Reading a verdict out of an uncontrolled completion fail-opened four times — fence strip, `re.fullmatch`, unguarded object scan, then the published claim about the guard that fixed it — three of them regressions against main, every one through a green gate, because nothing asserted over the *completion* until this PR. Two of the twelve findings originated on the review side. Five merge laps (T-M39-11); the last red was contention rows never in the index, not a regression
- T-R61 — the task field's placeholder still advertises the retired HN prompt (2026-08-24) — closed inside M40's PR #43; acceptance's second half (a `ui-form` pin on placeholder text) explicitly not met, so it can regress silently
- T-M32-9 — three published wall-clock ceilings are not the enforced ones, CLAUDE.md included (2026-08-24) — PR #40, trace in tasks/reviews/pr40-r*.json; pinned by `ceiling_sweep_rows`
- T-R44 — a published band is graded only against rows from its own environment (2026-08-24) — ADR-019 §7, PR #41, trace in tasks/reviews/pr41-r*.json; bundles T-R51, closes T-M32-13's second half
- M40 — the demo surface tells the truth about itself, and the matrix covers the domains a reviewer reaches for (2026-08-24) — PR #43, trace in tasks/reviews/pr43-r*.json; support-matrix D28; also closed T-R61
- T-M40-4 — deploy-smoke treats "refused because a run is executing" as not-a-failure, and says UNCHECKED when it exhausts retries (2026-08-24) — PR #47
- M41 — the agent answers from its own sec-10k inspector, and the matrix says exactly how far that goes (2026-08-26) — ADR-030, PR #58, trace in tasks/reviews/pr58-r*.json; 4 rounds, 1 circuit breaker (human ruled option A), support-matrix D30 declared `unreliable` at 4/6 with zero wrong-success; eight debt items T-M41-1..8
- M42 — loop mode: the model chooses every step, and the machinery that grades it does not move (2026-08-26) — ADR-028 (loop mode) + ADR-029 (local `fast` ceiling 90 -> 105), PR #57, trace in tasks/reviews/pr57-r*.json; 7 rounds, 4 human interventions; observation now pierces iframes and open shadow roots, a no-progress harness ends a circling run loudly, and ADR-024/ADR-018's guards are re-homed as tool-call-time refusals

## B-floor exit criteria — final status


All 6 met: criterion 2 (coverage/live breadth) was partial at the M5 freeze
and closed by M6 (3 live domains, 3 live task classes, live 6/6 after
ADR-007). Full criterion table with evidence: `tasks/TODO.md` at `98de1a6`
and `docs/plans/completed/task1-b-level-plan.md`. Standing qualification:
green live cases run hand-written plans, so live *planning* quality is
unmeasured (ADR-007) — the M5/M10 held-out probes are the counterweight.
