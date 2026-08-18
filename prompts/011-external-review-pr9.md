# 011 — An outside reader on PR #9: best-effort ≠ bounded

**Date**: 2026-08-18 · **Milestone**: post-M6 nav fix (PR #9) · **Outcome**:
mergeable with no blocker; one finding upgraded from "documented" to "debt with
a named end state"; the sharpest lesson of the chain named more precisely than
either session had managed.

## Context

PR #9 had already been through a peer Claude session's review — three findings,
all taken, all pushed. The owner then ran the PR past an **external model
(GPT)** and relayed the result through that session. Two AI reviewers of the
same diff, from different vendors, is a data point this project has not had
before, so it is worth a record of its own rather than a line in the ADR.

## The prompt

Not a prompt to me — a review of my branch, relayed. What came back, in
substance:

- **Mergeable, no blocker.**
- **Endorsed** rejecting `networkidle` on a measurement rather than a
  preference (+34s on the fast suite, over the ADR-002 budget).
- **Called finding 3** — `except Exception: pass` swallowing crash/close
  alongside timeout — the most important code-quality finding of the three.
- **Singled out the screenshot discovery** as the sharpest lesson in the chain,
  and named it better than I had: **`try/except` bounds error propagation, not
  latency.** "Best-effort" describes what happens when the call *fails*; it
  says nothing about how long the call may *take*. An unbounded default inside
  a handler is a budget nobody chose.
- **Flagged the missing root `requirements.txt`** (deps live in
  `src/browser/requirements.txt`) as a small reproducibility cost. Both
  reviewer sessions hit it independently.
- **Rejected my resolution of finding 2**, while agreeing with the call
  underneath it.

## The resulting decision

The last point is the one that changed something. I had declined to route
`_run_observe_case` through the production `navigate()` helper and written the
trade-off at the call site. The external review agreed with the *decision* —
and put the reason better than either session had:

> production readiness asks "is this page usable enough to act on?", observe
> ground truth asks "what does a fully settled page expose?"

— but did not accept the comment as the end state. **Documenting a trap is not
the same as making the harness diagnosable.** The third option neither session
named: keep strict `load`, but give it an explicitly chosen eval budget (5–10s,
not Playwright's 30s default), catch `PlaywrightTimeoutError`, and return
`{"passed": false, "failure": "eval_env", ...}` instead of a traceback. Strict
ground truth preserved, no 30s wait, and a timeout that reads as "this fixture
is not a valid strict-observe subject" rather than "the observer broke".

Graded MEDIUM and deliberately **not** folded into #9: it is eval-harness
robustness with no production path and no case reaching it, and expanding a
navigation PR to cover eval infrastructure would blur a clean scope. Recorded
instead where this repo keeps declared-and-unfixed items — a `ponytail:`
comment at the call site naming the ceiling and the upgrade path, plus a
support-matrix row — because `specs/` takes only invariants, contracts and ADRs
and `tasks/TODO.md` is milestone-level (CLAUDE.md rule 3).

## AI recommendation: accepted / rejected / modified

Accepted, including the part that says my own fix was insufficient. Worth being
precise about what each reviewer was for, since this is the first time three of
us have read the same diff:

- The **peer session** found the three code issues by reading the diff and then
  *running* things — it measured the 30.4s raise rather than predicting it, and
  that measurement is what made finding 2 worth more than a footnote.
- The **external model** found no new defects. What it contributed was
  *framing*: the abstraction-leakage argument for why the two navigation
  semantics must stay separate, and the best-effort/bounded distinction. Both
  were latent in what we had already written and neither of us had said them.
- I contributed the fixes and one push-back that survived scrutiny.

The honest summary is that a second reader is worth more than a second run, and
a reader from outside the conversation is worth more still — but for different
things. The peer caught what the code does; the external reader caught what the
words were failing to say.

## Assumption → Eval contradiction → Correction

- Assumed: a defect that is real, measured, and deliberately not fixed is
  adequately handled by a comment at the call site explaining why.
  Review said: documenting a trap is not making the harness robust — the
  comment tells the next person to avoid the hole, it does not stop the hole
  producing a traceback instead of a diagnosis when someone falls in anyway.
  Corrected: the comment now names a concrete end state (explicit 5–10s budget,
  `PlaywrightTimeoutError`, structured `eval_env` result) and is marked
  `ponytail:` so `/ponytail-debt` harvests it, with a matrix row carrying the
  same text. A deferral with a named end state is debt; a deferral with only a
  reason is a rationalisation.

- Assumed: "evidence best-effort" in a `try/except` comment described the
  block's behaviour.
  Review said: `try/except` bounds error propagation, not latency. The two are
  independent, and the comment silently claimed both.
  Corrected: already fixed in code (`SCREENSHOT_TIMEOUT_MS`); what this adds is
  the general form, now written into ADR-007 and the browser-domain skill so
  the next unbounded default inside a handler is easier to see. This is the
  second time in two milestones that a *comment asserting a property the code
  lacked* is what hid a defect from review.
