# 000 — Invariants

Properties that must ALWAYS hold, across every task in this repo.
**An invariant listed here without a backing eval case (tagged
`"suites": ["invariant"]`) is decorative and counts as drift** — the
`spec-drift` agent flags it.

Format per invariant:

```
## INV-<n>: <one-line property>
- Rationale: why this must never break
- Enforced by: evals/<...>.json (case id)
```

## INV-0: The pipeline never reports success with empty output
- Rationale: silent failure is the #1 graded failure mode; an empty result
  must surface as an explicit failure/low-confidence signal, never a green run.
- Enforced by: evals/adversarial/inv0-no-empty-success.json (inv0-no-empty-success)
  — guard lives in `src/browser/agent.py::assemble_result`; the case was proven
  red by disabling the guard before it was trusted green.

## INV-1: Every non-success status carries exactly one failure class
- Rationale: the taxonomy is only useful if a run maps to one cell of it. A
  status carrying two classes (or none) makes diagnosis accuracy, recovery
  rate and the failure distribution unmeasurable — and hides which mechanism
  was supposed to fire.
- Enforced by: evals/adversarial/inv1-one-failure-class.json (inv1-one-failure-class)
  — guard lives in `src/browser/agent.py::assemble_result`; proven red by making
  it emit `failure:<class>,act` before the case was trusted green.

## INV-2: The verifier outranks the executor
- Rationale: silent failure is prevented structurally, not behaviorally.
  Reaching the last step is not what makes a run successful — a non-PASS
  OutcomeVerifier verdict can never be reported as `success`, whatever the
  executor believes about its own work.
- Enforced by: evals/adversarial/inv2-verifier-outranks-executor.json
  (inv2-verifier-outranks-executor) — guard lives in
  `src/browser/agent.py::assemble_result`; proven red by deleting the verdict
  branch and watching the case fail.

## INV-3: Budget exhaustion is a loud classified failure, never a quiet stop
- Rationale: recovery ladders make a run able to spend more than it planned to.
  A bounded loop that gives up quietly is indistinguishable from one that
  finished, and it would let a run end with no answer and no failure class —
  which is INV-0 and INV-1 defeated through the side door. Every budget
  (actions, tokens, replans per task, relocation rungs per step) ends the run
  with a class and the complete trace of what was tried.
- Enforced by: evals/adversarial/inv3-budget-exhaustion-loud.json
  (inv3-budget-exhaustion-loud) — guard lives in `src/browser/agent.py::budget_stop`
  and the ladder branches in `run_task`; proven red before `budget_stop` existed,
  when a replan loop ran until the action budget tripped and reported
  `failure:env` — the wrong class for a run that died of an unfixable `act`.
  The end-to-end half is `evals/adversarial/budget-replans-exhausted.json`.

---

Task-specific invariants live below a `## <task>` heading as tasks are added.
