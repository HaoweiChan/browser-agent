# browser-agent

Generalized browser automation agent — accepts natural-language task
descriptions and executes them reliably across sites, with self-correction
(diagnose failures, switch strategies) and self-maintenance (detect UI /
selector drift and adapt locators).

Built on [groundwork](https://github.com/HaoweiChan/groundwork), an eval-first
scaffold: reliability here has no ground truth, so it is encoded as executable
invariants and golden/adversarial cases instead of prose specs.

## Status

Repo scaffolded from the template — no implementation yet. Next steps per the
groundwork loop: `specs/001-browser-agent-contract.md`, task invariants in
`specs/000`, a domain skill, and the first red eval cases before any code.

---

## The template underneath

**An eval-first project scaffold for the agent era.**

Most of the code in a groundwork project will be written, reviewed, and
maintained by AI agents. What survives agent handoffs is not tribal knowledge
or session memory — it is architecture, executable checks, and enforcement.
groundwork is the ground those agents stand on: for problems with no public
ground truth (extraction, agents, pipelines, anything where "correct" is a
judgment call), you lay your own ground — the eval set.

## The idea

Prose specs like "the output must be correct" are unfalsifiable, and an agent
told "please be careful" will drift. groundwork replaces both:

- **The eval set IS the spec.** Correctness lives in executable invariants and
  golden/adversarial cases, not in requirement documents. If a property isn't
  backed by a case that can go red, it doesn't exist.
- **Advice doesn't bind agents; enforcement does.** CLAUDE.md is advice. Hooks
  are law. Anything that must never happen is enforced by a hook that blocks,
  not a sentence that asks.

## Architecture — four layers, no overlap

Each layer answers one question. Nothing appears in two layers.

| Layer | Lives in | Answers | Binding? |
|---|---|---|---|
| **Facts** | `CLAUDE.md` | What is invariantly true here? (structure, commands, hard rules) | advisory |
| **Knowledge** | `.claude/skills/` | How do we do X well? (loaded on demand, zero resident context) | advisory |
| **Execution** | `.claude/agents/` | Who checks the work? (fresh-context subagents, no author bias) | advisory |
| **Enforcement** | `.claude/hooks/` + `.githooks/` | What can never happen? | **blocking** |

The common failure mode this prevents: writing enforcement-layer intent
("never commit a regression") into the facts layer, where it is a polite
suggestion an agent can talk itself past.

### The enforcement loop in practice

- Every `src/` edit → PostToolUse hook runs the **invariant suite** (absolute,
  100% required). A failure is fed straight back to the editing agent as an
  error it must fix — no human in the loop.
- Every commit → pre-commit hook runs the **fast suite** against
  `.eval-baseline.json`. A score below baseline blocks the commit. The
  baseline moves only by explicit decision, recorded in an ADR.
- Every session end → the session's prompts are dumped to `prompts/raw/`,
  so the AI-collaboration record builds itself.

### The execution layer in practice

Three standing subagents, all evidence-only (they may not fix anything):

- `cold-reviewer` — cold-reads new code without the author's reasoning; its
  deliverable is the three most likely *silent* failure inputs.
- `eval-adversary` — attacks the gaps in the eval set with real-world inputs;
  its findings become adversarial cases verbatim.
- `spec-drift` — audits gaps between what the repo says (invariants, contracts,
  ADRs, docs) and what the code does; flags decorative invariants first.

## Repo map

```
CLAUDE.md            facts layer — working rules, < 150 lines (AGENTS.md symlinks here)
.claude/settings.json  hooks registration + plugin wiring (ponytail auto-installs)
.claude/skills/      eval-protocol · failure-triage · cost-discipline · graphify (vendored)
.claude/agents/      cold-reviewer · eval-adversary · spec-drift
.claude/hooks/       post-edit invariant runner · session prompt logger
.githooks/           pre-commit eval gate
specs/               ONLY three kinds: invariants · output contracts · ADRs (why, not what)
evals/run.py         stdlib-only runner — defines the case + adapter contract
evals/golden/        hand-verified cases (provenance recorded per case)
evals/adversarial/   inputs that broke, or are designed to break, the pipeline
evals/report/        every run's scored output, committed — the progress narrative
prompts/             AI-collaboration record: auto-dumped raw/ + curated correction chains
src/<task>/          implementations — each exposes eval_adapter.py to the runner
```

## Using this template

```bash
git clone <this-repo> my-project && cd my-project
git config core.hooksPath .githooks   # enable the pre-commit eval gate
python3 -m evals.run --suite fast     # sanity: runner works (no cases yet)
```

Opening the repo in Claude Code auto-prompts to install the **ponytail** plugin
(lazy-first coding discipline); **graphify** (codebase knowledge graphs) is
vendored as a project skill. The harness itself is Python-stdlib-only; tasks
declare their own dependencies under `src/<task>/`.

To add a task: `src/<task>/eval_adapter.py` exposing
`run_case(case) -> {"passed": bool, ...}`, a domain skill, a contract spec,
and cases tagged `"task": "<task>"`. Details in `CLAUDE.md`.

Projects that outgrow the eval harness can delete `evals/` — every hook
degrades gracefully to a no-op.

## If you are an agent entering this repo

1. Read `CLAUDE.md` in full — it is short on purpose.
2. Run `python3 -m evals.run --suite fast` to see the current ground state.
3. Before changing behavior: write the failing case first, watch it fail.
4. Before claiming done: fast suite ≥ baseline, invariant suite at 100%.
5. When you hit a judgment call about what "correct" means — that is an ADR,
   not a code comment. Write it down in `specs/decisions/`.

## Per-feature loop

```
failing eval case → implement (invariant hook watching) → cold review
→ findings become adversarial cases → eval gate green → commit
```

Design rationale for the whole approach: `specs/decisions/ADR-000`.
