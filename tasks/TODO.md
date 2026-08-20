# Task 1 milestones — pr-loop queue

Block format: groundwork pr-loop (`### <id> — title [status: …]`);
`python3 tasks/ready.py` lists what is unblocked; protocol in the groundwork
plugin's `pr-loop` skill. Milestone-level only (ADR-001) — micro-tasks stay
in the session. Reviewer evidence tags reference the rubric cells in
`docs/product/assignment-requirements.md` §E1–E5. Converted 2026-08-20 from
the milestone table: the full per-milestone evidence prose lives in git
history (`tasks/TODO.md` as of `98de1a6`) and in each milestone's ADR —
blocks here carry the decision pointers, not the narrative. A-phase hour
guard: +12h (Reopen note below).

## Queue

### M9 — Cost/model ablation            [status: todo]
Spec: ≥2-model OpenRouter ablation, cost/latency tradeoff table, ADR for the
default-model choice. Reviewer evidence: analysis (E4), E5 tradeoffs.
Acceptance: table built from committed report runs, not estimates.

### M10 — A-Freeze            [status: todo]
Depends: M9
Spec: analysis/README/support-matrix refresh, prompts curated, second
held-out probe vs the deployed URL (mandatory gate, raw results committed).
Acceptance: A-exit criteria in `docs/plans/active/task1-a-level-plan.md` all
green → owner decides submission/public.

## Debt

### M11 — Live-drift snapshot replay            [status: todo]
Origin: M8's SHOULD item, left open at the M8 merge (PR #12)
Spec: replay committed live-page snapshots so live-site drift is detected
without network. Acceptance: a drifted snapshot turns a case red offline.

### M12 — Fast-suite wall-clock over budget            [status: todo]
Origin: PR #12, declared in support-matrix D8
Spec: `fast` is 68.2s against ADR-002 D4's 60s budget — 10.6s is one
deliberate click timeout, the rest a growth trend that crosses the budget
regardless of any one milestone. Acceptance: fast < 60s again, or ADR-002 D4
amended with the measured floor and why.

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence; M12 is the motivating symptom.

### M15 — Verifier-accuracy dashboard UI            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M16 — Visual fallback            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M17 — Per-IP rate limiting            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

## Done

### M0 — Harness            [status: done]
Planning package, ADR-001, prompts convention, CLAUDE.md amendments, suite
naming, browser-domain + finish-task skills, agent charters. Validation:
spec-drift found no contradiction; fast suite exits 0.

### M1 — Walking Skeleton            [status: done]
`specs/001-browser-contract.md`, trace schema, NL task → plan → execute →
result via CLI, pre-flight screening, Zeabur deploy spike. Validated on the
deployed instance (run `09b21b3a`); INV-0 no longer decorative. Details:
prompts/002.

### M2 — Eval Backbone            [status: done]
Fixtures + 3 tier-breaking mutations, EvalAuditor adapter, OutcomeVerifier
L1–L2, TC1–TC5 coverage, LLM stub boundary, cost fields. 41/41 fast, 5/5
invariant, 6/6 traps. Thresholds: ADR-002. Preceded M3 with the committed
scope checkpoint (`docs/evals/scope-checkpoint.md`: 12 observed failures →
2 mechanism families chosen, third refused).

### M3 — Reliability            [status: done]
7-class failure classifier, recovery ladders for the checkpoint-chosen
families, budgets, self-maintenance relocation loop. First relocated-success
measured (`l4-shop-button-text-renamed` red → green on an unchanged plan);
INV-3 added. Details: ADR-003.

### M4 — Reviewer UI            [status: done]
Full frontend on the live deployment: SSE trace stream, per-step screenshots,
support matrix served from its own markdown, spend/URL guards verified
in-browser. Details: ADR-004. Post-hoc cold review of M3+M4 (ADR-005): 6
defects in already-green code found and fixed (3 wrong-answer-scores-PASS),
7 findings deliberately not fixed, declared.

### M5 — B-Freeze            [status: done]
Coverage verified, `docs/analysis.md` from report data, README rewrite,
held-out probe vs the deployed URL (2/8 correct, 1/2 refusals, no wrong
answer reported as success — found and fixed the `log into` scope bypass).
B-floor: 5 of 6 criteria met; criterion 2 (live breadth) short → M6.
Exit criteria: `docs/plans/completed/task1-b-level-plan.md`.

### M6 — Live breadth & depth            [status: done]
3 live domains / 3 task classes cased; `near:` implemented (advertised since
M1, first code path now); 3 silent-wrongness defects from live sites + 4 more
from cold review, all cased. Closed B-floor criterion 2. Details: ADR-006.
Post-M6 fix (ADR-007): `navigate()` helper — `domcontentloaded` + bounded
`load` wait — took live to 6/6 after openlibrary recovered.

### M7 — Verifier accuracy            [status: done]
25 hand-labeled runs frozen and replayed through runtime `verify()`:
precision 0.476 / recall 0.909, headline being that the pre-fix verifier
passed 23/23 records right or wrong; `not_a_dump` added (measured threshold),
10 wrong-answer false positives declared not chased. Merged via peer-review
round on PR #10 (window-denominator fix, red first). Details: ADR-008,
support-matrix D1–D4.

### M8 — Mutation & hostility hardening            [status: done]
Five B-strong mutations on a stated admission test (2 committed as pinned
losses — element-reordered's confident wrong answer is the first measurement
of what `near:` was built for); hostile 4th live domain quotes.toscrape.com
published raw — the `/js` aggregate-page anchor hole reports `success` with
answer "Next →". First full pr-loop delivery (PR #12, 4 review rounds):
mutation metrics extracted to `mutation_metrics()` and pinned by a 10-row
discrimination-measured honesty case; known-wrong ground-truth pins now carry
`answer_is_known_wrong` end to end. mutation 9/11, 6 recovered (5 by
relocating); 86/86 fast, 22/22 invariant, 9/9 live. Details: ADR-009 D1–D9,
support-matrix D5–D11.

## Notes

### Reopen — A-phase (2026-08-17)
Owner decision, recorded in `prompts/008-a-level-reopen.md`: B-baseline
accepted; repo does not go public yet; Task 1 reopened for A-level before
submission. Task 2 start deferred by the same decision; the A-phase carries
its own +12h hour guard. M6–M10 are the A-phase roadmap, ranked by
reviewer-value ÷ effort against the two gaps the freeze measured (live
breadth, verifier accuracy).

### B-floor exit criteria — final status
All 6 met: criterion 2 (coverage/live breadth) was partial at the M5 freeze
and closed by M6 (3 live domains, 3 live task classes, live 6/6 after
ADR-007). Full criterion table with evidence: `tasks/TODO.md` at `98de1a6`
and `docs/plans/completed/task1-b-level-plan.md`. Standing qualification:
green live cases run hand-written plans, so live *planning* quality is
unmeasured (ADR-007) — the M5/M10 held-out probes are the counterweight.

Plans: `docs/plans/active/task1-a-level-plan.md` ·
`docs/plans/completed/task1-b-level-plan.md` ·
Methodology: `docs/evals/evaluation-methodology.md` ·
Architecture: `docs/architecture/task1-overview.md`
