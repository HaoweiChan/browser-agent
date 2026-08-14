# ADR-000: Eval-first scaffold instead of spec-driven development

Date: 2026-08-15 · Status: accepted

## Context

Standard SDD (OpenSpec / Spec Kit style) assumes requirements are ambiguous and
implementation is clear. The problems this template targets invert that:
requirements are explicit (e.g. split a 10-K into Items 1–16), but correctness
has no public ground truth. A prose spec like "Item 1A must be extracted
correctly" is unfalsifiable.

## Decision

The eval set is the spec. `specs/` holds only three artifact kinds:
executable invariants (000), per-task output contracts, and ADRs (why, not what).
Enforcement lives in hooks (PostToolUse invariant suite, pre-commit eval gate)
because hooks are the only layer that can actually block an agent — CLAUDE.md
is advice, hooks are law. Discipline mechanisms are hand-built on native Claude
Code primitives (skills/agents/hooks) rather than adopting OpenSpec/Superpowers/
BMAD/GSD: single-person short-cycle scope, and each mechanism must be
explainable line-by-line.

## Consequences

- Every feature starts by writing a failing eval case, not a spec section.
- Baseline moves are decisions and get recorded in ADRs.
- No tasks.md / plan files — session-native task tracking only, so no drift.
- Cost: no delta-spec audit trail; ADRs carry the "why" instead.

## ADR format for subsequent decisions

`ADR-NNN-<slug>.md`: Context (the fork in the road), Decision (one paragraph),
Consequences (what this buys and what it costs). Record judgment calls —
especially "what does correct mean here" rulings — not implementation detail.
