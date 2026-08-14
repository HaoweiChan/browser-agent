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
- Enforced by: (pending — first task-specific case must cover this)

---

Task-specific invariants live below a `## <task>` heading as tasks are added.
