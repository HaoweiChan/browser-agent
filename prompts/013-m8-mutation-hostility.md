# 013 — M8: mutation & hostility, and a counter that took two rounds to become true

**Date**: 2026-08-19 → 2026-08-20 · **Milestone**: M8 (A-phase) ·
**Outcome**: five B-strong mutations added on a stated admission test and one
candidate dropped for failing it; a hostile live domain whose raw result is a
confidently wrong answer; seven new L4 cases, three new pure-code guards; 86/86
fast, 22/22 invariant, 9/9 live, $0.0000. `mutation 9/11 survived, 6 recovered
(5 by relocating)`. **Five review rounds on PR #12** moved no product code and
found six defects anyway — all of them in the *measurement* and the *evidence*,
which is the part of this repo that had never been reviewed by anyone but its
author. `specs/decisions/ADR-009-m8-mutation-hostility.md`.

## Context

The milestone's own risk line was written before any code: *"catalogue scope
creep — each mutation must break a tier a plan stands on, or it's decoration."*
The B-strong list had been carried in `docs/evals/evaluation-methodology.md`
since M0, written before the resolver existed. So the first question was not
"how do we implement six mutations" but "which of these six break anything the
resolver actually stands on".

The delivery ran through the pr-loop: an implementer session in a worktree, a
gate, and a `pr-reviewer` with fresh context that never saw the implementer's
reasoning. Five review rounds followed, four of them authorised by the owner
after the three-round circuit breaker tripped.

## The prompt (verbatim, condensed)

> **Catalog scope = tier-breaking mutations only.** Implement the B-strong
> mutations that actually break a tier or capability the resolver stands on.
> `classes-scrambled` is explicitly **dropped** — the resolver has no class
> tier, so it would break nothing; record that reasoning in the ADR rather than
> silently omitting it… For each one you keep, state in its provenance which
> tier it kills and which tier survives for relocation to climb to…
> **Hostile live domain = `quotes.toscrape.com/js`**… **Publish results raw** —
> if the agent fails on it, the case's expectation encodes the real observed
> behaviour with the failure class… A hostile domain that quietly passes
> because you softened the task is worthless evidence… **Rule 6 is the trap in
> this task**: production execution-policy code must gain **no** site-specific
> selectors — if making a hostile case pass would require site knowledge in the
> executor, do not do it: let the case record the honest failure instead.

Two instructions in that brief did more work than the rest combined. "Record
the reasoning rather than silently omitting it" is what turned a dropped
mutation into a written admission test. "Let the case record the honest
failure" is what made two of the five mutations shippable at all — they have no
green half, and pretending otherwise would have meant faking a rescue.

## The resulting decision

- **Admission test, written down**: *does a plan that works on the base fixture
  stop working under this mutation, for a reason the agent could not have
  avoided by being written differently?* Wider than "is it a locator tier" —
  which is why `render-delayed` (breaks *when* the resolver looks) and
  `overlay-modal` (breaks what it may do after looking) are in, and they found
  the most.
- **`classes-scrambled` dropped, not deferred.** No class tier exists,
  `observe()` never reports a class, no target key can name one. Its L4 case
  would have passed on the day it was written, with no relocation running, and
  then been counted as a mutation survived.
- **Two mutations ship as losses.** `element-reordered` turns a positional plan
  into a confident wrong answer (`Aurora Desk Lamp Pro $59.00` for a task about
  the Meridian clock, past `grounded`, `not_a_dump` and *both* identity-anchor
  checks); `render-delayed` stops loudly at `failure:locate`. Neither can be
  rescued by any ladder, so both are committed asserting what the build really
  does. The owner ratified the amended M8 gate wording that this required
  (ADR-009 Decision 9).
- **The hostile domain answered "Next →".** On `quotes.toscrape.com/js` the
  body carries all ten quotes in 1,499 characters while the observation the
  planner would get carries none — 11 elements, every one chrome. Asked who
  wrote the first quote, the run answers the pager link and reports `success`.
  Published as it ran.
- **Red halves are ablations, not prose.** `MAX_FIXES = 0` →
  `ambiguous-match: 2 matches at tier role` and `no tier resolved`;
  `MAX_REPLANS = 0` → `failure:act` with Playwright's log naming the overlay
  subtree. Reproduced independently by the round-6 reviewer.

**AI recommendation: accepted, then corrected five times.** No product file
changed in any of those rounds — `git diff --name-only fcd4d60..HEAD -- src/`
touches `mutate.py` (fault injection) and `eval_adapter.py` (harness) only.
Every correction was in what the milestone *claimed*, not in what it did.

## Assumption → Eval contradiction → Correction

- **Assumed**: a mutation case that matches its expectation is a mutation the
  agent survived — the count had meant that since M2.
  **Eval said**: M8 wrote the first mutation cases that expect the agent to
  *lose*, and the metric counted both as survivals: 10/10 where the honest
  reading was 8/10 (measured directly over the ten cases).
  **Corrected**: `expect.mutation_survived: false` excludes a case from the
  numerator while keeping it in the denominator (`eval_adapter`).

- **Assumed**: that fix was the end of it.
  **Eval said**: nothing graded it. A case's `passed` never reads its
  `metrics`, so reverting the line left `fast` at 84/84 and restored the
  flattering 11/11 in silence (reviewer, PR #12 R2).
  **Corrected**: counters extracted to `mutation_metrics()` and pinned by
  `mutation-metrics-honesty` — watched red first, then re-checked by putting
  the old expression back, which turns three of its rows red.

- **Assumed**: with a guard in place, "survived" was now defined correctly.
  **Eval said**: it still meant *matched its expectation* — a case that
  expected **and got** `failure:locate` counted as a survival unless its author
  remembered the opt-in key (R8). The guard did not catch it, because no row
  paired a status mismatch with a default key.
  **Corrected**: surviving requires `status == "success"`; the opt-in key is now
  needed by exactly one case, and `l4-shop-render-delayed` had it removed.

- **Assumed**: "N by relocating" counted relocations.
  **Eval said**: `l4-shop-overlay-modal` is rescued by a *replan* — four
  resolved tiers, all `role`, nothing relocated — and was inside the published
  6 (R1). Both ladders write the same `recovery` label.
  **Corrected**: the family is read from the failure class of the attempt a
  rescue supersedes; the runner prints `N recovered (K by relocating)`.

- **Assumed**: reading the superseded attempt's class was the right rule.
  **Eval said**: every relocation rung supersedes the attempt before it,
  *including rungs that lose*, so a run whose rungs all failed and whose replan
  saved it still counted as relocated (R7). Reproduced on the runtime: tiers
  `['role','text','role','role','role']`, both rungs `act`, `replans: 1` —
  `mutation_relocated` **1 before, 0 after**.
  **Corrected**: a rescue is a labelled attempt that *succeeded*; new row
  `"rungs lost, replan won"` in `mutation-metrics-honesty`, and the case's
  provenance now records which wrong implementation each row kills, measured
  against seven of them.

- **Assumed**: a case pinning a wrong answer is documented by its prose.
  **Eval said**: `expect.answer` is layer-2 ground truth to `verify()`, so the
  committed live report read `verdict: PASS, ground_truth: true,
  answer_matches: true` for `"Next →"` answering "who is the author of the
  first quote" (R14). The gate criterion is *hostile results published raw* —
  a claim about the artifact, and the artifact read as verified-correct.
  **Corrected**: `expect.answer_is_known_wrong: true` on both pins, echoed into
  the published result as `known_wrong_ground_truth`; the ADR's claim that this
  followed the `live-ol-search-a11y-invisible` convention was itself wrong (that
  case pins a *failure* and injects no ground truth) and is corrected in place.

- **Assumed**: the a11y-stripped submit shim restored what a mouse user has.
  **Eval said**: it selected `div[type="submit"]`, and HTML does not require a
  submitter to spell that out — `shop.html`'s JS-handled form made the first
  shim (`dispatchEvent`) look correct while `forms.html`'s real POST submitted
  nothing. Watched red: `failure:act`, server record still all `None`, while
  `l4-shop-a11y-stripped` stayed green in the same run.
  **Corrected**: `form.requestSubmit()`, keyed on a `data-was-button` marker,
  with `l4-forms-a11y-stripped` grading it against the fixture's own `/state`
  endpoint — a mutation that damages the fixture measures nothing (the
  `ids-renamed` lesson, learned again).

- **Assumed**: `mutation-catalog-integrity` pinned every mutation in the
  catalogue, as `mutate.py`'s docstring claims.
  **Eval said**: it graded whatever `checks` blocks the case file happened to
  list; coverage was complete by coincidence (R11).
  **Corrected**: the adapter compares the blocks against `mutate.MUTATIONS` in
  both directions — watched red by adding a mutation with no block.

- **Assumed**: the documents describing all of the above were kept in step.
  **Eval said**: the same metric rule changed three times and a different
  subset of its four descriptions was updated each time; the methodology doc
  spent two rounds describing the fixed defect as current (R12), and the front
  page still published the pre-M8 build with a named report that was no longer
  the latest (R16).
  **Corrected**: `opt-in-expect-keys-declared` grades the *case-file* side of
  the claim in sets, so the next drift names the file; the prose stopped
  claiming to be graded, since nothing parses it. README, `docs/analysis.md`,
  the support matrix and this record now read on the committed M8 reports.
