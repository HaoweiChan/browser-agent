# ADR-009: The mutation catalogue is five, not six, and the hostile domain answered "Next →"

Date: 2026-08-19
Status: accepted; Decisions 5 and 6 were amended in the same PR (#12) by
Decisions 7, 8 and 9, after three review rounds: two found the same metric
block wrong twice, the third found the documents describing it stale. The original text is left as written; Decisions 7 and 8 say what moved
and — in round 2 — where round 1's own repair fell short.

## Context

M8's brief (`tasks/TODO.md`) is three things: finish the mutation catalogue,
add a hostile live domain, and publish both raw. The named risk was written
into the milestone before any code: **catalogue scope creep — each mutation
must break a tier a plan stands on, or it is decoration.** The B-strong list
`docs/evals/evaluation-methodology.md` has carried since M0 names six
mutations, and the list was written before the resolver existed. This ADR
records which of them survive contact with the resolver that was actually
built, what the hostile domain did, and the two metrics that had to be fixed
before the numbers meant anything.

## Decision 1 — the admission test is "a capability a plan stands on", not "a locator tier"

Applying "must break a tier" literally would have admitted three of the six
and rejected the two most interesting. The test used instead: **does a plan
that works on the base fixture stop working under this mutation, for a reason
the agent could not have avoided by being written differently?**

| candidate | admitted? | what it breaks | the rung that survives |
|---|---|---|---|
| duplicate-labels | yes | role+name **uniqueness** | text |
| a11y-stripped | yes | the role tier, for controls | text |
| element-reordered | yes | positional `index` | `near` (but nothing relocates) |
| render-delayed | yes | *when* the resolver looks (10s late) | nothing |
| overlay-modal | yes | actionability after a successful resolve | replan (the act family) |
| classes-scrambled | **no** | nothing | — |

**classes-scrambled is dropped.** Not deferred, not backlog: the resolver has
no class tier, `observe()` never reports a class, and no target key in
`specs/001-browser-contract.md` can name one. A `classes-scrambled` L4 case
would pass on every fixture the moment it was written, without a single line
of relocation running, and it would then be counted in "N mutations survived".
That is the decoration the milestone's named risk warned about, and the
cheapest way to fail the risk would have been to implement it anyway because
it was on a list.

Two of the five admitted are not tier breaks at all — `render-delayed` breaks
the instant the resolver looks, `overlay-modal` breaks what it may do once it
has looked. They are the two that found the most, which is the argument for
the wider test.

## Decision 2 — each mutation was watched red by ablating the mechanism that saves it

"Red without relocation, green with" is M8's validation line, and by M8 the
relocation ladder already exists — so a new L4 case cannot be watched red the
way `l4-shop-button-text-renamed` was at M2 (committed expecting
`failure:locate`, flipped at M3). The red half was produced by **ablation**:
the same case, the same mutation, with the ladder that rescues it turned off.
Raw, 2026-08-19:

```
[ablation] agent.MAX_FIXES = 0            # relocation ladder off
[FAIL] l4-shop-duplicate-labels   failure:locate
       ResolveError: 2 matches at tier role for {'role': 'button', 'name': 'Search'}
[FAIL] l4-shop-a11y-stripped      failure:locate
       ResolveError: no tier resolved {'role': 'button', 'name': 'Search'}

[ablation] agent.MAX_REPLANS = 0          # act-family replan off
[FAIL] l4-shop-overlay-modal      failure:act
       TimeoutError: Locator.click: Timeout 10000ms exceeded.
       ... <button onclick=...>Close</button> from <div id="mut-overlay">…</div>
           subtree intercepts pointer events
```

A fourth, `l4-forms-a11y-stripped`, ablates the same way (`no tier resolved
{'role': 'button', 'name': 'Submit enquiry'}`) and exists for a second reason —
see Decision 2b.

With the ladders on, all four are green and all four assert the mechanism,
not just the outcome (`recovery: true`, and `replans: 1` for the overlay).
The overlay's log line is also the first executable evidence for a claim the
`browser-domain` skill has asserted in prose since M1: overlay interception
surfaces as a click timeout and must be classified `act`, not `locate`. It is
classified `act`, and the act ladder — which had exactly one case before this
one — is what rescues it.

The two remaining mutations need no ablation because they are committed with
the failure as their expectation: they are red in the only sense that matters
(the agent does not survive them) and green only as pins on observed
behaviour.

## Decision 2b — the a11y-stripped shim was wrong on the fixture no case covered

"A mutation must break the agent, never the fixture" is the `ids-renamed`
lesson from M2. a11y-stripped turns every `<button>` into a `<div>`, which
disables a submit button, so the mutation ships a click shim that restores what
a mouse user still has on a real div-soup site. The first shim dispatched a
`submit` event on the enclosing form. Against `shop.html` — whose form is
JS-handled, `onsubmit="return doSearch(event)"` — that is indistinguishable
from correct, and `l4-shop-a11y-stripped` was green with it.

`forms.html` is a real POST form. A dispatched event fires no navigation and no
request there: the mutation would have silently disabled every future case
pairing a11y-stripped with a native form, while the case guarding the mutation
stayed green. Caught by running that pairing as a probe before committing, and
kept as `l4-forms-a11y-stripped` so it cannot come back: the shim is
`form.requestSubmit()`, and the case's pass condition is the server's own
record at `/fixtures/forms/state` (verifier layer 2), so a green means the POST
really landed. It is also the catalogue's only mutation coverage of TC5.

## Decision 3 — element-reordered is committed with the wrong answer as its expectation

`index` is not a locator tier. It is load-bearing anyway: two of the three
pre-M8 live domains reach their answer by counting (`live-books-travel-price`
index 5, `live-hn-item1-title` index 11), and both cases have declared in
their own triage since M5 that a re-ordered page would silently return the
wrong element. Nobody had ever run that.

Run it and it is worse than declared. Under element-reordered,
`{role: listitem, index: 2}` moves from the Meridian row to the Aurora Pro
row, and the run reports **success** with `Aurora Desk Lamp Pro $59.00` for a
task about the Meridian Wall Clock. Every guard passes: `grounded` (the text
is on the page), `not_a_dump` (26 of ~170 characters), and **both** identity
anchors — the runtime `anchor not in body` gate and `verify()`'s
`identity_anchors` — because "Meridian Wall Clock" is on the page whichever
row was read. There is no relocation either: `relocation_candidates` returns
no rungs for a target that names no string, deliberately.

So `l4-shop-element-reordered` is committed asserting the wrong answer. That is
**not** the `live-ol-search-a11y-invisible` convention, which this ADR first
claimed it was: that case pins a *failure* and carries no `expect.answer`, so no
ground truth is injected at all. These are the first two cases in the repo to
pin a **wrong answer as layer-2 ground truth**, which means their committed
audit reads `answer_matches: true, ground_truth: true, verdict: PASS` for an
answer every document here calls wrong (PR #12, R14). They therefore carry
`expect.answer_is_known_wrong: true`, and the adapter echoes
`known_wrong_ground_truth` into the published result, so the artifact says what
the prose says. Its pair,
`l4-shop-element-reordered-near`, runs the identical task and mutation with
`near:` instead of `index:` and answers correctly at tier `structural`. The
pair is the first measurement of what `near` was built for at M6 — until now
`near` had four cases proving it resolves correctly and none proving it
resolves something positional targeting gets *wrong*.

## Decision 4 — the hostile domain is quotes.toscrape.com, and its result is a wrong answer reported as success

`quotes.toscrape.com/js` renders all ten quotes with `document.write` into
`span`/`div`. Measured 2026-08-19 through the production `navigate()` +
`observe()` path:

| | /js | /js-delayed |
|---|---|---|
| `page.inner_text('body')` | 1,499 chars, all ten quotes | 78 chars, chrome only |
| `observe()` elements | 11, of which **0 are content** | 11, same |
| `get_by_role('link')` | 5, all chrome | 5 |
| `get_by_role('listitem')` | 1 — the pager | 1 |

The planner is blind to content the verifier can read in full. Given an
observation containing a WebArea, a heading, five chrome links, a navigation, a
list, one listitem (the pager) and a contentinfo — eleven elements, none of them
content — the most plausible target for "the first quote" is
`{role: listitem, index: 0}` — and it resolves, to the pager. The run reports
`success`, answer **"Next →"**, runtime verdict PASS
(`live-quotes-js-role-tier-blind`). `identity_anchors` passes too, on
"Albert Einstein", because that string is in the body text whether or not the
agent ever reached it — the aggregate-page hole `verifier.py` documents in its
own docstring, now instantiated on a site nobody here authored.

Two companion cases keep the finding narrow instead of sweeping:

- `live-quotes-js-text-tier-reaches` — the same page, `{text: "J.K. Rowling"}`,
  resolves at tier `text` and answers correctly. The page is readable; it is
  not *plannable*. (Einstein is quoted twice on page 1, so the same plan with
  his name raises `ambiguous-match` — measured.)
- `live-quotes-js-delayed-empty` — the same plan one URL over, where the
  content arrives ~10s late: `failure:locate`, loud, correct, no answer
  invented. This is the live twin of the render-delayed mutation, and it is
  what stops that fixture mutation from being a thought experiment.

Nothing about this was softened to make a case green. The support matrix row
for the domain is `unsupported` (TC1), citing the case.

## Decision 5 — two metrics were counting the wrong thing, and M8 is the first milestone that could see it

**Mutation survival.** `metrics["mutation_passed"]` was
`int(result["status"] == exp["status"])` — "the case matched its expectation".
Every mutation case since M2 expected `success`, so the two readings were
indistinguishable. M8 wrote the first mutation cases that expect the agent to
lose (a wrong answer; a loud stop), and the metric counted both as survivals.
Measured over the 10 mutation cases that existed when it was found: **10/10
under the old rule, 8/10 under the new one** (11 cases and 9/11 as committed).
The fix is one key — `expect.mutation_survived: false` —
excluding a case from the numerator while keeping it in the denominator, which
is the same shape as the M3 rule that a mutation nobody had to relocate around
is not a recovery.

**Recovery labelling on a failed rescue.** `l4-shop-render-delayed`
deliberately does not assert `recovery`. The relocation attempts it makes
*are* labelled `recovery` in the trace, so asserting the label on a run that
failed would have scored a failed rescue as a `recovery_verified`. The
adapter's existing guard (`recovery_verified` requires all checks to pass)
would have held here, but only by luck of this case's shape; the case
documents the trap rather than relying on it.

## Decision 6 — the `fast` gate now costs 66.6-68.3s, over ADR-002's 60s, and the case stays

`l4-shop-overlay-modal` spends 10.6s of that on one Playwright click timeout.
The decision was taken on a single 67.6s run; the heading carries the band the
committed reports actually measure, **66.6-68.3s** (68.05s in
`evals/report/20260820-020212-fast.json`) — observations on one machine, not a
bound, since a reviewer measured 68.6s on another. `docs/support-matrix.md` D8
carries the same range.

That is not waste: Playwright retries the hit test until the timeout, so
discovering that a resolved element cannot be clicked costs exactly one
timeout, and there is no cheaper way to observe interception. The obvious
"optimisation" — lowering the production click timeout so an eval runs faster
— is precisely the anti-pattern ADR-008 Decision 3 caught with `MIN_EVIDENCE`
(a production constant bent to accommodate eval scaffolding), so it was not
done.

The other 57s is not M8's. The trend is 13s (M2) → 48.6s (M6) → 55.4s (M7) →
57s (M8 without the overlay case): the suite would have crossed 60s at M9
regardless. Recorded as `docs/support-matrix.md` D8 rather than fixed here,
because the honest fix is the parallel eval runner that has been in the
backlog since M0, and promoting it is a milestone of its own with its own
evidence. Until then the pre-commit gate costs a minute, which is the number a
reviewer should see rather than a threshold quietly rewritten to contain it.

## Decision 7 — review round (PR #12): the relocation count, and a fix nobody could grade

Three findings, all in the metric block, all of the same family as Decision 5 —
a counter whose label had drifted from what it counts, and which M8 was the
first milestone able to see.

1. **"N by relocating" included a rescue that relocated nothing.**
   `l4-shop-overlay-modal` is saved by the act-family replan: its four resolved
   tiers are all `role`, `replans == 1`, no tier ever changes — and it was
   inside the published 6. Both ladders write the same
   `retry_or_recovery: "recovery"`, so the label cannot separate them; the
   *failure class of the attempt a rescue supersedes* can (`locate` = relocation
   ladder, `act` = replan ladder). Split into `mutation_recovered` (any family)
   and `mutation_relocated`, and `evals/run.py` now prints
   `N recovered (K by relocating)`. **Every published figure moves from
   "6 by relocating" to "6 recovered, 5 by relocating"** — including the first
   commit's message, which is left as history rather than rewritten.
2. **Decision 5's own fix had no case.** Reverting `mutation_passed` to the
   pre-M8 expression left `fast` at 84/84 and restored the flattering 11/11
   silently: a case's `passed` never reads its `metrics`, and the runner gates
   on `passed` only. The counters are now a pure function
   (`eval_adapter.mutation_metrics`) with an invariant case over synthetic
   traces (`mutation-metrics-honesty`), watched red first — and re-checked by
   putting the old expression back, which turns three of its six rows red
   (six rows at that point; ten after Decision 8).
3. **`mutation_recovered` was not survival-gated**, so a future case shaped like
   `l4-shop-element-reordered` (a wrong-but-successful answer after a rung) would
   have counted inside "by relocating" while sitting outside "survived", making
   the subset larger than its superset. Both recovery counters now carry the
   survival term.

Two smaller ones from the same review: the a11y-stripped submit shim keyed on
`[type="submit"]`, which HTML does not require of a submitter, so an implicit
`<button>` in a form would have been silently disabled — exactly Decision 2b's
failure mode, avoided only by fixture accident. It keys on `data-was-button`
now. And `render-delayed`'s injected delay went 3s → 10s: the delay costs the
suite nothing (the run ends long before the timer fires), so the only thing the
number buys is margin over the 388ms run it bounds — 26x instead of 7.7x — in a
suite ADR-002 calls deterministic.

## Decision 8 — review round 2 (PR #12): both round-1 repairs moved the defect one step

A second reviewer, with no memory of round 1, checked the repairs instead of
trusting them. Both MEDIUMs were confirmed on the runtime before being relayed.

1. **`mutation_relocated` still credited relocation for a replan's rescue.**
   Round 1 read "a rescue whose superseded attempt failed `locate`" — but every
   relocation rung wears the `recovery` label and supersedes the attempt before
   it, *including the rungs that lose*. So a run that failed `locate`, lost every
   rung, and was then saved by the replan family was still counted as relocated.
   Measured on the real runtime (`shop.html?mut=overlay-modal`, first target
   without a `role` so it cannot resolve): tiers `['role','text','role','role',
   'role']`, both rungs failing `act`, `replans: 1`, 21s — `mutation_relocated`
   **1 before, 0 after**. A rescue is now a labelled attempt that *succeeded*;
   the family still comes from the superseded attempt's failure class.

2. **`survived` still meant "matched its expectation".** The second term was
   `status == exp["status"]`, so a case that expected *and got* `failure:locate`
   counted as a survival unless its author remembered `mutation_survived: false`
   — which is verbatim the defect Decision 5 claims to have closed, one opt-in
   away. Surviving now requires `status == "success"` (plus: the case did not
   expect a failure, and did not declare the run a loss). `l4-shop-render-delayed`
   has had the key **removed** — its status excludes it — leaving exactly one
   case that still needs it, the wrong-answer pin `l4-shop-element-reordered`.

**No published figure moved**: 9/11 survived, 6 recovered, 5 by relocating,
before and after. Both non-survivors were already excluded, one by its key and
one (now) by its status. The counters were wrong; the catalogue's numbers were
not — which is exactly why neither round could have been caught by reading the
report.

The reviewer's sharper point was about the guard, not the counters: six
synthetic rows written by the author of the function can encode the
implementation rather than the intent. `mutation-metrics-honesty` now carries
ten rows chosen to discriminate against **named wrong implementations**, and the
discrimination is measured rather than asserted — each of seven plausible wrong
versions (the pre-M8 expression; the status term deleted; status-only; three
variants of the relocation reading, including round 1's; and dropping the
survival term from either recovery counter) turns the case red, and the case's
provenance records which row catches which. Round 1's expression is now killed
by exactly one row, "rungs lost, replan won" — the row this round added.

Two LOWs from the same review, both fixed: `mutation-catalog-integrity` graded
whatever `checks` blocks it happened to list rather than comparing them to
`mutate.MUTATIONS`, so a sixth mutation added without a block would have shipped
unguarded and green (watched red by adding one); and the round-1 D10 row was
written outside its own markdown table, so the disclosure rendered as a
pipe-delimited paragraph — the parser is line-based and could not see it, which
is a fair reminder that `support-matrix-cites-real-cases` grades citations, not
layout.

## Decision 9 — review round 4: the code was right, the declarations were not

Round 3 verified that the round-2 repairs hold — no counter moved a third time
— and every finding after it was declaration-vs-code drift. That is its own
lesson, so it is recorded rather than quietly patched: **this PR changed the
same metric rule three times and updated a different subset of its four
descriptions each time.** The ADR and the support matrix were amended in rounds
1 and 2; `docs/evals/evaluation-methodology.md` was not, and spent two rounds
telling readers that the metric "counts matched its expectation" (the defect)
and that two cases carry `mutation_survived: false` (one does). The prose that
went stale was the prose nothing could grade.

So the fix is not only the paragraph. `opt-in-expect-keys-declared` grades the
**case-file side** of the claim — not the prose, which no case parses (R17): the
declared users of `mutation_survived` and
`answer_is_known_wrong` are compared against the case files, in sets, so the
next time one moves the suite names the file instead of a reviewer naming it two
rounds later. It joins the same family as `mutation-catalog-integrity`'s
MUTATIONS coverage check (round 2) and `support-matrix-cites-real-cases`. The
repo's own history is the argument for it: "no case shows this shape" has been
falsified within days three times in this project.

**The artifact, not just the prose (R14).** `l4-shop-element-reordered` and
`live-quotes-js-role-tier-blind` pin wrong answers, and `expect.answer` is
layer-2 ground truth to `verify()` — so the committed reports carry
`verdict: PASS, ground_truth: true, answer_matches: true` for "Next →" as the
author of a quote. The prose called it wrong; the raw artifact read as verified.
M8's gate criterion is *hostile results published raw*, which is a claim about
the artifact, so both cases now carry `expect.answer_is_known_wrong: true` and
the adapter echoes `known_wrong_ground_truth` into the result. This ADR also
cited `live-ol-search-a11y-invisible` as the precedent for pinning a wrong
answer; it is not one — that case pins a *failure* and injects no ground truth
at all. Corrected in Decision 3.

**Superseded reports keep their green audits (R19), declared.** Only the final
`fast` and `live` report of this branch carries `known_wrong_ground_truth`; the
thirteen earlier ones committed here were produced before the marker existed and
still show the two pins as `verdict: PASS, answer_matches: true` with nothing
beside it. They are not deleted: `CLAUDE.md` makes `evals/report/` the record of
**every** run, and removing an artifact to improve how the branch reads is the
opposite of what that rule is for. So the rule is stated instead — a reader
jq-ing across `evals/report/` should take the newest report of a suite as the
one whose conventions are current, and the two pinned cases are named here, in
`docs/support-matrix.md` D5/D7 and in the case files themselves.

**Owner ratification of the amended M8 gate (R20), 2026-08-20.** The M8
validation cell in `tasks/TODO.md` was amended during this PR: the original read
"each new mutation red without relocation, green with", and two of the five
mutations have no green half, because no ladder can rescue them. The amended
cell reads "…**or**, where no ladder can save it, committed with the observed
failure as its expectation (3 of 5 green, 2 pinned as losses)". A reviewer
correctly flagged that a delivery agent editing its own acceptance criterion is
not a self-closing question. It went to the owner, and **the owner ratified the
amended wording as written**, on the grounds that the two unrescuable mutations
are pinned as honest losses rather than faked rescues (CLAUDE.md rule 4) and
that the cell discloses the split inline, so no reader can infer 5/5. Recorded
here so a spec-drift audit finds an owner for the amendment instead of an
unexplained edit.

**Declared, not fixed (R15).** `mutation_relocated` reads the recovery family
from the immediately-superseded attempt, so a genuine relocation whose previous
rung failed `act` — the laundering shape `live-ol-search-a11y-invisible`
records — is undercounted. No case produces it, the error can only understate
relocation, and the alternative was speculative counter surgery in the round
meant to close the PR. Named at the call site with its upgrade path and in
support-matrix D11.

## What is deliberately NOT fixed

1. **A bounded wait in `resolve()`** (would close render-delayed and
   `live-quotes-js-delayed-empty`). Every legitimately-absent element would pay
   the same wait, and this suite is full of cases whose entire point is that a
   tier finds nothing — including the first rung of every L4 case here. The
   honest version waits on the first tier only and arrives with its own case
   and its own latency measurement.
2. **A text-node fallback in `observe()`** (would close the hostile domain's
   blindness). It changes what every planner prompt sees on every page, and
   its cost is measured in planner tokens on a `full` run this milestone did
   not spend. Named, not attempted.
3. **An L3 evidence-only LLM check** — the only layer that could catch
   "Next →" as an answer to "who is the author". Absent by design since M2
   (`docs/evals/evaluation-methodology.md`), and still absent.
4. **Element-scoped identity anchors** (would catch element-reordered's swap).
   Not a fix, a different contract: it breaks every case whose anchor is
   legitimately elsewhere on the page, starting with `live-hn-item1-title`,
   which anchors on the submitter while extracting the title.
5. **The mutation cases still run hand-written plans**, like every other
   fixture case (`cost-discipline`). What is measured is
   resolver/executor/verifier under breakage; planning under breakage is
   unmeasured, and the hostile domain is where that gap hurts most — the whole
   D7 finding is about what a planner *could* have written from the
   observation it was given.

## The SHOULD left open

**Live-drift snapshot replay** was M8's third listed item and is not in this
PR. It is the one mechanism that would let a live DOM change be replayed
offline as a regression case (today a live case either passes against the
site's current shape or fails loudly, and the shape it failed against is not
kept). Deferred deliberately, not forgotten: it needs a capture format, a
storage decision for the snapshots, and a rule for when a snapshot is refreshed
— three decisions this milestone could not take without spending the evidence
budget the mutation catalogue and the hostile domain needed.

## Consequences

Buys: five B-strong mutations that each break something a plan stands on, with
their red halves recorded (six new L4 cases, seven counting the `near` twin); a hostile live domain whose result is a wrong answer
published as it ran; two metrics that stop flattering; and a fourth live domain
(nine rows in the support matrix, four of them live).

Costs: a pre-commit gate at 66.6-68.3s across runs (68.05s in the committed
`evals/report/20260820-020212-fast.json`), over its own documented ceiling; two
committed cases whose green means "the agent is reliably wrong here"; and a
declared limitation list seven rows longer (D5–D11).

Numbers, 2026-08-20 (after all repair rounds, PR #12): `fast` 86/86 in 68.05s
(`evals/report/20260820-020212-fast.json`), `invariant` 22/22
(`…-020104-invariant.json`), `live` 9/9 (`…-020100-live.json`), $0.0000, mutation **9/11 survived, 6 recovered — 5 by
relocating** (was 4/4, 2 relocating), recovery 7/7 verified over 13 rungs,
diagnosis 14/14. The first commit published "6 by relocating"; Decision 7 is
why that figure moved.

