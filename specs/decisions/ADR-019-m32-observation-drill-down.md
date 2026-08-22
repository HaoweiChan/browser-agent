# ADR-019: M32 — the planner can ask for a deeper view of the page

Date: 2026-08-22
Status: accepted

**Ruling**: the plan vocabulary gains a fifth action, `observe`, whose `target` names a container the planner was already shown; the executor re-runs `observe()` scoped to that subtree with the whole `MAX_ELEMS` budget spent inside it and a 1,500-character text head, and hands the result to the planner through the observation+note arguments a replan already uses, spending one call from the existing `MAX_REPLANS` budget. Progressive disclosure of the PAGE; the capability list stays fully disclosed and the executor stays closed-world.
**Because**: the planner's ceiling on M10 probe #4/#5/#7 was not that it misunderstood its tools — the closed-world executor would have graded that `failure:task` and zero runs did — but that the answer was verbatim in page text the planner was never shown, and `observe()`'s cap is what withheld it; raising the cap moves the cliff to the next larger page and taxes every task, while asking for one subtree taxes only the task that asks.
**Enforced by**: `observe-drilldown-past-max-elems`, `observe-cap-hides-the-answer-element`, `observe-blind-plan-dumps-the-container`, `observe-refused-drilldown-stops-the-run`, `observe-drilldown-no-progress-stops-the-run`, `observe-drill-into-chrome-gets-the-page-budget`, `observe-drill-text-head-reaches-past-300`, `observe-cannot-launder-noop-action`, `observe-drilldown-cannot-launder-noop-action`, `observe-drilldown-cannot-launder-unchecked-action`, `recovery-label-lands-on-the-extract`, `observe-step-cannot-carry-expected-state`, `planner-note-is-not-always-a-failure`

---

## Number

017 and 018 are deliberately skipped, not lost. ADR-016 exists twice in flight
(merged `main` has ADR-016 for M34; the open `task/M31` branch carries its own
ADR-016 plus an ADR-017), so M31 must renumber on merge and the first number
that cannot collide with either branch is 019. Ids have been taken out from
under concurrent sessions in this repo before; a gap is cheaper than a
collision.

## Context

`tasks/TODO.md` M32, from `prompts/015`. The prompt that opened it asked
whether wrapping the tools as MCP and disclosing them progressively would
raise completion. The eval record said no on both halves, and said something
else instead:

- **The capability list is not the gap.** The system prompt *is* the tool
  catalogue — 4 actions, 5 target keys, 3 `expected_state` shapes — and the
  executor refuses anything outside it (`resolver-unknown-target-key`, and
  now `observe-drilldown-past-max-elems`'s own red run,
  `StepError: unknown action 'observe'`). None of M10's seven misses was an
  unknown-action or unknown-key failure.
- **Disclosing the catalogue lazily saves nothing.** It was ~524 tokens of
  system prompt per call against a measured ~1,440-token planning call
  (`cd7121fc`, `734d3d1f`), under Anthropic's 1,024-token caching floor and
  under 1.5% of the 100k run budget.
- **The page is what is under-disclosed.** `observe()` caps at
  `MAX_ELEMS=60` and `TEXT_HEAD=300`. M10 probe #4, #5 and #7 each had the
  correct value verbatim inside the page text the agent itself captured and
  absent from the elements the planner was shown (`docs/analysis.md` §8a-2,
  finding 3: "when the agent captures the right data but can't answer, it
  dumps the whole page"). `live-quotes-js-role-tier-blind` is committed as
  the same shape on a live site — "readable but unplannable".

So progressive disclosure was not rejected; it was pointed at the other
object.

## Decision

### 1. One new action, `observe`, with a `target` subtree

`{"action": "observe", "target": {...}}`. The target is resolved by the
ordinary resolver, at the ordinary tiers, from the ordinary five target keys —
there is no new addressing scheme and no new target vocabulary. The executor
re-runs `observe()` with that locator as `root`, which changes exactly two
things about the walk:

- the whole `MAX_ELEMS=60` budget is spent inside the subtree instead of
  being consumed by everything ahead of it in document order — including when
  the drilled container is itself a landmark, where the chrome sub-budget
  (`MAX_CHROME=20`) is deliberately lifted: it exists to stop navigation
  nobody asked about from eating the page budget, and a drill-down is the
  planner asking. Cold review found the first cut capping a drill into
  `complementary` at 20 elements while the note told the planner it had the
  subtree entire (`observe-drill-into-chrome-gets-the-page-budget`); a
  page-level observation is unchanged, and `observe-content-survives-chrome`
  still holds it at 20 there;
- the text head is `DRILL_TEXT_HEAD=1,500` characters of *that subtree's*
  text rather than 300 characters of the page's.

Everything else — `SKIP_ROLES`, the `NAME_PROHIBITED` blanking, `render()` —
is unchanged, because the scoped observation is the same object in the same
format. There is no second observation type.

An `observe` step carrying an `expected_state` is refused as `failure:task`
rather than ignored. There is nothing for it to assert, and left to
`check_state` a failing assertion raised `StepError("act")` for a step that
acted on nothing — diagnosing the run `failure:act` and opening the act/replan
recovery ladder for a read-only step (`observe-step-cannot-carry-expected-state`).

### 2. It reaches the planner through the path a replan already uses

The scoped observation is passed as the `observation` argument of the next
`planner(...)` call, with the `note` argument saying which target was drilled
and that the observation is a subtree rather than the page. That is the same
two-argument channel `live_planner` already renders into its prompt and the
same one family 2's act-failure replan uses. No new planner argument, no
side-channel, no second prompt.

The note is now rendered **verbatim**. It used to be wrapped in "A previous
attempt failed: …" inside `live_planner` — true of the only caller that
existed when that wrapper was written, and false for the one this ADR adds: a
drill-down is a *successful* request, and telling the model the step that
asked for it failed steers it away from the container the answer is inside.
The framing moved to the caller that knows what happened (`agent.py`'s
act-failure replan says "failed" in its own note), and the assembly moved out
of the closure into `planner.build_user_message`, module-level and pure, so
the `fast` suite can grade the real string with no key and no spend
(`planner-note-is-not-always-a-failure`). Found by cold review; the `fast`
suite could not have seen it, because it stubs the planner one level above.

**An `observe` attempt replaces nothing and recovers nothing**, and two
trace fields follow from that. It never wears `retry_or_recovery: "recovery"`
— a recovery label claims a strategy changed after something failed, and
wearing it would put a read-only step inside the published "rungs tried"
figure, the same flattering-number defect `mutation-metrics-honesty` and PR #12
R7 were filed against. And it never consumes a pending `superseded_by` pointer:
that field claims "this failed attempt was replaced by that one", and an
observation replaces nothing. Both skip past the `observe` and land on the next attempt of any other kind;
if the run ends before one, the failed step keeps `superseded_by: null`, which
is the direction `supersede-never-dangles` asks for. That next attempt is
often an `extract`, which is read-only as well — deliberately not excluded,
because an `extract` is what completes a recovery and `recovery-replan-
postcondition` is the shape where the new plan is nothing else. The
distinction the metric cares about is not "does this step change the page" but
"could this step have saved the run": an `observe` produces no answer
(`recovery-label-lands-on-the-extract`).
`observe-drilldown-past-max-elems` asserts `recovery: false` for a drill-down
that follows nothing, and `observe-drilldown-cannot-launder-noop-action`
asserts it for one that follows an act failure — where a legitimate `recovery`
label is also present, on the step that does the acting.

### 3. It spends the existing budget, and no new one

The drill-down increments `budgets["replans"]` and is refused past
`MAX_REPLANS`. This is deliberate: a planner that keeps asking to look
instead of acting is the same runaway as one that keeps failing, and it must
hit the same wall. The worst case per run is therefore what it already was —
one plan plus two further calls — so the run-level ceiling does not move.
Bounded by `RUN_BUDGETS["llm_tokens"] = 100_000` above that, exactly as
before (INV-3, `budget-replans-exhausted`).

**Both replan paths apply the same laundering-evidence rule.** A plan may not
reach an `extract` with nothing that changes the page before it while a failed
action that changed nothing is still outstanding — that plan reports the state
the failed action was supposed to produce. `replan-cannot-launder-noop-action`
established the rule and asked it as "is the first step an `extract`", which
was the same question while `extract` was the only read-only action; `observe`
is a second one, so the test is now "does this plan read without acting first",
with leading `observe` steps transparent to it for the same reason their
`page_changed` is null (`agent.reads_without_acting`,
`observe-cannot-launder-noop-action`). The drill-down's own replan is a second
planner call and can return the same shape, so it carries the rule too and ends
the run as the act failure it actually died of
(`observe-drilldown-cannot-launder-noop-action`). Both guards read the evidence
through one predicate, `agent.changed_nothing`, for which `page_changed: null`
and `page_changed: false` mean the same thing — `null` is what every act
failure raised inside `execute` leaves behind, and for one commit the two
guards disagreed about it, which is the whole of
`observe-drilldown-cannot-launder-unchecked-action`. A plan that looks and THEN
acts is not laundering and is not refused.

One no-progress guard applies: a replan that returns an empty plan, or the
same steps that are already pending, is not taken. Family 2's other two
guards are about a plan laundering a *failed* action, and no action failed
here.

**A refused drill-down ends the run; it does not fall through.** Both
refusals — budget exhausted, and a replan that made no progress — return
`failure:env` naming the target that was asked for. The first cut only
appended a note, and because a drill-down opens on no failure there was no
class to carry, so the loop continued and executed whatever the plan had put
*after* the `observe`: cold review demonstrated a run that spent its entire
planning budget asking for a closer look, never got one, then answered from
the observation the drill-down existed to replace and reported `success` with
a green verdict (`observe-refused-drilldown-stops-the-run`,
`observe-drilldown-no-progress-stops-the-run`). `env` is the class
`budget_stop` already uses for a resource that ran out; specs/000's rule that
a ladder keeps the class of the failure it was fixing does not apply to a
ladder that was fixing nothing.

### 4. What it costs, measured

The **before** column is measured from committed reports. The **after**
column is arithmetic over those measurements plus the measured prompt delta —
stated as such, because measuring it directly means a `full`-suite run against
a paid model and this milestone did not spend one:

| | before | after | source |
|---|---|---|---|
| system prompt | 2,096 chars ≈ 524 tokens | 2,485 chars ≈ 621 tokens | `prompts/015` measured the 524; the delta is +389 chars at that file's own 4.00 chars/token |
| tokens per task, default model (`openai/gpt-5.6-luna`), no drill-down | 1,177.4 mean (758–1,693 over 5 runs) | ≈ 1,274 (+97, +8.2%) | `evals/report/20260821-004617-ablation.json`; all 20 rows there spent 0 replans, so tokens-per-task *is* tokens-per-call |
| tokens per task, same model, WITH a drill-down | n/a | ≈ 2,850 (two calls, the second carrying a 1,500-char text head instead of 300) | same |
| worst single call in any committed report | 17,754 (`deepseek/deepseek-v4-flash-0731`, live site) | unchanged | same report |
| worst case per run | 3 calls ≈ 53,262 tokens | 3 calls ≈ 53,262 tokens | 3 × the worst committed call; the call *ceiling* does not move |

The +97 tokens are paid by every planning call whether or not it drills; the
second call is paid only by a task that asks for one. Both stay inside the
100k run budget with the margin above, and the `fast` suite stays at
$0.0000 — the drill-down is exercised through the stubbed planner boundary
like every other planning behaviour here.

The "after" row is arithmetic over committed measurements, not a measured
after-run: measuring it directly means a `full`-suite run against a paid
model, which this milestone did not spend. The gate that WAS run is `evals/report/20260822-235208-fast.json` — 131/131, score 1.000, cost $0.0000 — together with
`evals/report/20260822-235232-invariant.json` (41/41).

## Rejected

**Raise `MAX_ELEMS`.** `observe.py`'s own comment already rejected this once,
at M6, for the chrome half of the same problem: it moves the cliff to the
next larger page and spends planner tokens on elements nobody asked about.
It is also the *wrong shape* — the budget is a per-page constant and the
question is per-task. `observe-cap-hides-the-answer-element` is tagged
`invariant` specifically so that "fix" turns the suite red.

**A second observation channel — e.g. attaching the full page text to the
replan note.** It would disclose the same characters without disclosing which
element carries them, so the planner would still have nothing addressable to
target; and it would put the whole page in every replan prompt, taxing every
failure recovery for the benefit of the few that need more of the page.

**Progressive disclosure of the tool set (MCP, lazy tool catalogues).**
Rejected in `prompts/015` with the numbers above: under 100 tokens saved, and
it reintroduces "the planner did not know X existed" — the one failure mode
this repo's closed-world executor makes impossible today.

**An LLM pass that summarises or picks the relevant part of the page.** It
would put a second stubbed LLM inside the offline gate (the fast suite stubs
exactly one boundary at $0.00), and it has no more ground truth than the
planner it feeds. The same objection `prompts/015` recorded against a
debating critic.

## Consequences

**Declared, not guessed at** — `docs/support-matrix.md` D27:

1. A drill-down only helps when the planner can *name* a container that the
   capped observation actually shows. Where a page exposes no content roles
   at all, there is nothing to aim at. Measured on
   `quotes.toscrape.com/js` by hand probe (2026-08-22, one page load, $0.00 —
   the sweep itself has no committed report; the case results cited below do):
   the page-level
   observation is 11 elements, and re-observing every one of the ten
   resolvable containers among them — heading, three links, `navigation`,
   `list`, `listitem`, `contentinfo`, two footer links — discloses zero quote
   content, with `Albert Einstein` absent from all ten scoped text heads while
   present in the 1,499-character body. **D7 stands, unchanged**, and
   `live-quotes-js-role-tier-blind` keeps its honest marker: it still reports
   `success` with `"Next →"`, `answer_is_known_wrong: true`, and still passes
   (`live` suite 9/9 after this change,
   `evals/report/20260822-234757-live.json`). One earlier `live` run on this
   branch went 8/9 and is not this change: `openlibrary.org` did not answer
   inside the 20s navigation budget, so `live-ol-search-a11y-invisible` ended
   `failure:nav` before a locator was ever resolved. The same suite, unchanged,
   was 9/9 two minutes later and `curl` answered that host in 0.88s — a
   third-party outage, not a result about this system, and its history line is
   in `evals/report/history.jsonl` either way.
2. If the drilled subtree is itself larger than `MAX_ELEMS`, the same cliff
   recurs one level down. No fixture demonstrates it; the text head is the
   only thing that still reaches past it, and nothing here makes the
   drill-down recursive.
3. The planner deciding *when* to drill is unmeasured, like every other
   planning behaviour in this repo (§7 of `docs/analysis.md`, item 1). Every
   plan in the suite is hand-written, so what these cases grade is the
   disclosure — `observe-drilldown-past-max-elems` asserts, per planner call,
   that the answer string was absent from the first observation and present
   in the second — not the planner's judgment about asking for it.
