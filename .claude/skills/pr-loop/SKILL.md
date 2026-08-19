---
name: pr-loop
description: Orchestrated implement → verify → review → repair loop for one tasks/TODO.md task, ending in a PR that carries evidence, not chatter. Use when the user says /pr-loop <task-id>, "deliver T<N>", or asks to run a task through the full delivery loop.
---

# pr-loop — the delivery state machine

You are the **orchestrator**. You never write implementation code and never
review it yourself. You own state transitions, deterministic gates, and the
evidence ledger. The human's only two touchpoints are: invoking this skill,
and merging the PR.

```
SPEC → IMPLEMENT → GATE → REVIEW ─ findings → REPAIR → GATE → REVIEW …
                              └──── approve → EVIDENCE → HUMAN (merge)
```

Role separation is the verification architecture — do not collapse it:

| Role | Owns | May never |
|---|---|---|
| implementer (subagent, worktree) | implementation + tests | approve its own work |
| pr-reviewer (subagent, fresh context) | falsification, structured findings | edit code |
| eval suite | objective pass/fail | be skipped or mocked |
| orchestrator (you) | transitions, relay, ledger | implement or review |
| human | spec, disputes, merge | be needed mid-loop |

## States

### 1. SPEC
Read the task block from `tasks/TODO.md` (format below). If the spec lacks
acceptance criteria you can gate on, STOP and ask the human — that is a spec
problem, not something to improvise past.

### 2. IMPLEMENT
Spawn an **implementer subagent with worktree isolation** on branch
`task/<id>`. Its prompt must contain: the full task block, the repo's
per-feature loop (failing eval case first), and the instruction to commit its
work on the branch. It reports what it built and which new eval cases it added.

### 3. GATE (deterministic — you run it, never trust "I ran the tests")
On the task branch:
```bash
python3 -m evals.run --suite invariant   # must be 100%
python3 -m evals.run --suite fast        # must be ≥ .eval-baseline.json
```
Fail → back to REPAIR with the raw output. Pass → first time through, push
the branch and `gh pr create` (body = task block + "evidence pack pending").
Then REVIEW.

### 4. REVIEW
Spawn the **pr-reviewer subagent** (fresh context, no author reasoning) on the
PR diff. It returns findings in this schema, nothing else:

```json
{"id": "R1", "severity": "HIGH|MEDIUM|LOW",
 "claim": "what is wrong, one sentence",
 "evidence": "file:line + the concrete input/state that triggers it",
 "repro": "command or case that demonstrates it",
 "acceptance": "what passing looks like after the fix"}
```

Post **one PR comment per round**: a table of the round's findings. That
comment is the audit record — no other reviewer chatter reaches the PR.

- Findings with severity HIGH or MEDIUM → REPAIR.
- Only LOW or none → reviewer states APPROVED → EVIDENCE.

### 5. REPAIR
Relay the findings verbatim to the implementer (same subagent via SendMessage
if alive, else a fresh one on the same worktree branch). Hard rule inherited
from CLAUDE.md: **every confirmed HIGH/MEDIUM finding becomes an adversarial
eval case before it is fixed** — watch it fail, then fix. A finding the
implementer rejects gets a one-line written reason; the reviewer sees it next
round. After the repair, post one implementer PR comment: per finding id —
fixed (with the eval case id) or rejected (with the reason). Then → GATE.

**Circuit breaker:** after 3 review rounds without approval, or any
implementer/reviewer deadlock on a finding, stop and hand the dispute to the
human with both positions stated. Do not loop forever.

### 6. EVIDENCE
Update the PR body to the evidence pack:

```markdown
## Evidence pack — <task-id>
**Gate**: invariant 12/12 · fast 44/44 (baseline 42) — run <date>
**Review**: N rounds · findings H/M/L: a/b/c · confirmed x · rejected y (reasons inline above)
**New eval cases**: <ids added this task>
**Verification**: <the one command a human can run to see it work>
```

Append one line to `evals/report/pr-loop-ledger.jsonl` (the workflow's own
eval — commit it with the branch):

```json
{"task":"T10","date":"YYYY-MM-DD","rounds":2,"findings":{"HIGH":1,"MEDIUM":2,"LOW":1},"confirmed":3,"rejected":1,"gate_failures":1,"human_interventions":0}
```

Notify the human: task id, PR link, one-line summary. **You do not merge.**

## PR comment identity

Every PR comment is posted by the same `gh` account, so the first line of each
comment MUST declare the role — this is how the human tracks who said what:

```
**pr-loop/reviewer — round <N>**      findings table
**pr-loop/implementer — round <N>**   per-finding: fixed (case id) / rejected (reason)
**pr-loop/orchestrator**              evidence pack, gate failures, circuit-breaker escalation
```

One comment per role per round, always tagged, no untagged comments.

## tasks/TODO.md task format

```markdown
## T10 — <title>            [status: todo|in-progress|pr|done]
Spec: what and why, 2-5 lines.
Acceptance: gateable criteria — eval cases, invariants, or a runnable check.
Out of scope: (optional)
```

Update the task's `status` field at each transition (in-progress at IMPLEMENT,
pr at EVIDENCE, done only after human merge).
