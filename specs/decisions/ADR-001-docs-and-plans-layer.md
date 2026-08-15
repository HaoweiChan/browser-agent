# ADR-001: Allow a docs/ planning layer and a milestone-level TODO

Date: 2026-08-15
Status: accepted

## Context

ADR-000 banned tasks.md and plan files: task lists live in the session, so they
cannot drift. That rule assumed the only consumers of planning artifacts are the
agents working in this repo. The Whaleforce assignment breaks that assumption:
reviewers read the repository itself, grade planning quality, eval design depth,
and honest tradeoff analysis, and the planning package is therefore a deliverable
— not internal exhaust. The fork: keep ADR-000 pure and put planning prose
nowhere reviewers can find it, or amend the rule and accept a second prose layer
that spec-drift must watch.

## Decision

Amend ADR-000. A `docs/` tree (product/, specs/, architecture/, evals/, plans/,
plus cross-cutting top-level files such as support-matrix.md and, at M5,
analysis.md) holds prose planning artifacts, and `tasks/TODO.md` exists at
**milestone level only** — micro-tasks still live in the session. `specs/` keeps its three-kind
charter (invariants, output contracts, ADRs) unchanged. Plans that finish move
to `docs/plans/completed/` and are exempt from spec-drift audit: a completed plan
is a historical record, not a living spec. The prompts convention switches from
date-topic to reviewer-ordered numbering (`prompts/00N-<topic>.md`), keeping the
correction-chain requirement.

## Consequences

Buys: reviewer-legible planning evidence (a graded criterion), and a single
place where scope decisions (MUST/SHOULD/BACKLOG) are recorded. Costs: a second
prose layer that can drift from reality — mitigated by the completed/-exemption
rule and by keeping `docs/plans/active/` to exactly one live plan. The
no-micro-task rule survives: if TODO.md grows entries smaller than a milestone,
that is drift and spec-drift should flag it.
