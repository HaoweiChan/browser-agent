# AI Coding Test — working rules

Eval-first repo for the Whaleforce AI coding test. Tasks live under `src/<task>/`.
**The eval set IS the spec.** Requirements here are clear; correctness is not
definable up front — so we encode it as executable invariants and metrics, not prose.

## Layout

```
.claude/skills/    domain + process knowledge, loaded on demand
.claude/agents/    cold-reviewer / eval-adversary / spec-drift subagents
.claude/hooks/     enforcement — the only layer that can actually block
.githooks/         pre-commit eval gate (installed via core.hooksPath)
specs/             ONLY: 000-invariants.md, per-task contracts, decisions/ADR-*.md
evals/golden/      hand-labeled cases (JSON, one per case)
evals/adversarial/ cases known or designed to break the pipeline
evals/report/      every run's output, committed to git
prompts/           AI-collaboration record (auto-dumped raw/ + curated files)
src/<task>/        implementation + eval_adapter.py per task
```

## Commands

```bash
python3 -m evals.run --suite fast              # quick gate suite
python3 -m evals.run --suite invariant         # must-always-hold assertions
python3 -m evals.run --suite all               # everything, writes report
python3 -m evals.run --suite fast --update-baseline   # deliberate baseline move
```

## Hard rules

1. **Never edit `.eval-baseline.json` by hand** and never `--update-baseline` just to
   make the pre-commit gate pass. A baseline move is a decision — record why in an ADR.
2. **Every new failure becomes a case** in `evals/adversarial/` before it is fixed.
   Watch the new case fail first; an eval you've never seen red proves nothing.
3. **specs/ holds only three kinds of files**: invariants, output contracts, ADRs.
   No tasks.md, no plans — task lists live in the session, not in files.
4. **No mocked results.** If a live dependency is unreachable, fail loudly; never
   fabricate output to make a run look green.
5. Commits go through the pre-commit eval gate. `--no-verify` is for emergencies
   and must be explained in the commit message.

## Per-feature loop

1. Plan mode → ADR + new invariant/eval cases (eval first)
2. Watch the new cases fail
3. Implement (PostToolUse hook keeps running the invariant suite)
4. `cold-reviewer` subagent cold-reads → its findings become adversarial cases
5. New cases into the eval set → back to 3
6. Eval gate green → commit

## Adding a task

1. `src/<task>/` with an `eval_adapter.py` exposing `run_case(case) -> {"passed": bool, ...}`
2. A domain-knowledge skill in `.claude/skills/<task>-domain/`
3. A contract spec `specs/0NN-<task>-contract.md`
4. Golden + adversarial cases tagged with `"task": "<task>"`
