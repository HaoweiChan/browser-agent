# AI Coding Test

Eval-first workspace for the AI coding test (Task 2: SEC 10-K item-level
extraction; scaffold is task-agnostic and extends to Task 1).

## Status

Scaffold only — no task implementation yet. See `CLAUDE.md` for working rules.

## Setup

```bash
git config core.hooksPath .githooks   # enable the pre-commit eval gate
python3 -m evals.run --suite fast     # sanity: runner works (no cases yet)
```

No dependencies — the harness is stdlib-only. Task implementations declare
their own deps under `src/<task>/`.

## How this repo is built (methodology)

The eval set is the spec: correctness here has no public ground truth, so it
is encoded as executable invariants + golden/adversarial cases instead of
prose requirements (ADR-000). Four layers, no overlap:

| Layer | Mechanism | Role |
|---|---|---|
| Facts | `CLAUDE.md` | invariant project rules, < 150 lines |
| Knowledge | `.claude/skills/` | domain + process knowledge, loaded on demand |
| Execution | `.claude/agents/` | cold-reviewer / eval-adversary / spec-drift, fresh context |
| Enforcement | `.claude/hooks/` + `.githooks/` | invariant suite after every src edit; eval gate before every commit |

Loop per feature: failing eval case → implement under the invariant hook →
cold review → findings become adversarial cases → gate green → commit.
`prompts/` holds the AI-collaboration record, including where evals
contradicted assumptions.

(Sections to be filled as tasks land: how to run each task, frontend URL,
what works / what fails honestly, performance & cost analysis.)
