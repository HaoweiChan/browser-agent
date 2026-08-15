# 003 — M2: eval backbone, and the grader turning out to be the weakest link

**Date**: 2026-08-16 · **Milestone**: M2 · **Outcome**: 41/41 fast, 5/5
invariant, 6/6 traps caught, $0.00; fixtures + 3 mutations + OutcomeVerifier
L1–L2; ADR-002 sets thresholds; scope checkpoint committed.

## Context

M2 per `tasks/TODO.md`: two fixture sites, three tier-breaking mutations, the
EvalAuditor adapter, OutcomeVerifier L1–L2 with identity anchors, TC1–TC5
coverage, cost fields in reports, and a baseline that ADR-002 turns into
thresholds. The milestone exists to make silent failure *measurable*, so most
of the value is in cases that can go red, not in code that runs.

## Assumption → Eval contradiction → Correction

Design-time, before any M2 code shipped:

- Assumed: realistic product markup (a `<dl>` with `aria-label` on the values)
  would be addressable by role+name, since Chromium's accessibility snapshot
  reports the name.
  Probe said: `get_by_role("definition", name="Warranty")` matches **0**
  elements — ARIA prohibits an author name on `term`/`definition`, so
  Playwright computes `""` no matter what the DOM says. The planner is
  instructed to target only what the observation shows, so it would have
  confidently emitted an unresolvable target on an element sitting in plain
  sight.
  Corrected: `observe()` blanks names on name-prohibited roles;
  `observe-name-prohibited-roles` guards it (watched red first); the residual
  gap is declared `unsupported` in the support matrix rather than hidden.

During implementation:

- Assumed: `ids-renamed` breaks the agent's stable-attr dependency.
  Eval said: `l4-shop-ids-renamed` red on first run — the mutation was renaming
  ids the *fixture's own script* depended on, so it broke the page, not the
  agent. A fault injector that damages the fixture measures nothing.
  Corrected: fixture scripts resolve their own elements by tag/aria-label;
  `mutation-catalog-integrity` now asserts the fixture contains no id lookups.
  The lesson went into the browser-domain skill: **a fixture must survive its
  own mutations.**

## Cold review at close-out (fresh-context reviewer, evidence only)

Three findings, all of the same shape — *a wrong answer scored PASS* — and all
against a suite that was 36/36 green at the time. Each became a case, was
watched red, then fixed:

- Assumed: `%g` formatting was a fine way to compare numbers.
  Reviewer said: `%g` is 6 significant digits, so the grader declared
  `$12,345.67` and `$12,345.74` equal. Every price above ~$9,999 lost its cents
  at the one layer whose entire job is deciding correctness. No golden case had
  an answer longer than 4 significant digits, so the numeric branch was only
  ever exercised where it happened to be exact.
  Corrected: exact `Decimal` comparison; `verifier-numeric-precision`, tagged
  `invariant` — a grader that cannot tell two numbers apart invalidates every
  other measurement in the repo.
- Assumed: `check_state` returning `True` for "nothing to check" was harmless.
  Reviewer said: it recorded unverified steps as `postcondition_ok: true`,
  making the module docstring's "every step is postcondition-verified" false —
  and the planner prompt actively encouraged `expected_state: null`. Separately,
  the `if/elif` chain graded compound expectations on their first key alone.
  Corrected: `postcondition_ok` is now true/false/**null**, every key must
  hold, `fill` verifies itself by readback, and the verifier fails any run with
  an unverified click. `postcondition-unverified-click` deliberately fails a
  plan that produces the *right* answer — an unverified state change is not a
  verified one. The planner prompt now requires a postcondition on every click.
- Assumed: identity anchors meaningfully constrain the answer.
  Reviewer said: the eval-side anchor corpus included the answer, so an anchor
  equal to the expected answer certified itself — unfalsifiable in four shipped
  cases. And on an aggregate page every candidate entity is in the page text,
  so the anchor passes for the wrong answer too.
  Corrected: anchors are checked against page evidence only
  (`verifier-anchor-not-self-satisfied`); the aggregate-page vacuity is not
  fixable at layer 1 and is now a trap case (`trap-search-not-executed`), a
  declared limitation in `verifier.py`, and a row in the support matrix.

Also fixed from the review: the forms fixture's ground-truth state was reset
only on opt-in, so a case written without the flag would grade against the
previous case's submission. Now reset unconditionally — an eval whose result
depends on case order is worse than no eval.

Two findings I did **not** treat as defects, with reasons: fixture machinery
(`?mut=`, `/fixtures/forms/state`) is reachable on the deployed app *by design*
— the architecture makes the mutation demo first-class UI; and the `grounded`
check is weak but not tautological, since `evidence_window` falls back to the
page head when the value is genuinely absent.

## The checkpoint the review changed

`docs/evals/scope-checkpoint.md` was written before the review, from 8 observed
failures, and concluded `locate` 4/8 dominated. The review added four more and
the distribution became `locate` 4/12, `act` 4/12, silent 3/12, `env` 1/12 —
tightening rather than overturning the M3 choice (relocation + postcondition
replan), and making the second family clearly load-bearing rather than a
make-weight. Worth recording that the honest number moved *after* the note was
written, and the note was updated rather than the finding filed away.

## Notes for M3

The mutation-recovery count that matters is **0/3**, not 2/3: `ids-renamed` and
`wrapper-nesting` pass because plans never depended on those tiers, so nothing
was relocated. `l4-shop-button-text-renamed` is committed expecting
`failure:locate` precisely so M3 has to flip it in the report history. And
tightening postconditions will push more live runs into `act` stops — Family 2
is what turns those into outcomes instead of dead ends.
