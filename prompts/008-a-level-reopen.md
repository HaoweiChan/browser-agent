# 008 — Reopening after the freeze: the A-level directive

**Date**: 2026-08-17 · **Milestone**: A-phase planning (pre-M6) · **Outcome**:
Task 1 reopened by owner decision; TODO restructured with milestones M6–M10;
`docs/plans/active/task1-a-level-plan.md` created; **no implementation** —
planning documents only.

## Context

M5 froze Task 1 at B-level per the freeze rule: 5 of 6 B-floor criteria met,
criterion 2 (live breadth) partial, held-out probe at 2/8 correct answers. The
recorded next step was "STOP, start Task 2". The owner instead issued a
reopen directive.

## The prompt (condensed, translated from Chinese)

1. B-baseline is treated as **passed**.
2. The repo must **not go public yet** — A-level comes before submission.
3. Locate where the A-level continuation tasks actually live in the repo.
4. Confirm the roadmap, then update `tasks/TODO.md` so work can continue.
5. **Scope restriction: tasks/planning files only — implementation is
   explicitly forbidden at this step.**
6. Record this instruction in `prompts/`, in English, structured.

## Where the A-level tasks were found

Scattered across three places, none of them a roadmap:

- `tasks/TODO.md` M6 — a single "post-freeze A-backlog" row holding nine items
  in one cell, ranked once at M5 and never revisited.
- `docs/plans/completed/task1-b-level-plan.md` — the SHOULD (B-strong) and
  BACKLOG scope registries.
- `docs/product/assignment-requirements.md` §E5 — the rubric definition of
  A-level markers (layered tradeoffs, honest failure modes, collaboration
  quality).

## The resulting decision

Consolidated into five milestone rows (M6–M10) in `tasks/TODO.md`, with the
detailed scope registry, A-exit criteria, and hour guard in a new
`docs/plans/active/task1-a-level-plan.md` (mirroring the B-plan's structure).
Ranking is by reviewer-value ÷ effort **anchored to what the freeze actually
measured**, not the backlog's original order:

- **M6 Live breadth & depth** first — it closes the only partial B-floor
  criterion, and the probe showed live capability is the thinnest evidence.
- **M7 Verifier accuracy** second — precision/recall has never been measured,
  and the probe exposed that answer-responsiveness held by luck once.
- **M8 mutation/hostility**, **M9 cost/model ablation**, **M10 A-Freeze** with
  a second held-out probe as the mandatory gate.
- Demoted to backlog: the verifier-accuracy *dashboard UI* (the numbers are
  MUST; the UI is not), adaptive locator learning, parallel eval runner,
  visual fallback.

The freeze rule is superseded by recorded owner instruction, not silently
deleted: the B-freeze record in TODO stands, a dated Reopen note sits under
it, and the A-phase gets its own hour guard (+12h default) so the reopen
stays bounded.

## AI recommendation: accepted / rejected / modified

Accepted with one deliberate reframe: the backlog's M5-era ordering was **not**
carried over as-is. The freeze produced data (criterion 2 partial, probe 2/8,
the responsiveness near-miss) that re-ranks the backlog; the roadmap follows
the data. The AI also kept the hour-guard discipline alive by giving the
A-phase its own guard rather than treating the reopen as open-ended.

## Assumption → Contradiction → Correction

- Assumed (by the plan on file): freeze ⇒ start Task 2 immediately; the only
  legitimate way back into Task 1 was a held-out-probe regression or a
  deliverable-claim fix.
  Owner said (a decision, not an eval): B-baseline accepted, go for A-level
  first, stay private until then.
  Corrected: dated Reopen note in `tasks/TODO.md` supersedes the freeze rule
  by recorded instruction; the A-phase carries its own guard and freeze line
  (`docs/plans/active/task1-a-level-plan.md`) so the override doesn't become
  the precedent that guards are optional.

- Assumed (by the M6 backlog row): the A-backlog ranking made at M5 was still
  the roadmap.
  The freeze data said: live breadth is the one partial criterion, the probe
  scored 2/8, and verifier responsiveness was never actually checked — none of
  which the original ranking could have priced in.
  Corrected: M6/M7 promoted to the top on measured gaps; the dashboard UI
  demoted to backlog because only its *numbers* buy rubric evidence.
