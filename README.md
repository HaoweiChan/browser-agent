# project-template

Eval-first project template for problems where requirements are clear but
correctness is hard to define (extraction, agents, anything without public
ground truth). Built on native Claude Code primitives — no SDD framework.

## Using this template

```bash
git clone <this-repo> my-project && cd my-project
git config core.hooksPath .githooks   # enable the pre-commit eval gate
python3 -m evals.run --suite fast     # sanity: runner works (no cases yet)
```

Opening the repo in Claude Code auto-prompts to install the **ponytail**
plugin (`.claude/settings.json` → `extraKnownMarketplaces` + `enabledPlugins`);
**graphify** is vendored as a project skill, no install needed.

The harness is stdlib-only. Task implementations declare their own deps under
`src/<task>/`. To add a task, follow "Adding a task" in `CLAUDE.md`.

## Methodology

The eval set is the spec: correctness is encoded as executable invariants +
golden/adversarial cases instead of prose requirements (ADR-000). Four layers,
no overlap:

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
