# 006 — The cold review, and what a live domain found in one afternoon

**Date**: 2026-08-16 · **Milestone**: M3/M4 close-out → M5 · **Outcome**: 6
defects in code green on 52 cases (ADR-005); then the first live domain found a
7th; 59/59 fast, 17/17 invariant, 1/1 live.

## Context

M1 and M2 were closed with a cold review. M3 and M4 were committed without one —
not by decision, but because the milestones felt finished. The prompt that
started this was one line: run the cold-reviewer pass before M5.

Two scopes were reviewed in parallel (reliability core; gateway/UI), each told
what the code *claims* and asked to hunt for inputs where a wrong or unverified
answer still scores PASS. Neither was shown the author's reasoning.

## Assumption → Eval contradiction → Correction

- Assumed: the grader's numeric comparison was settled — `verifier-numeric-precision`
  had already caught it once and had ten rows.
  Review said: `normalize`'s greedy `[^\w]*` ate the sign before the group's own
  `[-+]?` could take it, and erased every currency symbol. `-39 == 39`,
  `€18 == $18`, `2.5% == $2.50`.
  Corrected — and the *first* fix was wrong, which is the interesting part. A
  better regex cannot express this, because the relation is not transitive:
  `$39 == 39` and `€18 == 18` and yet `€18 != $18`. The suite caught the bad
  fix (`$39.00 == 39` broke), and the second attempt changed `answers_match` to
  compare value, unit and currency as three separate facts.

- Assumed: family 2 (replan) was demonstrated by `recovery-replan-postcondition`.
  Review said: that case is the *benign twin*. Its evil twin — same shape, but
  the click does nothing — returned `success` with the pre-action answer and
  verdict PASS.
  Corrected: no rule over the plan can separate them, because the difference is
  only in the world. `page_changed` was added as the discriminator, and it is
  the one piece of evidence bought (one `inner_text` per action, +8s on the
  suite) rather than reasoned around.

- Assumed: the URL guard was a guard.
  Review said: it ran on the submitted string and in the `navigate` branch only,
  so a click or a redirect walked the browser off the allowed host unchallenged
  — and **no eval had ever passed `url_guard` into `run_task`**, so both
  in-agent checks could have been deleted with every suite green. Meanwhile the
  frontend told reviewers a blocked URL is refused before a browser opens.
  Corrected: re-checked after every action, with a case that grades enforcement
  and the existing truth-table case that grades the predicate.

- Assumed: the support matrix could be trusted to render what it declares.
  Review said: a renamed heading or one unbalanced fence made it parse to zero
  limitations, its own case stayed green, and the UI rendered a clean empty
  table — an agent declaring no limitations at all.
  Corrected: it raises now. The case that was supposed to guard it also counted
  `evals/report/*.json` filenames as valid case citations.

- Assumed: fixtures plus mutations were enough domain coverage to defer live
  work to the freeze.
  The first live domain said: `observe()` spends its whole 60-element budget on
  banner and sidebar navigation, so on a real listing page **none of the twenty
  products were ever observed**. The planner planning blind about the only part
  of the page the task concerned — the exact failure M1's "observe before
  planning" fix exists to prevent, reintroduced as a budget rather than an
  omission. Every fixture was too small for the cap to bind.
  Corrected: a chrome sub-budget, not a bigger cap.

## The measurement that matters most

Across five milestones, **9 defects were found by cold review or by adding a
domain — not by the suite — in code that was green at the time**. The live
domain made it 10 within an hour of existing.

The conclusion is not that the eval set is weak; it is 59 cases and it caught a
wrong fix during this very session. It is that **an eval set written by the
author of the code is blind in the direction the author was already looking**,
and the only two things observed to move that blind spot are adversarial review
and unfamiliar input. Recorded in `docs/analysis.md` as a property of the
method, and the reason the cold review should be a gate rather than an option.

## AI-collaboration note

The reviews were run as two parallel subagents with no access to the reasoning
behind the code, which is what made the "benign twin" finding possible — the
author knew why `recovery-replan-postcondition` was correct and therefore did
not ask what else had that shape. The provenance of one case in this batch was
also corrected after the fact: the red proof for the URL-guard case did not
produce a wrong answer as first written, it produced a browser somewhere the
guard forbids. The claim was narrowed to what the mutation actually showed.
