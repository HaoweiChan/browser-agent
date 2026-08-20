# ADR-005: What the M3/M4 cold review found, and what it did not fix

Date: 2026-08-16
Status: accepted

**Ruling**: Answer comparison checks value, unit and currency as three separate facts, never one normalized string; a replan may not drop a superseded step and extract anyway unless that step provably never changed the page (`page_changed`); a recovery only counts when its first replacement step differs from the one it replaced; the URL guard re-checks `final_url` after every action, not just the submitted string; and a `superseded_by` pointer is written when its replacement step is created, never before.
**Because**: Six cold-review defects shared one shape — a wrong or unverified answer scoring PASS on a suite that was already green on 52 cases.
**Enforced by**: `evals/adversarial/verifier-sign-currency-percent.json`, `replan-cannot-launder-noop-action.json`, `supersede-never-dangles.json`

---

## Context

M1 and M2 were closed with a cold review; M3 and M4 were not, and were committed
without one. This ADR records the review that ran before the M5 freeze, across
two scopes (the reliability core, and the gateway/UI), and what changed.

The result argues for the step rather than for the code: **six defects, three of
which let a wrong or unverified answer score PASS, in code that was already
green on 52 cases.** M2's close-out found three of the same shape. The pattern is
stable enough to state plainly — this repo's suite is good at catching what it
was pointed at, and blind in the direction the author was already looking.

## Corrected

**1. The grader equated numbers it should not have.** `normalize`'s pattern
opened with a greedy Unicode `[^\w]*`, which ate the sign before the group's own
`[-+]?` could take it and erased every currency symbol: `-39 == 39`,
`€18 == $18`, `2.5% == $2.50`, `(39.00) == 39.00`. At layer 2, the only layer
that decides correctness, and upstream of every other number in the repo.

The fix is not a better regex. A single canonical string *cannot* express this,
because the relation is not transitive: `$39` and `39` are the same answer,
`€18` and `18` are the same answer, and `€18` and `$18` are not. So
`answers_match` now compares value, unit and currency as three separate facts —
a symbol may be absent on one side, two different symbols never match, and a
unit like `%` must match exactly. `normalize` stays a string key for name
matching, where the resolver uses it. Case: `verifier-sign-currency-percent`.

**2. A replan could launder an action that never landed.** `act` failure →
supersede the step → replan drops it → extract anyway. Supersede exempts the
failed step from `no_failed_postcondition` and `actions_verified`, so the run
returned `success`, verdict PASS, with the *pre-action* answer.

What makes this the sharpest finding in the review: it is **indistinguishable
from the legitimate case by any rule over the plan**. `recovery-replan-postcondition`
has the same shape — click, postcondition never arrives, replan skips to
extraction — and is correct, because there the click really did sort the list.
The only discriminator is whether the action moved the page at all, so that is
now recorded (`page_changed`, specs/001) and gates the drop. Family 2 had only
its happy path pinned, while family 1's equivalent rule was enforced in code and
pinned by `relocation-distinct-tier`. Case: `replan-cannot-launder-noop-action`.

**3. Retry wearing recovery's badge.** The no-progress guard compared the whole
replacement list against the whole tail, so a replan whose first step was
byte-identical to the step that just failed counted as progress if anything
later differed — and was labelled `recovery` unconditionally. The headline
`recovery n/n verified` number was reachable without any strategy change. Now
the replacement's first step must differ from the step it replaces — family 2's
version of the distinct-tier rule. Case: `recovery-label-requires-strategy-change`.

**4. The URL guard was an input filter, not a guard.** It ran on the submitted
string and in the `navigate` branch, so a click, a 302 or a meta-refresh walked
the browser off the allowed host unchallenged, and `final_url` was never
checked. The frontend told reviewers verbatim that a blocked URL is refused
before a browser opens — true only of the string. Worse: **no eval passed
`url_guard` into `run_task` at all**, so both in-agent checks could have been
deleted with every suite still green. The guard is now re-checked after every
action. Case: `url-guard-holds-after-navigation` grades the enforcement; the
existing `url-guard-literal-ips` grades the predicate. Neither is coverage alone.

**5. The honesty artifact could go quietly blank.** `parse_matrix` keyed on a
heading prefix and an exact cell count and asserted nothing about having found
anything, so a renamed heading, an added column or one unbalanced fence made a
section parse to zero entries — and `support-matrix-cites-real-cases` stayed
green, because it iterates rows it did not find and every surviving citation
still resolves. The frontend then rendered a clean, header-only table: an agent
declaring no limitations at all. Now empty or malformed sections raise. Case:
`matrix-parse-fails-loudly`. Same runner: `known` case ids were globbed from
`evals/*/*.json`, which swept in `evals/report/*.json`, so a report filename
counted as a valid citation.

**6. A dangling supersede on the failure path.** The replan wrote
`superseded_by = len(trace) + 1` *before* the replacement existed. If a budget
tripped on the next iteration, the run shipped a trace whose last, run-killing
step pointed at a step number that was never created — and `verify()` runs only
on the success path, so `supersedes_resolve`, the check specs/001 says makes the
supersede exemption safe, was bypassed on exactly the path that produced it. The
frontend dimmed that fatal step and labelled it "superseded by #31", the
vocabulary it reserves for "a ladder replaced this". The pointer is now written
when the replacement is created. Case: `supersede-never-dangles`.

Also corrected, without a case of its own: `recovery_verified` was computed from
the runtime's own `status`, so a run that "recovered" into a wrong answer counted
toward the headline recovery number even when ground truth said FAIL. It is now
graded on the audit.

## Not fixed, and why

Recorded rather than quietly carried. Each is real; none is a wrong answer
scoring PASS, and the freeze is close.

- **Anchors can be satisfied by discarded evidence.** `verify` drops superseded
  steps from `trace` grading but builds `evidence_text` from *all* extractions,
  including a superseded attempt's. The supersede gate covers the trace only.
- **A replan after a completed extract would append a second answer**, turning a
  scalar into a list. Known since ADR-003; still no case produces it.
- **`grounded` is close to tautological** — `evidence_window` builds the window
  around the value, so the check can only fail if the value is absent entirely,
  or is long enough to be truncated (which would be a false `failure:semantic`).
- **Relocation rung 1 ignores the target's role**, so a target
  `{role: link, text: X}` can relocate onto a same-named heading. A real
  precision bug on listing pages; needs a fixture that reproduces it.
- **`MAX_FIXES` cannot bind** — `relocation_candidates` never returns more than
  two rungs, so the per-step ladder budget in ADR-003's table is currently
  unreachable, and INV-3's ladder-class half has no end-to-end case.
- **`stream-shows-every-step` grades the `on_step` data, not the SSE endpoint.**
  It installs its own hook and compares step `i` only, so the gateway's emitter
  and its copy semantics are untested, and stripped step *contents* would pass.
  Testing the endpoint means either the live planner or a stub backdoor on a
  public route; neither is worth it before the M5 probe.
- **Fixtures and the `?mut=` fault-injection layer are served by the production
  app.** Inside rule 6's carve-out (never executor input) but a placement smell:
  a deployed executor can be pointed at its own fixtures.

## Consequences

The `fast` suite goes 52 → 58 cases and ~24s → ~32s, the increase being one
extra `inner_text` per action to capture `page_changed` — evidence bought
deliberately, since it is the only thing separating finding 2 from its benign
twin. Still inside the 60s gate (ADR-002).

For M5: the "not fixed" list above is the honest backlog, and the reported
recovery number should be read knowing it moved from a runtime-status count to
an audit-graded one. The support matrix carries the reader-facing half.
