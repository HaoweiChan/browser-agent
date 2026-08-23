# Task 1 milestones — pr-loop queue

Working set only: Queue + Debt here, merged work is a
one-liner in `tasks/DONE.md`. Block format and protocol: the `pr-loop`
plugin skill; list unblocked tasks with
`python3 "$CLAUDE_PLUGIN_ROOT"/skills/pr-loop/scripts/ready.py` (repo root).
Milestone-level only (ADR-001) — micro-tasks stay in the session. Reviewer
evidence tags reference `docs/product/assignment-requirements.md` §E1–E5.
A-phase hour guard: +12h (Reopen note below). Dependency rule: a block with
no `Depends:` line is unblocked — any set of unblocked Queue tasks can run as
parallel pr-loop sessions on their own `task/<id>` worktree branches.

## Queue

### M31 — Plan lint: a superlative task with no enumerating step is sent back before the browser moves            [status: pr]
Depends: M10
Origin: PR #25 finding 3 — correct-answer rate 2/8 (25%) at M5 → 1/7 (14%)
at the M10 probe — and the discussion it triggered (`prompts/015`). PR #25
closed the aggregate hole on the *verifier* side: `aggregate_needs_comparison`
fails closed on every superlative question without ground truth, and its own
comment says why — "the plan vocabulary has no comparison primitive to have
gotten it right WITH" — with the false-refusal cost declared as D22. This
block is the planner-side half: stop emitting the plan that guard exists to
catch, and give the planner the primitive so the guard can relax.
Spec: (1) one new step `extract_all` — every match of a target, answer is a
list; rank/compare/count stays in code (answer assembly + verifier), never in
the LLM. (2) A deterministic, site-agnostic (rule 6) plan lint between plan
and first action: task matches the aggregate shape (reuse `_AGGREGATE` —
one regex, two callers, same ceiling as T-R31) and the plan has no
enumerating step → do not execute; replan once with a note naming the gap,
through the existing replan budget and no-progress guard. Not an LLM critic:
structural not behavioral, fast suite stays $0 — the ADR says why a
debater was considered and rejected.
Acceptance: a case where the first plan lacks an enumerating step is watched
red first (rejected before any action — `actions` spent = pre-plan nav only);
a fixture twin of probe #3 (most-quoted author) goes green against ground
truth; D22 is re-measured and restated, not deleted; replan rate published
per D7.
Acceptance AMENDED at PR #29 R4 (reviewer finding, amend route chosen by the
orchestrator): the original line also required `live-books-cheapest-travel` to
go green. It does not, and the amendment records why rather than hiding it.
That case is `full`-tagged — a real planner call against a real site — so
running it spends money, and stubbing it is forbidden (hard rule 4); it has
been declared unrun since M6 and still is. Worse for the milestone's own
thesis, its wording ("In the Travel category, find the cheapest book and tell
me its exact price") matches neither `_AGGREGATE` nor therefore the plan lint
nor the code-side reduction, so M31's central mechanism provably cannot fire on
it. What IS proven offline: the reduction gets that exact case right on its own
ground truth (`rank-reduces-enumeration-in-code` row 1, the eleven hand-verified
Travel prices reducing to £23.21), and the enumerate-then-rank path end to end
on a superlative task (`probe3-quotes-most-quoted-author`), and — since PR #29
R9 — the reduction itself on that exact wording end to end
(`extract-all-cheapest-wording-still-reduces`). The residual is narrower than
the first version of this amendment said: such a task IS reduced when the plan
enumerates; what is missing is the lint that would make it enumerate, because
`_AGGREGATE` needs BOTH halves to match — a `which|what|who` frame AND a word from {most, least, fewest, highest, lowest, greatest} — and the frame alone is not enough: `verifier-catches-listing-dump`'s own committed task, "Which product is the cheapest, and what is its price?", has the frame and still returns `is_aggregate(...) is False`, because `cheapest`-style price wording lives only in `_RANK`. That is T-CHEAPEST-WORDING below.

### M32 — Observation drill-down: the planner can ask for a deeper view instead of planning against 60 elements of chrome            [status: pr]
Origin: `prompts/015`. README's `live-quotes-js-role-tier-blind` ("readable
but unplannable") and M10 probe #4/#5/#7, where the value was verbatim in the
page text the agent captured and absent from the a11y elements the planner
was shown (`docs/analysis.md` §8a-2).
Spec: progressive disclosure of the *page*, not the tool set — the whole
vocabulary is ~524 tokens of system prompt and disclosing it lazily saves
nothing while breaking the closed-world guarantee. One new action `observe`
with a `target` subtree: the executor re-runs `observe()` scoped to that
subtree with the full `MAX_ELEMS` budget and a longer text head, and the
result reaches the replanner through the existing observation+note path.
Costs one planning call, bounded by `MAX_REPLANS`. No site knowledge.
Acceptance: an offline fixture case where the answer element sits past
`MAX_ELEMS` in document order goes from `failure:locate`/dump to correct, red
first; `quotes.toscrape.com/js` keeps its honest marker if it is still
unplannable; tokens-per-task measured before/after from committed reports
and stated (must stay inside the 100k run budget).

### M33 — Ablation arm: per-step tool-calling planner vs evolving-prefix, same eval set, numbers decide            [status: todo]
Origin: `prompts/015` — "would an MCP / tool-calling loop raise completion?"
`docs/architecture/task1-overview.md` chose B over A (LLM-per-step) on
reasoning, never on a measurement; M9's ablation mechanism (ADR-010,
`evals/ablation.py`) now exists and varies only the model.
Spec: a second planner mode behind the unchanged
`planner(task, url, obs, note)` boundary — OpenRouter native `tools=[…]` with
the same step schemas as function definitions (four when this block was
written; five since M31 added `extract_all`), one model call per step,
fresh observation after every step, step cap = `RUN_BUDGETS["actions"]`. No
MCP: same process, no external client — MCP is transport, not capability.
Every tool call lands in the trace record so the UI and verifier read the
same evidence pipeline. Driven by `evals/ablation.py --planner toolcall`
against the deployment on the M9 task set plus one probe-#3-shaped task;
report as `-ablation.json` under the ADR-012 policy; `fast` stays on
`stub_planner` — the arm is paid-only.
Acceptance: `docs/analysis.md` §9 gains a per-arm row set (correct-answer,
success, $/task, tokens, ms, planner calls) built from a committed report and
guarded by `analysis-ablation-table-not-estimated`; an ADR that either keeps B
with the measured gap or amends the A-vs-B table — decided by the numbers,
with the fast-suite/inspectability cost of A stated either way.

### M36 — responsiveness is judged by an LLM, because four structural mechanisms have failed            [status: pr]
Origin: PR #30 post-merge confirmation (2026-08-22, deployed build `2e94bed`); owner's call on the mechanism
Spec: M34's `not_page_furniture` compares a 20-char context window on the
assumption that site chrome carries its neighbours wherever it recurs. On
books.toscrape.com the banner is preceded by page-specific text (a result
count), so the windows differ and furniture passes. 6 wrong-answer-as-success
in 9 deployed runs (`8ffc6fdc`, `4649a0c5`, `2f89cec2`, `81fe507f`, `8896c5ec`,
`f2c00566`), zero clean correct answers on the defect task. That is the fourth
mechanism falsified by real input and the third falsified at a shape its authors
had declared acceptable (`log into`, `delete all`, `which...most`, now the
context window). The owner's decision is to stop betting on structure and judge
responsiveness with an LLM: does this answer actually answer this question.
The deterministic checks stay and run first — the judge is the last rung of the
escalation ladder, not a replacement for it.
Acceptance: the real-site shape (chrome preceded by page-varying text) is an
adversarial case watched red first; no terminal non-failure status can carry an
answer the judge rejects; the judge fails CLOSED on error, timeout or missing
key, and a case proves it; the `fast` suite still makes zero paid calls with the
judge stubbed at its own injection boundary, and a case proves the boundary
holds; a prompt-injection case proves page text cannot talk the judge into
certifying a wrong answer; per-run judge cost and per-stage hit-rate land in the
`evals/report/` entry; repeated runs on the deployed build show zero
wrong-answer-as-success before criterion 5 moves.
Out of scope: extraction quality (M28), planner-side lint (M31). Do not remove
M34's deterministic checks — they are cheaper and they run first.

## Debt

### T-M32-10 — `report-citations-resolve` checks that a citation resolves, never that the number beside it is the report's            [status: todo]
Origin: PR #34 R17.
Spec: ADR-020 claimed "`live` suite 9/9 after this change" and cited a report
whose `score` is 0.889 — 8/9, with `live-ol-edition-title` failing. The claim
and the artifact disagreed and nothing could see it, because
`report-citations-resolve` grades that `evals/report/<id>.json` EXISTS. That is
the repo's standing one-direction gap (T-R19 is the same shape for the reverse
direction), and it is what let a green claim hang on a red artifact inside a
review's own surface. The citation is corrected; the mechanism is not.
Repro: point any "N/N" prose at a report whose `score < 1.0` and run
`--suite invariant` — nothing goes red.
Acceptance: a citation adjacent to a pass-rate claim must resolve to a report
whose score supports it — the parse only has to be good enough to catch
"9/9 ... <red report>", not to understand arbitrary prose — watched red against
the ADR-020 sentence as it stood before this fix.

### T-M32-11 — a fixture case with an empty `expect` crashes the adapter on a failing run            [status: todo]
Origin: PR #34, found while reproducing R16 with the reviewer's own probe.
Spec: `_run_fixture_case` ends with `v = audit["verdict"] if audit["layer"] > 1
else result["verdict"]["verdict"]`. A run that fails before grading carries
`result["verdict"] is None`, and with no `expect` the audit stays at layer 1, so
the subscript raises `TypeError` and the case reports a traceback instead of the
failure it just produced. Every committed case has a non-empty `expect`, so this
only bites ad-hoc probes — which is precisely the tool people reach for when
hunting defects, and it turns "the run failed loudly" into "the harness broke".
Repro: `_run_fixture_case({... "expect": {}})` on any plan that ends
`failure:task`, e.g. the R16 reproduction after its fix.
Acceptance: a failing run with no expectations reports its status, not a
traceback.

### T-M32-3 — act-failure coverage costs 4.6s of a suite that already straddles its ceiling            [status: todo]
Origin: PR #34 R1 (the fix, not the finding); cost model corrected per PR #34 R11.
Spec: an act failure is only expensive when it is a POSTCONDITION failure. Those
run `check_state`'s whole settle loop (10 x 200ms) before returning False, so
they cost a full `SETTLE_BUDGET_MS` each: `observe-cannot-launder-noop-action`
2.29s, `observe-drilldown-cannot-launder-noop-action` 2.35s, and the three that
predate this PR (`recovery-replan-postcondition` 2.33s,
`recovery-label-requires-strategy-change` 2.32s,
`replan-cannot-launder-noop-action` 2.29s). An act failure raised INSIDE
`execute` never reaches `check_state` at all and is free — a fill readback
mismatch is instant, a click timeout is 10s for a different reason. The first
version of this block claimed the settle loop was the price of every act
failure; that was wrong, and `observe-drilldown-cannot-launder-unchecked-action`
now uses the cheap shape (~0.15s, a fill past the search box's `maxlength`).
The two 2.3s cases keep the postcondition shape because it is the only one that
produces `page_changed: false` — the cheap shape produces `null`, and PR #34 R8
is precisely what happens when those two values are not both pinned.
Repro: `evals/report/20260822-185625-fast.json`, sort `results` by `seconds`.
Acceptance: either a cheaper way for a case to declare "this postcondition will
not hold" (a per-case settle bound is the obvious one, and it must not weaken
the production budget), or an explicit ruling that act-failure coverage is worth
its share of the ceiling — recorded wherever the open wall-clock decision lands
(PR #29 R21). Do NOT fix it by shortening SETTLE_TRIES: that is a production
budget with `nav-load-event-never-fires` behind it.

### T-M32-1 — the reviewer UI has no phase for an `observe` step            [status: todo]
Origin: M32 (ADR-020), found while adding the drill-down.
Spec: `phaseFor(s)` in `src/browser/server.py` maps `navigate` -> "browser" and
`extract` -> "verification" and everything else to "action". An `observe` step
reads the page and changes nothing, so showing it as "action" tells a watcher
the agent is acting when it is looking. One line, but that file is M35's
(the visitor-facing console) and this PR must not collide with it.
Repro: run a task whose plan starts with an `observe` step and watch the SSE
progress bar — the "action" phase lights up before anything is done.
Acceptance: `observe` maps to a reading phase, and `ui-execution-progress`
covers the mapping.

### T-M32-2 — the post-edit invariant hook runs in the wrong worktree            [status: todo]
Origin: M32, found while implementing.
Spec: `.claude/hooks/post-edit-invariant.sh` cds to `$CLAUDE_PROJECT_DIR` and
prefers `.venv/bin/python` there. When the session is working inside a
`.claude/worktrees/` sibling, that variable still points at the ORIGINATING
worktree, so the hook grades a different checkout than the one being edited,
and with a bare `python3` if that checkout has no `.venv` — which reports
`ModuleNotFoundError: No module named 'fastapi'` for 14 of 38 invariant cases
on every single edit under `src/`. Loud, so nothing was silently wrong, but the
feedback it gives is about neither the edit nor the tree.
Repro: edit any file under `src/` from a worktree whose parent checkout has no
`.venv` and read the hook's output.
Acceptance: the hook resolves the tree from the edited file's path (or from
`git rev-parse --show-toplevel` on it) rather than from `$CLAUDE_PROJECT_DIR`.

### T-M32-4 — the `analysis_section1` grader asserts presence, not absence of contradiction            [status: todo]
Origin: PR #34 R10
Spec: `docs-numbers-are-derived`'s new `analysis_section1` block reads the whole
of `docs/analysis.md` and asserts each derived string is `in text`, with no
section scoping (unlike `analysis_coverage`, which slices `## 6. Coverage`..`## 7.`)
and no uniqueness check — so a contradicting sentence beside the correct one
stays green. Verified: inserting "Actually only 170 browser actions run, and 12
of the 119 cases open a browser." above the correct "202 browser actions in a
`fast` run" leaves the case PASSING. Strictly a narrower instance of `T-R29`,
which already owns this weakness for the same case's other halves — fix it once,
for every half, there.
Repro: insert the contradicting line into `docs/analysis.md` §1 and run
`_run_doc_counts_case(json.load(open('evals/adversarial/docs-numbers-are-derived.json')))`
-> `passed: True, wrong: []`.
Acceptance: the §1 block scans only §1, and/or asserts no other
`\d+ browser actions` / `\*\*\d+ of the \d+\*\* cases` string appears in the
section; the contradicting-line probe above reddens.

### T-M32-5 — README publishes 28 wall clocks no committed report backs            [status: todo]
Origin: PR #34 R12
Spec: `README.md:68`, `:71-73`, `:78`, `:85`, `:90`, `:96` and `:99` publish
wall-clock numbers that `docs-numbers-are-derived` does not recompute — its
`readme_quotes` are only the three case-count strings, and `where_it_stands`
only recomputes the fenced baseline block. All of these predate PR #34 (the M32
band that round-1 finding R4 named IS deleted), so they are not M32's to fix,
but they are the same class of published-number drift R4 and R5 were about and
the repo has now hit that class three times in one PR.
Repro: `grep -n '59.62\|58.96\|59.77\|68.1s\|89.62s\|63.3s' README.md` and
try to resolve any of them to a report in `evals/report/`.
Acceptance: each remaining README wall clock names the report it came from and
is recomputed by `docs-numbers-are-derived`, or is deleted.

### T-M32-6 — the recovery-label clause credits the drill-down path with a label it never sets            [status: todo]
Origin: PR #34 R14
Spec: `specs/001-browser-contract.md:130-135` says the `recovery` label and the
`superseded_by` pointer "skip past an `observe` and land on the next attempt of
any other kind, which is usually the `extract` the drill-down was asked for",
and cites `recovery-replan-postcondition` as the shape where that extract is
the only step. Both halves conflate two paths: `pending_recovery` is assigned
at `src/browser/agent.py:833` only, inside family 2's act->replan branch — the
drill-down branch (`agent.py:743-791`) sets only the note — and
`recovery-replan-postcondition`'s stub plans contain no `observe` at all, so
nothing skips past anything there. ADR-020 §2 carries the same conflation.
The code is correct and graded; only the prose is imprecise.
Repro: `grep -n 'pending_recovery' src/browser/agent.py` -> 682, 694, 697, 833;
only 833 assigns `"recovery"`, and it is unreachable from the drill-down branch.
Acceptance: the clause separates the two statements — the label defers past an
`observe` and lands on the next non-`observe` attempt, which in
`recovery-replan-postcondition` is a bare `extract` with no drill-down involved
and in `recovery-label-lands-on-the-extract` is the `extract` the drill-down's
replan returned while a family-2 recovery is in flight.

### T-M32-7 — the contract's laundering clause omits the `page_changed: null` half            [status: todo]
Origin: PR #34 R15
Spec: `docs/support-matrix.md` D25 and `specs/decisions/ADR-020` were both
rewritten to say that "changed nothing" covers an attempt that ran and moved
nothing AND one that never got far enough to be compared, citing all three
laundering cases. `specs/001-browser-contract.md:145-150` was left at the
earlier wording: no null half, and no
`observe-drilldown-cannot-launder-unchecked-action`. Three documents state the
same rule and one of them is now behind. Nothing grades the contract's case
citations — `support-matrix-cites-real-cases` covers the matrix, not
`specs/001` — so they can drift silently, which is how this happened.
Repro: `git diff 5a88b9c..HEAD -- specs/001-browser-contract.md docs/support-matrix.md`.
Acceptance: `specs/001-browser-contract.md:145-150` states the null half and
cites the third case, matching D25 and ADR-020 word for word on the predicate;
ideally a grader covers the contract's case citations the way
`support-matrix-cites-real-cases` covers the matrix's.
### T-R34 — the band grader checks equal-derived-ceiling, not `published >= ledger max`            [status: todo]
Origin: PR #29 R24
Spec: R24 found three things. Two are fixed in the M36 merge (`b578b15`): README
no longer publishes a property the grader does not implement — it now states
what `_check_published_band` actually checks (case count matches, published
maximum derives the SAME ceiling as the ledger maximum, committed ceiling >=
the rule applied to that maximum) — and both README's band table and ADR-019's
band lines are now regenerated from `evals/report/history.jsonl` by script, so
the published run lists are the ledger's own and the derivation sentences
multiply the ledger maximum at the shipped case count.
What remains is the judgement call R24 raised: property 2 is
`rule(published) == rule(ledger max)` rather than `published >= ledger max`.
The weaker form was chosen deliberately (the strict form reddens on ordinary
0.2-0.5s run-to-run variance, which is rot-by-construction one level up), and
it does catch the harmful direction — a band justifying a LOWER ceiling than
the truth. It does not catch a published maximum that is up to ~1.0s below the
ledger's at these magnitudes while still landing in the same band.
Acceptance: either the tighter property is adopted with a regeneration step
that keeps the doc honest without hand-editing (the script that now produces
these lists is the obvious hook), or the trade-off is stated in ADR-019 as a
declared ceiling with the ~1.0s slack named, and a case pins the miss so it is
a decision rather than an artefact of what was convenient to grade.

### T-R35 — three specs files still publish the withdrawn 75s/15s ceilings as current            [status: todo]
Origin: PR #29 R25
Spec: `specs/decisions/INDEX.md:11` (rewritten by 3699b87) reads "fast 75s local / 90s CI"
while the same commit set `evals/run.py:91` to `{"fast": 80, "invariant": 20}` and INDEX:26's
own ADR-019 line says "local `fast` 60 -> 80". ADR-019:10's Amends header says
"(local `fast` ceiling 60 -> 75)", contradicting its own Ruling at :5 (60 -> 80).
ADR-002:8 says "`fast` 80s local / 90s CI, `invariant` 20s local / 20s CI, since ADR-019"
and then, in the same sentence, "then re-measured to 75s at M31 ... `invariant` has had its
own 15s ceiling since ADR-019". T-R25 asserts "All of that is corrected in the line now" — it
is not. Third occurrence of the defect T-R25 exists for.
Acceptance: every ceiling statement in specs/ names 80/90/20/20; ADR-019's Amends header
matches its Ruling; ADR-002's parenthetical stops asserting a live 15s invariant ceiling;
T-R25's Update states what is actually fixed. Ideally one graded row that compares INDEX/ADR
ceiling numbers against `WALL_BUDGET_S`, watched red against the current text.

### T-R36 — `adr-header-and-index` cannot see an ADR file missing from INDEX when another shares its number            [status: todo]
Origin: PR #29 R26
Spec: The duplicate this block was opened for is resolved: main's M34 INDEX line
was restored during the M36 merge, and this branch's two decisions renumbered to
ADR-018 (M31 plan lint) and ADR-019 (wall-clock ceilings) so main keeps 016/017.
What survives is the grader hole R26 named. `_run_adr_header_index_case`
(`src/browser/eval_adapter.py`) computes `sorted(set(adr_nums) - set(index_nums))`,
so if two files share a number and only one is indexed, the missing entry never
appears in `missing_from_index` — the set collapses it. `duplicated_in_index`
does catch a doubled INDEX line, which is what forced the renumber here, but the
file-side blindness is untested and is what let R26's dropped M34 line survive a
merge in the first place.
Acceptance: `_run_adr_header_index_case` compares files to entries per FILE (or
fails on a duplicated ADR number on disk), watched red against a tree with two
same-numbered ADR files and one INDEX line. This is the general form
T-ADR-NUM already tracks — fold it in if that block is promoted first.

### T-R37 — a plural aggregate request is now refused as if it asked for one item            [status: todo]
Origin: PR #29 R27
Spec: `src/browser/agent.py:200-221` refuses whenever `is_aggregate(task)` and the single
`extract_all` does not carry `rank is True`. `_AGGREGATE` is
`\b(which|what|who)\b.{0,80}\b(most|least|fewest|highest|lowest|greatest)\b`, which matches
"Which products in this catalogue have the lowest prices?" — not a which-ONE-of-a-set question.
End-to-end on shop.html with the plan from `plan-lint-refuses-a-declared-non-comparison`:
`status failure:task`, `answer null`, `budgets.actions 1`, reason "...Declare `rank: true` and
let code do the comparison...", which would return one product for a question that asked for
several. At `117301e` the same input returned the four-row list as success, so this is a
regression introduced by PR #29's round-4 repair. It fails LOUD — a false refusal, not a wrong
answer published as success. ADR-018's justification ("`_AGGREGATE` is narrow and
high-precision: when it matches, code is entitled to contradict a `rank: false`") is falsified
by that one input, and nothing declares the cost.
Acceptance: either the lint's precondition is narrowed so a plural which-question is not treated
as which-one (no new wording regex needed — the existing match already exposes the number), or
ADR-018's "entitled to contradict" paragraph states this ceiling with this exact input as its
evidence, and a case pins the behaviour so it is a decision rather than a side effect.

### T-R38 — `extract_all` rows after the first lose M34's DOM-offset anchoring            [status: todo]
Origin: PR #29 R28
Spec: `src/browser/agent.py:675-676` — `off = (real_offset if v == vals[0] else
_closest_occurrence(body, v, -1))`. Rows 2..n of an `extract_all` get hint -1, plain
first-occurrence, which is the pre-R2-1 behaviour PR #30 R2-1 fixed. `docs/support-matrix.md:67`
(D24) still says the context is "anchored to the actual DOM occurrence it was read from" and
lists three uncaught shapes; this fourth is not among them (only a source comment names it).
`loc.first` is the right call — `loc.evaluate` on a multi-match locator is a Playwright
strict-mode violation — and the row-wise judging claim holds (verify() with two extraction
records fails the set when only the second row's context repeats on the other page). But every
M34 case uses `extract`, so the merged `extract_all` x `other_page_text` path is graded nowhere.
Acceptance: D24 names the residual, or the hint is taken per-row via `loc.nth(i)`; plus one
adversarial case running an `extract_all` across two pages where one enumerated row is chrome,
watched red against a build that judges the set by row 0's evidence.

### T-RANK-MIRROR — a list-shaped task declared `rank: true` truncates to one item, and nothing contradicts it            [status: todo]
Origin: PR #29 R20 (the mirror half; the aggregate half is fixed)
Spec (claim): M31 requires the plan to declare `extract_all.rank`, and code now
contradicts a declaration it can prove wrong — but it can only prove one
direction. `is_aggregate(task)` is narrow and high-precision, so `rank: false`
on a task it matches is refused (`plan-lint-refuses-a-declared-non-comparison`).
There is no predicate for the other direction: a task that asks for the whole
set is not something code recognises, so `rank: true` is obeyed and the answer
is one row where the user asked for every row, reported `success`.
Evidence: `extract-all-declared-rank-obeys-the-plan` pins exactly that — same
task, same fixture and same verb as `extract-all-list-task-keeps-every-row`,
opposite declaration, opposite answer, both green.
Repro: run `extract-all-list-task-keeps-every-row`'s plan with `rank: true`;
answer becomes "Cobalt Floor Rug $18.00" instead of the four rows.
Acceptance: a signal that is not a wording regex over `list`/`every`/`each` —
that mechanism decided this call three times and was backwards each time
(PR #29 R2, R9, R16), so reintroducing it as a decider is explicitly out of
scope. Candidates worth a red-first case: a second declaration the executor can
cross-check against the evidence (e.g. an expected cardinality the enumeration
must satisfy), or an L3 evidence-only check that asks whether one row answers
the question. Until then the residual is that the planner's declaration is
trusted wherever code has no opinion — which is most tasks.
Note: `live-books-cheapest-travel` is the only case that would put this decision
in front of a real planner and it is `full`-tagged and unrun, so there is no
measurement of how often a real model gets `rank` right.

### T-CHEAPEST-WORDING — the plan lint does not fire on price-worded rankings, so nothing sends such a plan back            [status: todo]
Origin: PR #29 R4, restated at PR #29 R9 and R12
Spec (claim): the plan lint (`agent.plan_gap`) is gated on `verifier.is_aggregate`.
`_AGGREGATE` needs BOTH halves to match — a `which|what|who` frame AND a word from {most, least, fewest, highest, lowest, greatest} — and the frame alone is not enough: `verifier-catches-listing-dump`'s own committed task, "Which product is the cheapest, and what is its price?", has the frame and still returns `is_aggregate(...) is False`, because `cheapest`-style price wording lives only in `_RANK`.
So a ranking task worded with `cheapest` is never linted: the planner may answer
it with a single `extract` and the run reports whatever that one element said.
The code-side REDUCTION is not affected — PR #29 R9 moved its gate off
`is_aggregate` and onto `_RANK` plus an enumerate-request test, so an
enumeration for such a task is reduced correctly (`rank-reduces-enumeration-in-code`
row 1, `extract-all-cheapest-wording-still-reduces`). What is missing is only
the push: nothing makes the planner enumerate in the first place.
Evidence: `is_aggregate("Which product is the cheapest, and what is its price?")`
-> False, on a task committed in this repo since M7. Same for
`live-books-cheapest-travel`'s "In the Travel category, find the cheapest book
and tell me its exact price."
Repro: `plan_gap("In the Travel category, find the cheapest book and tell me its
exact price.", [{"action": "extract"}])` -> None.
Acceptance: either widen `_AGGREGATE`'s second half to the price vocabulary with
a watched-red case — and prove it does not drag the fifteen shop-fixture cases
whose task says "name the cheapest product" into a lint they have no reason to
meet, which is why M31 did not widen it — or run `live-books-cheapest-travel`
with a key and record what the planner does now that the verb exists.
Note: the same regex ceiling T-R31 names for the verifier guard, with one more
consumer. `_RANK` (the reduction) and `_AGGREGATE` (the lint and the verifier
guard) are deliberately separate vocabularies; this block is about the second.

### T-EXTRACT-ALL-VOLUME — `extract_all` has no cap on matches and stores one full evidence window per match            [status: todo]
Origin: PR #29 R7
Spec (claim, reviewer's evidence carried verbatim): `extract_all` has no cap on
match count, and each match stores its own up-to-2000-char evidence window, so
one enumeration multiplies the page text by the number of matches in
`result.json` and in the API/SSE payload.
Evidence (verbatim): src/browser/agent.py extract branch:
`extractions.extend({"value": v, "page_text": evidence_window(body, v, anchor), ...} for v in vals)`
with `PAGE_TEXT_KEEP = 2000` (agent.py:41) and no bound on `len(vals)`.
`RUN_BUDGETS` caps actions/tokens/ms, not extraction volume. Measured:
`extract_all {role: link}` on `quotes.html` yields 13 records each carrying its
own window of the same body.
Acceptance (verbatim): Either a declared cap on enumerated matches (loud when
exceeded, like every other budget here) or one shared evidence window per
`extract_all` step, with a case pinning the record count for a large
enumeration.
Note: the per-value window is not incidental — `grounded` and `not_a_dump` are
judged per extraction, so collapsing to one shared window changes what those
checks mean and needs its own red-first case, which is why this is not a
one-line fix folded into PR #29.

### T-CASE-CITES — case ids cited from `src/` and from case files resolve against nothing            [status: todo]
Origin: M31 cold review (secondary finding), the general form of T-R32.
Spec (claim): `support-matrix-cites-real-cases` resolves backticked case-id
tokens in `docs/support-matrix.md` against `evals/`, and nothing resolves the
same tokens anywhere else. Code comments in `src/browser/verifier.py` and
`src/browser/eval_adapter.py` and the `provenance`/`triage` prose inside case
files all cite case ids heavily, and a renamed or folded-away case leaves them
pointing at nothing with the whole suite green.
Evidence: M31 folded one case into another mid-milestone and left three live
references to the dead id — two in `src/`, one in a case file — found by cold
review, not by the suite.
Repro: rename any case file and grep for its old id under `src/` and
`evals/*/*.json`; `--suite invariant` stays green.
Acceptance: one case resolves case-id citations across `src/` and the case
files themselves (the support-matrix half already exists), watched red against
a deliberately dangling id first. Pairs naturally with T-R32, which is the same
mechanism for D-numbers.

### T-RANK-UNITS — `verifier.rank` compares enumerated numbers without checking they are commensurable            [status: todo]
Origin: M31 implementation (`specs/decisions/ADR-018-m31-plan-lint.md` Decision 2),
found while writing the reduction, out of that milestone's scope.
Spec (claim): `rank` reduces an `extract_all` enumeration numerically whenever
every value parses as a number, comparing on the Decimal alone — so a list
mixing currencies ("£23.21", "$18.00") or units ("2.5%", "18") ranks as if the
values were commensurable, and returns a confident winner. `answers_match` in
the same file already refuses that comparison for exactly this reason
(`verifier-sign-currency-percent`), which is what makes the omission a real
inconsistency rather than a hypothetical.
Evidence: `_num_parts` returns `(value, currency, unit)` and `rank` reads only
`[0]`; nothing anywhere refuses a mixed list.
Repro: `rank("which is cheapest", ["£23.21", "$18.00"])` -> "$18.00", no refusal.
Acceptance: a mixed-currency / mixed-unit enumeration is refused the way a tie
already is (`ValueError` -> `failure:semantic`), watched red first. Deliberately
NOT done in M31: no enumeration in this repo produces one — every `extract_all`
in the eval set reads one column of one page — and the ponytail comment on
`rank` names the ceiling and this upgrade path.

### T-R32 — D-number citations in code and docs are not machine-checked            [status: todo]
Origin: PR #25 R5
Spec: `support-matrix-cites-real-cases` resolves backticked case-id tokens
against `evals/`, but not bare `D21`/`D22`-style numeric references against the
`docs/support-matrix.md` table. `src/browser/agent.py:64`, `docs/analysis.md`
§8a-2 and `src/browser/verifier.py` now all cite D-numbers, so a future
renumbering or row deletion leaves those citations dangling with nothing red.
This is PR #25 R1's defect in its general form — R1 was one uncited claim; this
is the mechanism that lets the next one through.
Repro: renumber or delete the D21 row in `docs/support-matrix.md` and run
`--suite invariant` — nothing goes red despite `agent.py` citing a dead D21.
Acceptance: a case resolves bare D-number citations against the support-matrix
table and is watched red against a deliberately broken D-number first.

### T-R33 — the judge's certify parser has no provider-side schema enforcement, so the strict boolean check is trusted on hope, not guaranteed            [status: todo]
Origin: PR #33 R3 (MEDIUM, routed debt)
Spec (claim): `live_judge`'s request to OpenRouter carries no `response_format`
constraint, so nothing GUARANTEES `certify` arrives as a JSON boolean rather
than a string, a number, or absent entirely — the strict `is True` check
(docs/support-matrix.md D26) is the correct posture given that, but it means
the app is hoping the model's own formatting habits stay boolean-shaped
rather than enforcing the shape at the request level.
Evidence: `src/browser/judge.py`'s `payload` in `live_judge` sets `model`,
`messages`, `usage: {"include": True}` — no `response_format`. OpenRouter (and
most providers behind it) supports `response_format: {"type": "json_object"}`
for syntactically-valid JSON, and some models additionally support
`{"type": "json_schema", "json_schema": {...}}` for a typed schema (certify
as an actual boolean). Neither is attempted.
Repro: n/a — this is an absence, not a reproducible defect; nothing here
demonstrates the parser actually receiving a malformed shape from a real
call, because there is no `OPENROUTER_API_KEY` in this environment (same
constraint D26 states for the ceiling itself).
Acceptance: add `response_format` to the request (`json_object` is the safe,
widely-supported floor; `json_schema` with a strict `{"certify": boolean}`
schema is the real fix if `deepseek/deepseek-v4-flash-0731` supports it) and
verify it against a live call before trusting it — an untested schema
constraint added here would be exactly the kind of unwatched change PR #33
R3 warned against, just moved one layer down.
Orchestrator note: MEDIUM in origin, routed to debt rather than fixed inline
because it cannot be verified in this environment (no key) and a wrong or
unsupported `response_format` value would fail the live path silently worse
than today's absence of one. D26 stands regardless of how/whether this is
picked up.

### T-R30 — the widened SCOPE_BLOCK determiner regex over-refuses informational/hypothetical delete questions            [status: todo]
Origin: PR #25 R3 (LOW, routed debt)
Spec (claim): the widened determiner regex over-refuses informational/hypothetical
questions about deletion that use the same verb+determiner adjacency as a real
command.
Evidence: SCOPE_BLOCK matches 'Can you explain how to delete our test entry?' and
'What happens when I delete all the drafts?' — both informational. The pinned
case l5-refuse-delete-determiners tests three informational rows, none combining
an interrogative frame with an adjacent determiner.
Repro: `SCOPE_BLOCK.search('What happens when I delete all the drafts?')` -> match.
Acceptance: either accept as consistent with the already-declared over-refusal
tradeoff and note it for the delete clause, or add a case.
Orchestrator note: LOW, and in the safe direction — same shape as the
already-declared login over-refusal. Debt.

### T-R31 — the aggregate-superlative regex misses phrasings outside the which/what/who + keyword shape            [status: todo]
Origin: PR #25 R4 (LOW, routed debt)
Spec (claim): the aggregate-superlative regex misses phrasings that don't use
which/what/who alongside the exact keyword list, so the same defect class can
recur one step removed from the probe's wording.
Evidence: `_AGGREGATE` requires `\b(which|what|who)\b.{0,80}\b(most|least|fewest|highest|lowest|greatest)\b`;
'Rank the books by price and give me the top one.' does not match.
Repro: `_AGGREGATE.search('Rank the books by price and give me the top one.')` -> no match.
Acceptance: already disclosed by the ponytail comment in verifier.py; logged for
completeness, not blocking.
Orchestrator note: LOW and already acknowledged in-code. Debt — and the honest
name for the ceiling this PR ships.


### M28 — extraction gives up and dumps the whole page instead of failing cleanly or isolating the value            [status: todo]
Origin: M10 second held-out probe, finding 3 (`docs/analysis.md` §8a-2)
Spec: on three of the probe's canonical-round tasks (#4 star rating in a CSS
class attribute, #5 Tokyo 2020 population on a real Wikipedia infobox, #7
Open Library's first publication year for a search result), the correct
value was present verbatim inside the page text the agent itself captured —
`star-rating Three`, the infobox population figure, "First published in
1965" — but the run returned `failure:semantic` with a multi-hundred/
multi-thousand-character raw page dump as the `answer` field instead of
either isolating the value or failing with `answer: null`. This is graded a
failure, not a wrong success, so it does not implicate the inviolable
property (`not_a_dump` never sees it: the check only fires on `success`), and
it is out of the two-defect scope M10's repair was bounded to.
Acceptance: a case pins the "data was captured but answer is a page-text
dump on failure" shape red first, then either the extraction step tries a
narrower isolation before giving up, or `failure:semantic`'s `answer` field
is null'd rather than carrying the dump — reviewer's call which is correct.

### M11 — Live-drift snapshot replay            [status: todo]
Origin: M8's SHOULD item, left open at the M8 merge (PR #12)
Spec: replay committed live-page snapshots so live-site drift is detected
without network. Acceptance: a drifted snapshot turns a case red offline.

### T-ADR-NUM — ADR numbers are allocated by "next free", and this branch has been renumbered three times            [status: todo]
Origin: PR #20 (no finding id — discovered by doing it, three times)
Spec: an ADR takes the next free number when it is *written*, and concurrent
branches all see the same next free number, so whichever merges last renumbers.
This branch's wall-clock ADR was written as ADR-010 and shipped as ADR-013:
010 -> 011 when M9's ablation ADR merged first, 011 -> 012 when the readiness
ADR (PR #19) merged, 012 -> 013 when the report-policy ADR (PR #22) merged —
three forced renames in one PR, each while the branch was otherwise finished.
Each rename rewrites the same string across ~12 files: the ADR itself, ADR-002
(status header, Amended-by, Ruling, Enforced-by, Decision 4), ADR-009's closure
note, `specs/decisions/INDEX.md`, `README.md`, `docs/analysis.md`,
`docs/support-matrix.md`, `tasks/TODO.md`, two eval case files, and comments in
`evals/run.py`, `src/browser/eval_adapter.py`, `src/browser/agent.py`.
The part that makes this worth a block rather than a shrug: **once several
renames have layered, a sweep is no longer verifiable by grep alone.** Every hit
for the old number looks plausible because the text around it was written by an
earlier sweep, and the tree now contains three live ADR numbers within two of
each other (011 readiness, 012 report policy, 013 wall clock) whose references
are told apart only by reading each line. Verifying the third sweep meant
classifying every `ADR-01[123]` hit by hand against which ADR it means. A
mechanical check would not have to.
Acceptance: a number-allocation rule plus a gate-time guard, not one or the
other — reserve-on-open (a branch claims its number when the PR opens) or
date-based ids remove the collision, and an `adr-header-and-index` extension
that refuses a duplicate number, a gap in the sequence, or an INDEX entry whose
number does not match its file makes a botched sweep red instead of plausible.
Do not design it in this PR.
Fourth instance, and the first outside ADR numbers: PR #23's tinboker ADR was
written as ADR-013 and shipped as ADR-014 (PR #20's wall-clock ADR took 013
first), and the *task id* collided the same way — PR #21 R1 logged a soak debt
as M18 while PR #23's branch, PR title and review artifacts were already M18,
so the debt block was renumbered to M27 on merge. "Next free" fails for every
id sequence in this repo, not just `specs/decisions/`; whatever rule lands here
should cover `tasks/TODO.md` ids too.

### T-R13 — the module tail that turns `main()`'s return into an exit code is ungraded            [status: todo]
Origin: PR #20 R13 (LOW, routed debt by the reviewer, which approved alongside it)
Not specific to M12's ceiling: the same tail gates the pre-existing invariant and
regression rules identically, and nothing in PR #20's diff made it worse. The
wording half of its acceptance was taken in PR #20; this is the mechanism half.
Spec (claim): the R8 repair grades `main()`'s return value but not the module
tail that turns it into a process exit code, so `evals/run.py:179` changing from
`sys.exit(main())` to `main()` silently disables the wall-clock gate (and the
invariant and regression gates with it) while `fast-wall-clock-budget` stays
green. Evidence: `evals/run.py:178-179` is the only thing CI and
`.githooks/pre-commit` (`python -m evals.run --suite fast`) actually read, and
`src/browser/eval_adapter.py` `_main_exit_code` calls `R.main()` in-process,
never the `__main__` guard. Measured in a scratch copy: with
`WALL_BUDGET_S = {"fast": 60, "invariant": 0}` and the tail unmodified,
`python -m evals.run --suite invariant --no-report` exits 1; with the tail
changed to a bare `main()` the same over-budget run exits 0, and
`run_case(fast-wall-clock-budget)` still returns
`{'passed': True, 'main_exit': [{54.35, exit 0, got 0}, {79.02, exit 1, got 1}]}`.
Repro: cp -a the worktree to a scratch dir; `sed -i '' 's/sys.exit(main())/main()/'
evals/run.py`; `python -m evals.run --suite fast --no-report; echo $?` on an
over-budget tree -> 0, and
`python -c "import json,src.browser.eval_adapter as A; print(A.run_case(json.load(open('evals/adversarial/fast-wall-clock-budget.json')))['passed'])"`
-> True. Acceptance: the case drives the process — one
`subprocess.run([sys.executable, '-m', 'evals.run', ...])` over-budget probe
reading `returncode` — rather than calling `main()` in-process.

### T-R12 — `--update-baseline` records a baseline over the wall-clock ceiling, silently            [status: todo]
Origin: PR #20 R12 (LOW, routed debt — what should happen there is a repo-owner call)
Spec: `evals/run.py:157-161` writes the baseline and `return 0` at line 161; the
`over_budget` check is at line 166. A `fast` run measuring 79.02s therefore exits
0 with only `[eval] baseline['fast'] = 1.000 (recorded)` on stdout and no
`OVER BUDGET` line anywhere, even though the same run without the flag exits 1.
So the one command CLAUDE.md sanctions for a deliberate baseline move records it
on a tree that is over the ceiling and says nothing. ADR-013 Decision 2 describes
the ceiling as "the same shape as the invariant-100% rule beside it" — which sits
at line 162 and is bypassed by the same early return, so the shape does match, but
the resulting silence is undocumented. Repro: the 0.25s-per-case injection used
for R8, run with `--suite fast --update-baseline --baseline /tmp/b.json` → exit 0,
no OVER BUDGET line; drop `--update-baseline` → `OVER BUDGET: suite 'fast' wall
clock 79.02s > 60s`, exit 1. Acceptance: either the over-budget line is printed
(as a warning) on the `--update-baseline` path too, or ADR-013 Decision 2 names
`--update-baseline` as a path where the ceiling is not reported.

### T-R5 — Borrowed-browser context leak on a failed new_page            [status: todo]
Origin: PR #20 R5 (LOW, routed debt — unreachable from any committed case)
Spec: `src/browser/agent.py:311-312` creates the `BrowserContext` and its page
before the `try:` whose `finally: await ctx.close()` is the only close, so a
failure inside `ctx.new_page()` leaks that context for the life of the eval
process. The own-browser path is swept by the exit stack; the borrowed path has
no `stack.push_async_callback(browser.close)` to fall back on. Not reachable
from a committed case — a full `fast` run in reverse case order leaves
`len(_BROWSER.contexts) == 0` — and reachable only by making `ctx.new_page()`
raise on the shared path. Acceptance: `ctx` created inside the exit stack
(`stack.push_async_callback(ctx.close)`) or inside the `try`, so both paths
close it on any failure, with a case that leaks before the fix.

### T-R19 — `report-citations-resolve` only checks citation->file, never file->citation            [status: todo]
Origin: PR #20 R19 (MEDIUM, routed repair; the reverse-direction guard itself is
logged here as debt rather than built, since it is more than a "prune to fix" fix)
Spec: the merge at `94f1a42`/`7a2869a` re-added 41-46 uncited routine `fast`/
`invariant` report dumps that ADR-012 had just pruned, and no case caught
it because `_run_report_citations_case` (`src/browser/eval_adapter.py:1014`)
is one-directional: it resolves citation -> file, never enumerates
`evals/report/*.json` and asks whether each file is cited by anything. The
uncited dumps were deleted by hand in this round (38 files: 20 `fast`, 18
`invariant`), not caught by a guard. Acceptance: `report-citations-resolve`
(or a sibling case) additionally enumerates `evals/report/*.json`, excludes the
policy-exempt kinds (`-live.json`, `-soak.json`, `-ablation*.json` — ADR-012
Consequences: "non-prunable by policy regardless of citation"), and fails if any
remaining file is cited by nothing in `REPORT_CITATION_SCOPE`. Watch it fail
first by re-adding one of the 38 pruned files uncited.

### T-R21 — the over-budget-counts-as-red report-write clause is ungraded            [status: todo]
Origin: PR #20 R21 (LOW, routed debt — reviewer's own routing)
Claim: the `or over_budget(args.suite, totals["wall_seconds"])` clause added to
`red` in `evals/run.py:217-219` is correct but ungraded — no case goes red if
that clause is deleted.
Evidence: `evals/run.py:217-219` adds `or over_budget(args.suite,
totals["wall_seconds"])` to `red`. Verified working (stubbed 99.0s fast run:
exit 1, report written, OVER BUDGET line), but `fast-wall-clock-budget`'s
`applied_in_main` probes pass `--no-report`, so they can never observe the
write policy, and no other case inspects it.
Repro: Stub main() with a 99.0s result and no --no-report; assert a report file
appears.
Acceptance: one row driving main() without --no-report on an over-budget stub
and asserting a report file appeared — or recorded as debt with the ADR saying
it is unpinned.

### T-R23 — the ADR-013 renumber sweep's commit-message tally is off by one            [status: todo]
Origin: PR #20 R23 (LOW, routed debt — classification (the thing that matters)
is correct and was verified by hand, only the published tally is wrong)
Claim: the ADR-013 renumber sweep is correct, but its published tally is off by
one: the commit message claims "four `ADR-012` hits"; there are three.
Evidence: Classified by hand: ADR-011 4 hits, all main's readiness ADR, correct.
ADR-012 3 hits (header, INDEX.md:21, evals/run.py:216), all main's report-policy
ADR, correct. ADR-010 all main's M9 ablation plus two deliberate "written as
ADR-010, shipped as ADR-013" notes. No stale ADR-013 reference in src/, evals/,
docs/, README.md or .github/.
Repro: `grep -rn 'ADR-012' --exclude-dir=.git --exclude-dir=report .` -> 3 lines.
Acceptance: the PR body / ledger tally reads 3, or drops the count in favour of
the classification.

### M13 — Adaptive locator learning            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M14 — Parallel eval runner            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence. M12 resolved without amending
ADR-002 D4 — it removed 11.3s of per-case browser launch and left the 42.2s of
deliberate waiting (settle loops, bounded load/screenshot waits, one 10s click
timeout) that only parallelism can hide. `fast` now typically sits under
59.5s against a local 60s ceiling with only a thin, inconsistent margin (a
straddling band briefly pushed the ceiling to 70s, round-5 review could not
reproduce it and withdrew it, then post-commit verification found the
suite clears 60 in 20 of 21 further real runs, not all of them — ADR-013
Decision 4), so this lever is close to urgent: the next case `fast` gains,
even a cheap one, is likely to turn the ceiling red on top of the residual
noise already there.

### M15 — Verifier-accuracy dashboard UI            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M16 — Visual fallback            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### M19 — ADR-011 quotes a readiness latency no report supports            [status: todo]
Origin: PR #21 R8
Spec: ADR-011 Decision 4 says "Measured in the case: 5 ms, mid-run". The eight
committed reports carrying `readyz-tracks-the-run-slot` record `during_latency_s`
of 0.001-0.007 and never 0.005. The substance holds (all <=7ms); the figure is
unsourced.
Acceptance: the ADR quotes a value that appears in a named committed report, or
states it as a range.

### M20 — ADR-011's "invariants, all graded" overstates what the case asserts            [status: todo]
Origin: PR #21 R9
Spec: Decision 3 lists five invariants as graded. Invariant 5 (starts nothing,
spends nothing) is asserted nowhere, and every sample comes from a single
submission — so moving `ACTIVE_RUN = run_id` out of `async with SEM` to
submit-time leaves `readyz-tracks-the-run-slot` PASSING, i.e. `active_run_id`
non-null while `busy` is false is undetectable. The reviewer confirmed the
seven-ablation claim in Decision 5 does reproduce; this is the eighth mutation.
Acceptance: either the ADR narrows "all graded" to what the case asserts, or the
case adds a second in-flight submission so the state is detectable — watched red.

### M21 — the soak's mid-run readiness probe is one instant, not a series            [status: todo]
Origin: PR #21 R10
Spec: `soak.py` captures `mid` once, ~2s after submission, in runs lasting
4.7-13.7s — and at ~2s the run is provably inside an await (playwright launch,
navigate, observe, the awaited planner call). D20 and ADR-011 D7 say "measured
ten times", which is ten single instants, not ten runs observed throughout. Both
documents already hedge ("narrowed, not eliminated"), which is why this is LOW.
Acceptance: the probe samples repeatedly across the run and the report carries
the series, or both documents say "one probe per run, taken ~2s in".

### M22 — ADR-011 D8 overclaims that the retry ledger is pinned            [status: todo]
Origin: PR #21 R12
Spec: the retry probe asserts `"URLError" not in json.dumps(report)`, a substring
search the per-row `retries` list already satisfies — so `summarize` can drop
`transport_retries` entirely and the case stays green. R3's acceptance is met at
the row level; the count and phase live only in the unasserted ledger field.
Acceptance: the probe asserts `transport_retries` content (count + phase at
least) so emptying the ledger reddens, or ADR-011 D8 narrows its wording.

### M23 — a retry-exhausted attempt is published as "retried through"            [status: todo]
Origin: PR #21 R13
Spec: `_http` appends the final attempt to the out-list before re-raising, with
no success marker, so a connect failure that never succeeded appears in
`transport_retries` with `count: 3` and prints under the banner "connect-phase
failures that retried through". The same event is reported twice, once with the
wrong label — on the exact distinction the ledger was added to make.
Acceptance: only attempts followed by a success are recorded, or the entry
carries `retried_through: bool` and the banner reflects it; a case pins that a
fully-failed connect produces an empty ledger.

### M25 — RETRY_SLEEPS sits under a comment describing the socket timeout            [status: todo]
Origin: PR #21 R15
Spec: `evals/ablation.py` — the "30s was too tight ... raised to ~4x the worst
observed stall" block documents `timeout: int = 120`, and `RETRY_SLEEPS = (5, 10)`
was inserted between the comment and the `def`, so the comment now reads as
describing the backoff tuple.
Acceptance: the constant sits above its own one-line comment, or the existing
block names the timeout it describes.

### M26 — the soak's swept-surface inventory omits `results`            [status: todo]
Origin: PR #21 R17
Spec: `summarize` returns 13 keys; the round-2 inventory accounts for 12 and
omits `results` — the per-row evidence body every committed soak report and
D20's row-level recomputation rest on. Blanking it leaves the case green, and
the retry probe's substring check still passes because `transport_retries`
carries the string, so nothing reddens when the artifact loses all its evidence
rows. The case's triage note also calls `transport_retries` "the remaining
published field" when five are unasserted.
Acceptance: a `want` dict asserts `len(report["results"]) == len(rows)`, or the
inventory and the triage sentence name `results` and the passthrough group so
the sweep claim is honest about what it does not cover.

### M27 — The soak cannot separate a bad deployment from a bad third-party site            [status: todo]
Origin: PR #21 R1 (logged there as M18; renumbered on the PR #23 merge — both branches allocated M18 by "next free", the T-ADR-NUM failure mode applied to task ids)
Spec: `summarize` now borrows `ablation.is_measurement` to decide what a
completion is, so a live task ending `failure:nav` because the site itself was
down drops `demo_ready` to false and reads as if the deployment failed. That is
the safe direction to be wrong in and it is why it shipped, but it is still a
conflation: "we could not measure this run" and "this deployment could not
complete it" are different verdicts. Acceptance: a case injects a terminal
`failure:nav` on the live task and pins that the report distinguishes it from a
deployment fault without ever letting it count as a clean completion.

### M17 — Per-IP rate limiting            [status: todo]
Origin: backlog (pre-pr-loop, never promoted)
Spec: promote only with its own eval evidence.

### T-R24 — nothing grades which browser an eval case is allowed to use            [status: todo]
Origin: PR #23 R7 (LOW, routed debt by the reviewer)
Spec (claim): the N1 repair is narrower than the premise it was accepted on, and
the resolution artifact overstated it: the `invariant` suite still needs a real
Chromium in six cases, so "invariant is pure code, no browser" is not restored —
only the newest violation was retagged, and nothing grades the rule.
Evidence: `tasks/reviews/pr23-r3-resolution.json` claimed the fix retains
coverage "without an invariant Playwright import". With a broken browser path the
invariant suite drops to 28/34: `ablation-env-failure-is-a-result`,
`contract-trace-schema`, `observe-content-survives-chrome`,
`readyz-tracks-the-run-slot`, `supersede-never-dangles` and
`url-guard-holds-after-navigation` all fail. `_check_supersede_dangling`
(`src/browser/eval_adapter.py`) calls `_run_agent` without `own_browser`, which
routes to `_browser()`. These six are inherited from main, but they make the
resolution's green sentence untrue of the suite, and no case reddens if
`ui-rendered-narrow` is retagged back into `invariant`.
Repro: PLAYWRIGHT_BROWSERS_PATH=/nonexistent-browsers python3 -m evals.run --suite invariant --no-report 2>&1 | grep -E "^\[FAIL\]|suite 'invariant'"
(reproduced in PR #23 R4 repair: 28/34, exactly those six).
Acceptance: a case grades the invariant suite's purity so the retag cannot
silently reverse. The R3 resolution's `green` text was narrowed in the R4 repair,
which is the honesty half; this block is the graded half.
Same family, same gap, found in the same round: ADR-013 Decision 1 says the suite
shares one Chromium, and `ui-rendered-narrow` owned its own for a whole review
round with nothing red (PR #23 R5). `agent-launches-its-own-browser` did NOT miss
it — that case grades `run_task(browser=None)`, the production launch branch, and
`ui-rendered-narrow` never routes through `run_task`. Do not widen that case:
what is missing is a check on the eval harness's own renderers, not on the agent.

### T-R25 — INDEX.md's ADR-002 line published withdrawn ceilings (both halves)            [status: fixed at PR #29 R22, kept for the mechanism]
Origin: PR #23 R8 (LOW, routed debt by the reviewer); local half fixed and CI
half found at PR #29 R22
Update (PR #29 R22): the line published BOTH a withdrawn local number (70s) and
a superseded CI one (80s, moved to 90s by ADR-019), and named neither ADR-019
nor the `invariant` ceiling that has existed since it. All of that is corrected
in the line now. What is NOT fixed is the mechanism: `adr-header-and-index`
still checks only that each ADR appears in INDEX exactly once, so the prose of
an INDEX line can still contradict the ADR it summarises with nothing red. That
is what this block stays open for — the numbers were a symptom twice.
Spec (claim): `specs/decisions/INDEX.md`'s ADR-002 line still publishes the
withdrawn 70s local ceiling, contradicting ADR-002 itself and INDEX's own ADR-013
line.
Evidence: `specs/decisions/INDEX.md:11` — "fast wall clock ≤ each environment's
own measured ceiling (70s local, 80s CI — ADR-013 Decisions 3 and 4)" vs
`INDEX.md:22` "60s locally (a straddling band briefly moved it to 70s, withdrawn
the same day ...)", `specs/decisions/ADR-002-performance-thresholds.md:4` "60s
locally, 80s on CI", and `evals/run.py:80` `WALL_BUDGET_S = {"fast": 60}`.
Inherited: byte-identical to `git show fcdc6b0^2:specs/decisions/INDEX.md` line
11, so the hand resolution did not introduce it — but INDEX.md was one of the
three hand-resolved files in this diff and `adr-header-and-index` only checks
numbers, never the prose.
Repro: sed -n '11p;22p' specs/decisions/INDEX.md && sed -n '80p' evals/run.py
Acceptance: INDEX.md:11 reads "60s local, 80s CI", matching ADR-002:4,
INDEX.md:22 and `WALL_BUDGET_S`. Held out of PR #23 deliberately: the one-word
edit is not the point, a guard that reads the ceiling out of `WALL_BUDGET_S`
instead of out of prose is.

### T-R26 — two review artifacts route to task ids that no longer resolve            [status: todo]
Origin: PR #23 R9 (LOW, routed debt by the reviewer)
Spec (claim): task-id bookkeeping around the M18/M27 renumber leaves two
artifacts pointing at ids that no longer resolve.
Evidence: `tasks/reviews/pr21-r1-resolution.json:32` still routes the soak
finding to `{"id": "M18", "origin": "PR #21 R1"}` while that block is now
`tasks/TODO.md` `### M27`; TODO.md documents the renumber but the artifact is not
cross-linked, so a reader following pr21-r1-resolution lands on the TinBoker
restyle. Separately, `tasks/reviews/pr21-r2-resolution.json:11` routes R14 to
`debt_id: "M24"` and no `### M24` block exists in `tasks/TODO.md` on this branch
or on `fcdc6b0^2` (inherited from main).
Repro: grep -n '"M18"\|M24' tasks/reviews/pr21-r*.json && grep -nE '^### (M24|M27)' tasks/TODO.md
Acceptance: pr21-r1-resolution.json's debt id reads M27 (or carries a
`renumbered_to` field), and M24 either exists in TODO.md or the pr21-r2 routing
is corrected. Same root cause as T-ADR-NUM's fourth instance — fix them together
or the next renumber re-opens this.

### T-R27 — in a git worktree the pre-commit gate runs the MAIN checkout's hook script            [status: todo]
Origin: PR #23 R4 repair (discovered mid-task, no finding id)
Spec (claim): `core.hooksPath` is repo-level and absolute
(`/Users/willy/Documents/browser-agent/.githooks`), so a commit made in a
pr-loop worktree executes the hook script as it exists in the MAIN checkout's
working tree, not the one on the branch being committed. The hook then `cd`s to
`git rev-parse --show-toplevel` — the worktree — so it grades the right tree
with the wrong script.
Evidence: this round's second commit attempt was blocked by the gate on a 60.18s
fast run (`evals/report/history.jsonl` ts 20260822-011326, sha c947008,
102/102 = 1.000, `"report": null`) and left no per-case report, even though
`evals/run.py:219-222` puts `over_budget` into `red` precisely so an
over-budget run writes one — verified directly:
`over_budget('fast', 60.18)` is True, and a stubbed 99s run writes
`<ts>-fast.json` and records it in the history line. The reason is that
`/Users/willy/Documents/browser-agent/.githooks/pre-commit:14` (the main
checkout, on an older `main`) still passes `--no-report`, while both
`origin/main` and this branch carry the version that does not. Every commit made
from any worktree therefore silently ran the older gate.
Repro: git config core.hooksPath; diff /Users/willy/Documents/browser-agent/.githooks/pre-commit .githooks/pre-commit
Acceptance: the enforcement layer stops depending on which checkout the hook
file happens to live in — the hook execs the script from the tree being
committed (`git show :.githooks/pre-commit` or `$(git rev-parse --show-toplevel)/.githooks/pre-commit`),
or `pr-loop` sets `core.hooksPath` per worktree when it creates one. Same family
as the venv gap already known for worktrees: enforcement that a branch changes
is not the enforcement its own commits get.

### T-R28 — `_run_ui_rendered_case` leaks a BrowserContext when the case errors            [status: todo]
Origin: PR #23 round-5 verification (out-of-scope note, no finding id)
Spec: the R5 repair moved the case onto the shared Chromium, but its `go()`
closes the context only on the success path, so an exception inside
`page.evaluate` leaks a BrowserContext onto the shared browser for the rest of
the suite. Its sibling `_run_observe_case` (`src/browser/eval_adapter.py:466`)
already uses the try/finally pattern this one needs.
Evidence: reproduced by renaming `stepEl` in the PAGE source — the case raises
and `len(_BROWSER.contexts) == 1` afterwards; on the clean pass path four
consecutive warm invocations leave `len(_BROWSER.contexts) == 0`. Reachable
only when the case is already erroring, which is why it did not block PR #23.
Acceptance: `go()` wraps its context in try/finally, and a case asserts the
shared browser holds no contexts after a deliberately-erroring render.

### T-R29 — `docs-numbers-are-derived` asserts substring presence, so a contradicting line beside a correct one stays green            [status: todo]
Origin: PR #23 round-5 verification (out-of-scope note, no finding id)
Spec: the R4 repair made README's "Where it stands" block recompute from the
report files it cites, but the assertion is `expected_string in readme`. A
README that keeps the correct line and adds a contradicting one next to it is
still green — the same class of drift R4 was filed for, one step removed.
Acceptance: the check pins the block's content rather than the presence of
strings within it — parse the fenced block and compare it whole, or assert that
no other line in it parses as a competing figure for the same field.

## Notes

### Reopen — A-phase (2026-08-17)
Owner decision, recorded in `prompts/008-a-level-reopen.md`: B-baseline
accepted; repo does not go public yet; Task 1 reopened for A-level before
submission. Task 2 start deferred by the same decision; the A-phase carries
its own +12h hour guard. M6–M10 are the A-phase roadmap, ranked by
reviewer-value ÷ effort against the two gaps the freeze measured (live
breadth, verifier accuracy).

Plans: `docs/plans/completed/task1-a-level-plan.md` ·
`docs/plans/completed/task1-b-level-plan.md` ·
Methodology: `docs/evals/evaluation-methodology.md` ·
Architecture: `docs/architecture/task1-overview.md`
