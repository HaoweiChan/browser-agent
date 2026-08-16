# 007 — M5: the freeze, and the probe that made it worth doing

**Date**: 2026-08-16 · **Milestone**: M5 · **Outcome**: 60/60 fast, 18/18
invariant, 1/1 live; M4 deployed and verified; held-out probe run against the
live URL with raw results published.

## Context

M5 is the B-freeze: analysis, README, prompts, and the mandatory held-out probe.
The prompt was one line — continue with M5 — and the first useful thing was not
building anything. It was checking what was actually true.

Two facts surfaced immediately and neither was visible from inside the repo:

1. `docs/analysis.md` did not exist, so the E4 rubric cell had no evidence.
2. **The deployed instance had been serving the M1 build for four milestones.**
   `/support-matrix` 404'd; the page still titled itself "deploy spike". M2, M3
   and M4 existed only in git. Every claim about the reviewer UI was true of the
   repository and false of the URL a reviewer would open.

That second one is the M5 lesson. "Deployed at M1 and kept alive" was recorded
in the tracker and was technically true — the *instance* was alive. Nobody had
checked that it was alive *serving the current code*.

## Assumption → Eval contradiction → Correction

- Assumed: fixtures plus three DOM mutations were enough coverage to defer live
  work to the freeze without cost.
  The first live domain said: `observe()` walks the a11y tree depth-first to a
  60-element cap, so on a real listing page the whole budget went to banner and
  sidebar — **none of the twenty products were ever observed.** The planner
  planning blind about the only part of the page the task concerned, which is
  exactly what commit `ed1f774` claims to have closed.
  Corrected: a chrome sub-budget rather than a bigger cap, with an offline
  nav-heavy fixture as the deterministic twin.

- Assumed: the scope screen was settled — five L5 refusal cases, all green, and
  a comment in the code saying "every L5 refusal case is caught by the pattern
  below".
  The held-out probe said: `\blog ?in\b` needs a word boundary after `in`, and
  **"log into" has none**. The deployed agent walked to a real Google login
  wall, recovered from a locate failure to find the Sign in button, typed the
  literal placeholders `<email>` and `$EMAIL` into the credential field,
  submitted twice, and spent $0.0235 — five times a normal run — on a task that
  should have cost nothing.
  Corrected: inflections, "into" and hyphenated forms. The comment was the tell:
  it was true and meaningless, because the cases had been written to the regex.
  `screening-word-boundary` even reasons about boundaries — only in the
  false-positive direction. Nobody checked the other way.

- Assumed: writing the probe's findings up was a documentation task.
  Reality: one finding could not be fixed honestly. "What is the sign in the
  shop window?" is refused today, and no keyword screen can separate it from
  "sign in to my account" — same words, different intent.
  Corrected: that row was written into the new case and then **removed**, and
  the over-refusal declared in the support matrix instead. Encoding it as
  `expected: blocked` would have made the eval set certify a bug as a feature,
  which is the exact failure this repo is built to avoid.

## What the probe is worth

2 correct answers out of 8 answer-seeking tasks. A reviewer reading only that
would call the capability thin, and they would be right — it is about one hop
deep.

But **no run reported success with a wrong answer**, every failure was loud and
classified, and the trace named the exact failing target every time. That is the
property the whole design is for, and the probe is the first evidence for it
that was not written by the author.

The honest caveat is recorded next to it: probe #5 returned a 20-book page dump
as its answer and was rejected on a whitespace technicality rather than on "this
does not answer the question". Nothing in the verifier asks whether an answer is
*responsive*. That guarantee held by luck once, and the analysis says so.

## AI-collaboration note

The probe agent was told to write its 10 tasks before reading `evals/`, and to
verify every answer against the target site rather than trusting the run. Both
constraints mattered: the tasks it wrote are ones the author would not have
written, and the one it flagged hardest — a Gmail login — is a phrasing no case
in this repo used.

Running the two adversarial passes (cold review at the M4/M5 boundary, held-out
probe at the freeze) produced 7 defects that 59 self-written cases did not. The
number now in the README and the analysis — 10 defects found by review or by
unfamiliar input, in code green at the time — is the most useful measurement
this project produced about its own method.
