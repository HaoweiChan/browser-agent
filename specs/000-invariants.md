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

---

Task-specific invariants live below a `## <task>` heading as tasks are added.
