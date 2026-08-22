# ADR-016: The plan lint and `extract_all` — the planner-side half of the aggregate guard

Date: 2026-08-22
Status: accepted

**Ruling**: a superlative task whose plan does not read the page exactly once with `extract_all` is rejected at every point the executor adopts a plan — before the browser moves, and again on an `act`-ladder replan — and replanned once through the existing replan budget; `extract_all` is the primitive that lets the replan land, and the ranking over what it enumerates is done in code (`verifier.rank`), never by the model, both halves gated on the one `is_aggregate` shape. The lint is deterministic and site-agnostic — an LLM debater was considered and rejected.
**Because**: PR #25 closed this hole at the verifier, which is correct and one layer too late — the run still had to move the browser and produce a wrong answer for the guard to reject, and the guard's own comment said why it could not do better ("the plan vocabulary has no comparison primitive to have gotten it right WITH"). Adding the verb is what lets the guard relax; rejecting the plan is what stops paying for the verdict in actions.
**Enforced by**: `verifier-aggregate-superlative-fails-loud`, `probe3-quotes-most-quoted-author`, `rank-reduces-enumeration-in-code`, `plan-gap-truth-table`, `extract-all-refuses-a-selector`, `extract-all-list-task-keeps-every-row`, `extract-all-cheapest-wording-still-reduces`, `plan-lint-holds-across-a-midrun-replan`, `replan-cannot-launder-noop-action-extract-all`, `recovery-replan-postcondition`, `planner-prompt-carries-the-note`, `verifier-aggregate-ground-truth-untouched`, `ui-execution-progress-is-trace-derived`

---

## Context

M10's second held-out probe asked "which author has the most quotes listed on
the first page?" and got `status: success, verdict: PASS` with a wrong answer,
three times, with two different wrong strings (`docs/analysis.md` §8a-2). PR #25
fixed it at the verifier: `aggregate_needs_comparison` fails any layer-1-only
verdict on the superlative shape, and declared the cost as D22 — it now refuses
questions a single extraction would have answered correctly, on every live run,
because a live run has no ground truth.

Two things were left open by that fix, and both are named in its own comment.
The plan that produced the wrong answer is still emitted, executed, and paid
for in actions before the verdict arrives. And the guard cannot ever relax,
because there is no plan it could relax *for*: `navigate | click | fill |
extract` has no way to say "read all of these and compare them".
`live-books-cheapest-travel` is the same gap in the price direction — the
deployed run `734d3d1f` planned "read article 0" for "the cheapest book" and
returned the first tile.

## Decision

### 1. `extract_all` — one new step, and only one

`extract_all` resolves its target the same way `extract` does, at the same
tiers, with the same site-agnostic keys — except that several matches are the
answer rather than a `locate` failure (`resolver.resolve(..., many=True)`). It
contributes a list of values, one evidence record each.

**It refuses `index` and `near`.** Both mean "of these matches, that one",
which is the opposite of what the step asks for, and the resolver honours
`near` before it honours `many` — so the combination enumerated a single
element, ranked it against nothing, and shipped a trace whose `extract_all`
step relaxed the aggregate guard (Decision 4) for a single-shot read. Found in
cold review before this milestone was committed, watched red as a wrong answer
scored `success` with every check green, and closed the way an unknown target
key is: loudly, because the executor does not reinterpret a plan that says two
things (`extract-all-refuses-a-selector`).

Rejected alternatives: a `count` step (the count is derivable from the list and
a second step could disagree with the first), a `filter`/`sort` step (site
knowledge by the back door — "sort by price" is a control on a page, and
`click` already reaches it), and a `compare` step (that is the LLM ranking,
which is the thing this ADR exists to keep out of the model).

### 2. The ranking is arithmetic, in code

`verifier.rank(task, values)` reduces an enumeration to the item the task's
superlative asks for. **Whether to reduce at all is its own decision, from the
task text**: a task that asks for the enumeration (`list`, `every`, `each`)
keeps its list; anything else with a `_RANK` word gets one item. Two wrong gates
were tried here and both are cased. Gating on the answer's shape alone (a single
list) truncated "list every product … cheapest first" from four rows to one and
reported success (PR #29 R2, `extract-all-list-task-keeps-every-row`). Gating on
`is_aggregate` instead over-corrected: it dropped the reduction for every
`cheapest` wording — the milestone's own headline shape — and published the raw
enumeration as a successful answer to a single-answer question (PR #29 R9,
`extract-all-cheapest-wording-still-reduces`). The two cases are a pair: one
rule has to keep both green, and either alone is satisfied by deleting the
other's behaviour.

The reduction and the lint therefore run on **different** vocabularies, on
purpose. `_RANK` includes the price wording; `_AGGREGATE` does not, and `_AGGREGATE` needs BOTH halves to match — a `which|what|who` frame AND a word from {most, least, fewest, highest, lowest, greatest} — and the frame alone is not enough: `verifier-catches-listing-dump`'s own committed task, "Which product is the cheapest, and what is its price?", has the frame and still returns `is_aggregate(...) is False`, because `cheapest`-style price wording lives only in `_RANK`. So a price-worded ranking is reduced but not linted — declared
as T-CHEAPEST-WORDING, not fixed here.

Three rules, chosen by what the values *are*: EVERY value
parses as a number → compare the numbers; NONE of them does → count
occurrences, which is what "which author has the most quotes" is actually
asking; some but not all → refuse. No ranking word in the task → the list is
the answer and survives untouched.

A tie **refuses**, and so does a column that is only partly numeric. Two
winners mean the enumeration does not identify one answer, and picking either
would be a confident wrong answer — the same ruling ADR-006 made for `near`
(`near-equidistant-is-ambiguous`). Both surface as `failure:semantic`: the page
was read correctly and does not decide.

The partly-numeric rule came from cold review, and the first implementation had
the dangerous default. `if all(nums)` fell through to the counting branch, so
one "Out of stock" in a price column demoted a comparison into a mode: the
repeated price won "highest", and — worse — the junk cell, unique and therefore
never a tie, won "cheapest" and was reported as the price. Both watched red
(`rank-reduces-enumeration-in-code` rows 8 and 9).

`rank`'s direction vocabulary is deliberately **not** `_AGGREGATE`'s. The two
answer different questions — "is this an aggregate-shaped task" (the lint's and
the guard's shared ceiling) versus "which end of the order did it ask for",
once a plan has already enumerated — and only the second needs to cover the
price wording `_AGGREGATE` excludes on purpose (D14). Widening one does not
widen the other, and widening `_AGGREGATE` to reach "cheapest" would have put
fifteen existing shop-fixture cases through a lint they have no reason to meet.

### 3. The lint is structural, and it is not an LLM critic

`agent.plan_gap(task, steps)` runs at **every point the executor adopts a
plan** — the first plan, before any action, and again on `steps[:si] +
new_steps` when the `act` ladder replans mid-run. Running it only on the first
plan left the second adoption point unlinted, and a mid-run replan produced
exactly the unranked list of lists this decision names as the defect, scored
`success`/`PASS` (PR #29 R3, `plan-lint-holds-across-a-midrun-replan`). A future
adoption point (M32's `observe` replan) has to lint too; that is the invariant,
not the two call sites. The rule: task matches `verifier.is_aggregate` and the
plan's extraction steps are not
**exactly one `extract_all` and nothing else** → do not execute. Every other
shape leaves the comparison with no single set of values to rank over, and all
of them are quiet rather than loud: zero enumerations guesses the winner; two
yields a list of lists; one enumeration beside a plain `extract` yields a
composite answer that `rank` never sees (it reduces an enumeration only when
the enumeration IS the answer) while the relaxed guard passes it on the
strength of an `extract_all` in the trace. That last shape was the M31
spec-drift audit's top finding against this function's first version, which
asked only whether SOME step enumerated. The truth table is graded directly
(`plan-gap-truth-table`), since the two end-to-end cases reach only two rows.

Replan once with a note naming the gap, and stop by the same no-progress rule
the `act` ladder uses — an empty plan, an identical plan, or a second plan
carrying the same gap ends the run as `failure:task`. There is no third pass
and no path where a gapped plan runs anyway.

An **accepted** lint replan is charged to the same `budgets["replans"]` counter
the `act` ladder spends from, so the lint cannot buy itself attempts the ladder
then also gets. A **rejected** one is not: the run ends there, and the counter
measures replans that produced a plan, exactly as the `act` ladder's own
no-progress branch does. The planner call is still billed either way
(`llm_tokens`/`llm_usd` are added before the check), so the cost is visible even
when the replan credit is not — `verifier-aggregate-superlative-fails-loud`
pins `replans: 0` on that path.

**Why not a debater / critic agent.** The owner's third hypothesis in
`prompts/015` was an LLM beside the planner arguing about what to do. It was
checked and rejected on three grounds, and this is the record of that:

1. **It has no more ground truth than the planner.** The one catch a debater
   was actually predicted to make on this eval set — "this plan has no
   comparison step" — is a *structural* property of the plan, and structural
   properties are exactly what deterministic code decides better than a model.
   Everything else it would say is another opinion about a page neither of them
   can verify.
2. **It costs the offline gate its only stubbed boundary.** The `fast` suite is
   $0.00 because there is exactly one LLM seam (`planner`) and the harness
   injects a stub into it. A second model means a second stub, two stubbed
   opinions arguing in a test, and a gate that measures the stubs.
3. **It is not falsifiable per-case the way this repo grades things.** A lint
   either fires on a plan or it does not, and one case pins each direction
   (`verifier-aggregate-superlative-fails-loud`,
   `probe3-quotes-most-quoted-author`). A critic's verdict varies run to run,
   which is the failure mode `docs/architecture/task1-overview.md` chose
   architecture B to avoid: silent-failure prevention structural, not
   behavioral.

The note reaches the trace as well as the planner: it is written onto the first
step of the replanned plan, so a reader of `trace.jsonl` or the SSE stream sees
why the plan changed. It is deliberately not labelled `recovery` — nothing
failed and no ladder ran, and ADR-003 keeps that flag for a classified failure
that switched strategy, which is what keeps the recovery metric honest. Both
claims are cased rather than asserted: `probe3-quotes-most-quoted-author` pins
`recovery: false` and `trace_note_contains`, each watched red against the
variant that breaks it (PR #29 R6).

**The framing of a replan prompt belongs to the caller, not to the planner.**
`live_planner` used to prepend one shared sentence to every note — "A previous
attempt failed … plan only the steps still needed from the page above" — which
is true of the `act` ladder and false in all three clauses of the lint's replan,
where nothing has executed, nothing has failed, and the whole task is still to
be planned. The planner now appends the note verbatim and each call site writes
what actually happened.

Graded in two halves, because one of them alone was mistaken for both.
`expect.planner_note_contains` reads `stub_planner.notes` and grades **what the
call site passes** — the lint path by `probe3-quotes-most-quoted-author`, the
act path by `recovery-replan-postcondition`. It does not reach `live_planner`
at all: every offline case uses the stub, so the line this decision changed was
executed only by `full`-tagged cases and reverting it left the whole suite green
(PR #29 R11). The message build is now the pure function `planner.build_user`,
graded directly by `planner-prompt-carries-the-note` — the note arrives verbatim
and the planner adds no framing of its own — at no key, no network and no
token.

The ceiling is stated rather than hidden: `is_aggregate` is a regex over
English, so a rephrased superlative walks around the lint exactly as `log into`
walked around `SCOPE_BLOCK` (D21). The lint is not a proof that a plan can
answer the question; it is one shape, the shape a probe demonstrated.

### 4. The verifier guard relaxes, and keeps a backstop

`aggregate_needs_comparison` now passes when the **graded** trace contains an
`extract_all` step. Graded, not present: an `act`-ladder replan can supersede
the enumeration mid-run and execute a bare `extract` in its place, and a
relaxation written over the whole trace would let that launder itself
(`verifier-aggregate-ground-truth-untouched` row 5). That is also the one route
the lint cannot see — it reads the first plan, and a mid-run replan is not one
— so the M10 guard stays exactly where it was, as the backstop for it.

The E2E half of `verifier-aggregate-superlative-fails-loud` therefore changed
meaning rather than being deleted: the same input now stops one layer earlier
(`failure:task`, one action spent), and the guard it was written for is graded
directly, in both directions, by the rows of
`verifier-aggregate-ground-truth-untouched`.

## Consequences

- **D22 shrinks and is restated, not deleted** (`docs/support-matrix.md`). The
  false refusal it declares is still real, but it is now reachable only by a
  run that enumerated nothing — and a first plan that enumerates nothing does
  not execute. The row carries the re-measurement.
- **Replan rate moves, and is published** (design decision D7,
  `docs/architecture/task1-overview.md`): the lint spends replans that the act
  ladder used to be the only consumer of. The suite's own number is in
  `evals/report/` and README's "Where it stands" block, derived by
  `docs-numbers-are-derived` rather than typed.
- **`live-books-cheapest-travel` becomes expressible, not yet proven.** The
  primitive and the reduction it needs both exist and are graded offline
  (`rank-reduces-enumeration-in-code` row 1 is that case's own eleven Travel
  prices). The case itself still needs `OPENROUTER_API_KEY` and a real planner
  call, so it stays `full`-tagged and unrun in this milestone, the same
  declared state it has had since M6. Neither the lint nor the reduction fires
  on it — "find the cheapest book" is not an `_AGGREGATE` match — so what M31
  gives it is the vocabulary, the prompt line and — since PR #29 R9 — a
  reduction that fires on its wording once a plan enumerates. What it does not
  give it is the lint that would make a plan enumerate: `_AGGREGATE` needs BOTH halves to match — a `which|what|who` frame AND a word from {most, least, fewest, highest, lowest, greatest} — and the frame alone is not enough: `verifier-catches-listing-dump`'s own committed task, "Which product is the cheapest, and what is its price?", has the frame and still returns `is_aggregate(...) is False`, because `cheapest`-style price wording lives only in `_RANK`.
  PR #29 R4 called the acceptance line out as unmet; it is amended in
  `tasks/TODO.md` with the reason, and the residual is T-CHEAPEST-WORDING.
