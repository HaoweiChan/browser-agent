# Project working rules

Eval-first repo. Tasks live under `src/<task>/`.
**The eval set IS the spec.** This repo targets problems where requirements
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
docs/              planning package: product/ architecture/ evals/ plans/ + support-matrix.md, analysis.md (ADR-001)
backlog/           Backlog.md task store — one file per task, drafts/ = debt; `backlog task list --ready --plain` (groundwork GW-017)
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
python3 -m evals.run --suite invariant   # pass: 100%, wall clock <= the ceiling evals/run.py enforces
python3 -m evals.run --suite fast        # pass: score >= .eval-baseline.json, wall clock <= the ceiling evals/run.py enforces
```

The ceilings themselves are per (suite, environment) and live in `WALL_BUDGET_S`
(`evals/run.py`) and `.github/workflows/eval.yml` — not here. They are measured,
not chosen (ADR-013's rule, ADR-019 as amended by ADR-021), so they move; a
number re-typed into this file is a number nothing reads back.

## Commands

```bash
python3 -m evals.run --suite invariant         # must-always-hold: pure-code probes plus the fixture runs that pin them (loopback only, no LLM, no live site) — 100%, and a ceiling of its own
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
   Prose planning lives in `docs/`; task state lives only in Backlog.md
   (`backlog/`; ADR-001 amended by groundwork GW-017). Micro-task lists stay in
   the session.
4. **No mocked results.** If a live dependency is unreachable, fail loudly; never
   fabricate output to make a run look green.
5. Commits go through the pre-commit eval gate. `--no-verify` is for emergencies
   and must be explained in the commit message.
   Commit subjects and PR titles share one shape: `<type>(<scope>)?: <lowercase
   summary>` (feat, fix, docs, chore, refactor, test, perf, ci, build, revert);
   `.githooks/commit-msg` and `.github/pr_check.py` enforce it, and PR bodies
   follow `.github/PULL_REQUEST_TEMPLATE.md`.
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

For a full Backlog.md task that should end in a PR, run the loop through
**/pr-loop <task-id>** (Claude Code) or **$pr-loop <task-id>** (Codex): one
orchestrator session drives implement → gate → probe → one independent
verification → one repair → one delta verification, with the roles kept apart
(implementer in a worktree, verifier with fresh context, never more than two
model calls). A finding blocks only with a reproduction and only for unmet
acceptance, drift from the task, or wrong output; prose never blocks. What is
still open after the second call goes to the human as `Decision: not met`.
Debt is one `backlog task create --draft` line naming a case or run id. The PR
carries the six-section body `.github/pr_check.py` enforces. One pr-loop
session per repo at a time. Protocol: the `pr-loop` plugin skill (groundwork
GW-017).

## Adding a task

1. `src/<task>/` with an `eval_adapter.py` exposing `run_case(case) -> {"passed": bool, ...}`
2. A domain-knowledge skill in `.claude/skills/<task>-domain/`
3. A contract spec `specs/0NN-<task>-contract.md`
4. Golden + adversarial cases tagged with `"task": "<task>"`
