# Support matrix — Task 1

**Report-assisted, human-declared** (see `docs/evals/evaluation-methodology.md`):
the latest `full`-suite eval report suggests a status; a human declares the
final status with a reason; README and the frontend render this same data.
A pass-rate does not threshold itself into "supported" — declaring is an
engineering-judgment act, and the reason column is the graded honesty evidence.

Entry shape (also served as JSON to the frontend):

```json
{
  "domain": "wikipedia.org",
  "task_type": "TC2 search-then-extract",
  "eval": "7/8",
  "declared_status": "unreliable",
  "reason": "Disambiguation pages still misroute the extraction step (case tc2-wiki-004)."
}
```

## Current matrix

No eval runs exist yet — this table is intentionally empty until M2 produces
the first baseline report. Empty cells are shown, not hidden.

| Domain | TC1 | TC2 | TC3 | TC4 | TC5 |
|--------|-----|-----|-----|-----|-----|
| shop fixture | — | — | — | — | — |
| forms fixture | — | — | — | — | — |
| wikipedia.org | — | — | — | — | — |

Statuses: `supported` / `unreliable` / `unsupported` / `—` (not yet evaluated).
Unsupported and unreliable rows must cite a concrete failing case id.
