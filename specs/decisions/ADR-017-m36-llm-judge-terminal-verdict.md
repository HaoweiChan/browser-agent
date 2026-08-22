# ADR-017: M36 — an LLM judge, not a fifth structural heuristic, decides responsiveness

Date: 2026-08-22
Status: accepted

**Ruling**: `verify()`'s L1 deterministic checks stay and run first, unchanged. A run that passes every one of them now reaches one more, LAST rung: `agent.py`'s `_apply_judge` calls an LLM (stubbed at $0 in `fast`, cached and budget-capped at 1 call/run when live) with the task, the candidate answer, and the page evidence — never the task string — and any non-certify outcome (reject, error, timeout, missing key, budget exhausted) fails the run CLOSED.
**Because**: four structural mechanisms in a row (`\blog ?in\b`, `delete (my|the|this)`, the which…most aggregate guard, M34's cross-page context window) were each falsified by real input at a shape their own authors had declared safe, most recently by chrome preceded by page-varying text — the owner's ruling is to stop betting on structure and ask whether the answer actually answers the question.
**Enforced by**: `judge-catches-varying-context-furniture`, `judge-fail-closed-on-error`, `judge-fail-closed-on-any-exception`, `judge-missing-key-fails-closed`, `judge-run-budget-enforced`, `judge-fast-suite-stub-boundary`, `judge-cache-hit-needs-no-key`, `judge-injection-cannot-flip-verdict`

---

## Context

`tasks/TODO.md` M36: ADR-016's own fix (M34, `not_page_furniture`) was refuted
by its own post-merge confirmation — `docs/support-matrix.md` D23/D24 — 6
wrong-answer-as-success in 9 deployed runs, zero clean correct answers, on a
task shape D24 had already named as an undemonstrated gap in the fix: chrome
that is byte-identical across pages but *preceded* by page-varying text (a
result count, a heading), so `not_page_furniture`'s 20-char window compare
never matches even though the value really is site chrome. That is the fourth
mechanism falsified by real input, the third falsified at a shape its own
authors had explicitly declared acceptable. The owner's decision, stated in
the milestone spec rather than left for this PR to infer: stop adding a fifth
regex/heuristic and ask an LLM the actual question.

## Decision

**Mechanism: the judge is the last rung, not a replacement for the ladder
below it.** `agent.py`'s runtime call to `verify()` (no ground truth — a live
run never has any) is unchanged; only when it returns `PASS` does
`_apply_judge` (agent.py) run, once, passing the task, the candidate answer,
and the evidence text already captured for `identity_anchors` — nothing new
is scraped for this. `verdict["checks"]` gains `judge_responsive` (the
judge's own certify/reject, when it ran) or `judge_available: false` (the
judge itself could not be reached), and a non-certify outcome flips the
verdict to `FAIL`, which `assemble_result`'s existing INV-2 rule
(`verdict != PASS` ⇒ `failure:semantic`) already turns into a non-success
status — no new status class, no change to that invariant.

**Injection boundary, same shape as the planner's.** `src/browser/judge.py`
mirrors `planner.py`'s `stub_planner`/`live_planner` split exactly:
`run_task` takes a required `judge` parameter (no default — every caller,
`cli.py`/`server.py`/the eval adapter, names `stub_judge(...)` or
`live_judge()` explicitly, so nothing can default to spending money), and the
`fast` suite's default (`_run_agent`'s own `stub_judge([True])`) keeps every
case written before M36 meaning exactly what it did.

**Prompt isolation.** `judge.py`'s `SYSTEM` message is the only channel that
carries instructions; the untrusted page evidence sits inside its own
`<<<EVIDENCE_START>>>`/`<<<EVIDENCE_END>>>` fence in the user message, and the
grading instruction comes AFTER that fence, not before — so the last thing the
model reads before it must answer is the app's own instruction, never
whatever the page said last. `judge-injection-cannot-flip-verdict` proves both
halves against the real `_prompt()` function: the payload never leaks into
`SYSTEM`, and a synthetic model with no defense against instruction recency is
fooled by a naive concatenation (watched red first) but not by the production
ordering.

**Fail closed, by construction, not by convention.** `_apply_judge` treats
every exit except a clean certify as FAIL: budget already spent
(`RUN_JUDGE_BUDGET = 1`, enforced in code before the call, not just declared),
any exception at all from the judge callable (not narrowed to `JudgeError`,
unlike `live_planner`'s deliberately narrow `PlanError` split — the judge has
no "model answered but wrongly" case to separate from "the call failed"), and
an explicit reject. Six cases exercise this from different angles: a genuine
L1-passing run whose judge stub raises (`judge-fail-closed-on-error`, through
the real pipeline), a bare non-`JudgeError` exception
(`judge-fail-closed-on-any-exception`), no `OPENROUTER_API_KEY`
(`judge-missing-key-fails-closed` — this environment genuinely has none, so
no mocking was needed), and the budget guard called twice directly
(`judge-run-budget-enforced`, since production never calls it twice on its
own).

**Cost.** `budgets_spent` gains `judge_calls`/`judge_tokens`/`judge_usd`
(`specs/001-browser-contract.md` updated, `contract-trace-schema` pins the
new keys); the runner's existing generic `sum_numeric` rollup picks them up
for free, and `evals/run.py` now prints a per-suite judge cost line and a
per-stage hit-rate line (L1-alone rejections vs. judge-reached vs.
certified/rejected/unavailable) — the number cost-discipline rule 1 asks be
recorded. Caching is content-hash keyed
(`task, answer, evidence, model, PROMPT_VERSION`) in `runs/judge_cache.json`
(already-gitignored), checked BEFORE the key check, so a cache hit answers
even with no live key present — proved directly against the real
`live_judge()` function by `judge-cache-hit-needs-no-key`. Model:
`deepseek/deepseek-v4-flash-0731`, ADR-010's own cheapest already
price-vetted cell (Decisions 5/6: every ablated candidate tied on
correctness, so cost decided) — the judge's job is a single grounded yes/no
over evidence already captured, not multi-step planning, so re-running the
ablation for it was not warranted; asserted at import time to stay inside
`planner.ABLATION_MODELS`, the same frozen snapshot ADR-010 pinned.

## What this PR could not verify

No `OPENROUTER_API_KEY` exists in this environment (a stated M36 constraint),
so the live judge's actual grading QUALITY — whether a real model, given this
prompt, reliably rejects "Warning!" and certifies £45.17 — is unverified here
and cannot be until the `full` suite runs against a deployed key. What IS
verified offline: the wiring (a reject flips the terminal status, an error
fails closed, the budget caps at one call, the fast suite spends nothing, the
cache serves without a key, the prompt structurally isolates evidence from
instruction). The deployed-build repeated-run confirmation this milestone's
acceptance criterion 5 needs — like M10's, M29's and M34's before it — has not
run; `ADR-015-a-freeze.md`'s criterion 5 stays RED until it does.
