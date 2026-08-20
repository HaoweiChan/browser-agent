# Project working rules

Eval-first repo, built on **groundwork**. Tasks live under `src/<task>/`.
**The eval set IS the spec.** groundwork targets problems where requirements
are clear but correctness is hard to define up front — so correctness is encoded
as executable invariants and metrics, not prose. Architecture rationale lives in
README.md; this file is the working contract.

## Toolchain

- **ponytail** plugin is enabled repo-wide via `.claude/settings.json` — laziest
  working solution, stdlib first, shortest diff. Applies to all code here.
- **graphify** is vendored as a project skill — use `/graphify` for architecture
  and file-relationship questions; once `graphify-out/` exists, treat such
  questions as graphify queries first.

## Layout

```
.claude/skills/    domain + process knowledge, loaded on demand
.claude/agents/    cold-reviewer / eval-adversary / spec-drift subagents
.claude/hooks/     enforcement — the only layer that can actually block
.githooks/         pre-commit eval gate (installed via core.hooksPath)
specs/             ONLY: 000-invariants.md, per-task contracts, decisions/ADR-*.md
docs/              planning package: product/ specs/ architecture/ evals/ plans/ + support-matrix.md, analysis.md (ADR-001)
tasks/TODO.md      milestone-level tracker only — micro-tasks stay in-session (ADR-001)
evals/golden/      hand-labeled cases (JSON, one per case)
evals/adversarial/ cases known or designed to break the pipeline
evals/labels/      frozen raw evidence + hand labels for accuracy sampling (JSONL)
evals/report/      every run's output, committed to git
prompts/           AI-collaboration record (curated 00N-*.md)
src/<task>/        implementation + eval_adapter.py per task
graphify-out/      knowledge graph — graph.html / graph.json / GRAPH_REPORT.md +
                   cost.json / manifest.json tracked, cache/ ignored; /graphify --update
```

## Gate

The objective pass/fail for this repo. pr-loop, the hooks, and any reviewer
run exactly these, in order:

```bash
python3 -m evals.run --suite invariant   # pass: 100%
python3 -m evals.run --suite fast        # pass: score >= .eval-baseline.json
```

## Commands

```bash
python3 -m evals.run --suite invariant         # must-always-hold, pure code, no LLM/network
python3 -m evals.run --suite fast              # offline gate: fixtures + LLM stubs, zero paid calls
python3 -m evals.run --suite live              # real sites, hand-written plans — network, still $0.00
python3 -m evals.run --suite full              # live sites + real LLM — manual/scheduled only
python3 -m evals.run --suite all               # every case regardless of tags
python3 -m evals.run --suite fast --update-baseline   # deliberate baseline move
```

Suite names are case tags (`"suites": [...]`); `all` is the only selection-special
CLI value, and `invariant` additionally gates at 100% regardless of baseline.
`live` and `full` are separate tags on purpose: `live` is every case that needs
the network, `full` adds the ones that also spend LLM tokens, so `--suite live`
exercises real sites at $0.00 while the paid cases stay behind `full`.

## Hard rules

1. **Never edit `.eval-baseline.json` by hand** and never `--update-baseline` just to
   make the pre-commit gate pass. A baseline move is a decision — record why in an ADR.
2. **Every new failure becomes a case** in `evals/adversarial/` before it is fixed.
   Watch the new case fail first; an eval you've never seen red proves nothing.
3. **specs/ holds only three kinds of files**: invariants, output contracts, ADRs.
   Prose planning lives in `docs/`; the only task file is milestone-level
   `tasks/TODO.md` (ADR-001). Micro-task lists stay in the session.
4. **No mocked results.** If a live dependency is unreachable, fail loudly; never
   fabricate output to make a run look green.
5. Commits go through the pre-commit eval gate. `--no-verify` is for emergencies
   and must be explained in the commit message.
6. **No site-specific knowledge in the execution policy.** Production agent code
   contains no site-specific selectors, DOM paths, or navigation recipes.
   Eval/fixture code may use them strictly for ground-truth verification and
   fault injection, and must never feed them to the executor. Allowed per-site
   data anywhere: start URL, rate limit, ground-truth API endpoint.
7. **Commits are consolidated milestones, not save-points.** Reviewers read the
   history. Batch related work, verify it (suites + a self-review pass), THEN
   commit once. No rapid fixup chains — a "fix X" commit minutes after X is a
   review failure, not progress.
8. **Secrets are environment variables only** — Zeabur service settings in prod,
   shell env locally. No .env files, no secrets in code or history (pre-commit
   guard enforces the OpenRouter pattern).

## Per-feature loop

1. Plan mode → ADR + new invariant/eval cases (eval first)
2. Watch the new cases fail
3. Implement (PostToolUse hook keeps running the invariant suite)
4. `cold-reviewer` subagent cold-reads → its findings become adversarial cases
5. New cases into the eval set → back to 3
6. Eval gate green → commit

For a full tasks/TODO.md task that should end in a PR, run the loop through
**/pr-loop <task-id>** instead: one orchestrator session drives
implement → gate → review → repair with subagents (implementer in a worktree,
pr-reviewer with fresh context); the human only writes the spec and merges.
The PR carries role-tagged structured findings and an evidence pack — never
agent chatter. Protocol: the groundwork plugin's `pr-loop` skill (see `.groundwork-version` for the pinned upstream).

## Adding a task

1. `src/<task>/` with an `eval_adapter.py` exposing `run_case(case) -> {"passed": bool, ...}`
2. A domain-knowledge skill in `.claude/skills/<task>-domain/`
3. A contract spec `specs/0NN-<task>-contract.md`
4. Golden + adversarial cases tagged with `"task": "<task>"`
