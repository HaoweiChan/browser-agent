# 001 — Project planning: Task 1 scoped, reviewed, compressed

**Date**: 2026-08-15 · **Phase**: planning only, no production code ·
**Outputs**: the `docs/` planning package, ADR-001, `tasks/TODO.md`,
two skills, agent charter amendments.

## Context

Fresh groundwork scaffold; both assignment files read (EN/ZH — verified
identical in substance). Goal of the session: turn Task 1 into a testable
engineering project with explicit scope, eval methodology, failure taxonomy,
architecture decision, and a freeze line — before writing any product code.

## The prompt (condensed)

Act as lead engineer/planner. Extract the real requirement matrix from the
assignment. Define the problem operationally (taxonomy over demo-site list).
Design evaluation BEFORE architecture, including ground truth and an auditor
that never lets the executor grade itself. Define self-correction beyond
try/except and self-maintenance under controlled UI mutation. Propose ≥2
architectures with tradeoffs. Plan subagents/skills without persona inflation.
Define a B-level stopping point. Run an adversarial review pass. Do not
manufacture git history. Flag conflicts between this prompt and the repo's own
rules.

## Decisions that came out

Recorded in the planning package; headline ones: architecture B (deterministic
execution + LLM evolving-prefix planning) · layered OutcomeVerifier with
identity anchors · recovery metric excludes retries by construction · committed
tier-breaking mutation catalog as self-maintenance ground truth · coverage
cells over case counts · thresholds deferred to post-baseline ADR-002 ·
OpenRouter for LLM access · Task 2 in a separate repo · 20–24h hour guard.

One prompt/repo conflict surfaced and resolved by ADR-001: the repo banned
plan/task files; the assignment grades planning artifacts, so a bounded `docs/`
+ milestone-TODO layer was carved out.

## Review pass 1 — adversarial Plan-agent review (15 objections)

The first full draft was reviewed by an independent planning agent instructed
to refute, not rubber-stamp. Accepted (headline items): deploy spike moved to
M1 (blocker — public URL is the hardest dependency) · spend/URL guards pulled
into B-scope (blocker — public endpoint + API key during grading week) ·
identity anchors added (the wrong-but-self-consistent extraction slipped all
three verifier layers as drafted) · traps demoted to a *floor* of verifier
accuracy · the "bounded observe-act burst" escape hatch replaced by
replan-as-normal-loop (the hatch would have quietly turned the majority path
into LLM-per-step) · trace schema specced before executor code · performance
thresholds deferred post-baseline · knowledge-placement rule extended over
evals/config · 7 failure classes instead of ~17 · per-axis coverage arithmetic.

## Review pass 2 — human/GPT scope rejection

**The human reviewer rejected the plan** (with a second-model critique):
planning sophistication exceeded what the assignment needs. Specific calls:
the drafted "B-level" was actually A-minus and conflicted with the strategy of
finishing both tasks; ≥45 cases was a count fetish (coverage cells matter, not
raw counts); per-site tier counters were "dynamic for dynamism's sake"; abuse
infrastructure exceeded reviewer ROI; pre-building recovery ladders for all 7
classes was classification-first design. Directives: OpenRouter instead of
direct Anthropic API; hard 2–3-day budget; MUST/SHOULD/BACKLOG on everything;
every MUST names its rubric cell.

All accepted. The plan was rewritten: B-floor/B-strong split, evidence-budget
column, minimal Step schema, ladders only for baseline-observed failure
families, milestones re-cut to M0–M5 + STOP.

## Review pass 3 — approve with five fixes

Second human/GPT pass approved the compressed plan (verdict: further planning
optimization now has worse ROI than starting) with five refinements, all
accepted: recovery families "up to 3, minimum 2" — never quota-filling · the
selector ban rescoped to the production execution policy (eval/fixture code may
use selectors for ground truth and fault injection, never fed to the executor —
the blanket ban would have made cold-reviewer fight normal test code) ·
L3-difficulty (ambiguity) demoted to SHOULD · support matrix made
report-assisted + human-declared rather than threshold-generated · the verifier
model decoupled from the planner default (deterministic verification is the
default; LLM verdicts are weak independent evidence). Added: a committed scope
checkpoint between M2 baseline and M3, the 20–24h hour guard, and the Task 2
separate-repo decision with an honest-bootstrap note.

## Assumption → Eval contradiction → Correction

(Eval contradictions in this planning phase are review findings; runtime eval
chains start at M1.)

- Assumed: an upfront typed plan with a bounded "observe-act burst" escape
  hatch keeps architecture B honest.
  Review said: the hatch is an unspecified trapdoor — most interesting TC2/TC3
  tasks route through it, making the majority path architecture A in disguise.
  Corrected: replan-on-invalidated-postcondition is the *normal* loop; replan
  rate is a tracked metric with an honesty clause in the ADR.
- Assumed: a trap set measures verifier accuracy.
  Review said: traps sample imaginable wrongness; correlated planner/verifier
  errors are by construction the ones the model family doesn't notice.
  Corrected: traps reported as a floor; hand-labeled verdict sample is the
  estimate; limitation stated in the analysis.
- Assumed: a thorough B definition (≥45 cases, all levels, full mutation
  catalog, auditor sample) is the safe target.
  Human said: that's A-minus wearing a B label, and it eats the time reserved
  for Task 2.
  Corrected: B-floor/B-strong split, coverage cells, hour guard, freeze rule.
- Assumed: banning site-specific selectors everywhere makes generalization
  greppable.
  Review said: fixtures must know their own DOM; the blanket ban makes the
  reviewer fight ground-truth code.
  Corrected: ban scoped to the execution policy; eval/fixture selectors allowed
  for verification and fault injection, never fed to the executor.
- Assumed: 5 milestones of pre-designed recovery ladders demonstrate
  self-correction depth.
  Human said: build ladders for failures you've measured, not imagined.
  Corrected: M2 baseline → committed scope checkpoint → ladders for observed
  top families (≤3, ≥2 distinct).
- Assumed: the M0 suite-naming fix was complete once CLAUDE.md and the
  methodology agreed.
  Drift audit said (spec-drift run, post-package): eval-protocol and
  cost-discipline skills still carried the old `full`-suite semantics; the
  contract filename `001-browser-agent-contract.md` broke both the
  `0NN-<task>-contract.md` convention and the runner's Python import path;
  INV-0's backing case had no milestone owner. (One audit finding — a missing
  AGENTS.md symlink — was a false positive; the symlink exists.)
  Corrected: both skills updated, task id fixed to `browser` with contract
  `specs/001-browser-contract.md`, INV-0's backing case assigned to M1,
  ADR-000 gained an amended-by marker, eval-adversary gained a probe
  blindness protocol.

## Why this record exists

The correction chain above — initial proposal → adversarial review → scope
problem identified → human rejection → compression → approval — is the AI
collaboration evidence the assignment says it will read. The final plan is
`docs/plans/active/task1-b-level-plan.md`.
