# ADR-010: The model ablation ships as a mechanism, and its table is committed empty

Status: accepted · 2026-08-20 · milestone M9. Decisions 13–17 amend earlier
ones across five review rounds on PR #15; the original text is left as written
and each amendment says what moved and where the previous repair fell short.

**Ruling**: M9 ships the ablation *mechanism* with its tradeoff table committed empty and graded — the key lives only on the deployment, so no number can exist until this merges and redeploys, and `analysis-ablation-table-not-estimated` refuses any data row in §9 while it declares itself pending and requires every cell to equal the driver's own formatter output once it names a report; the price ceiling is the **model** `deepseek/deepseek-v4-pro` rather than a number (its list price moved 11% inside one working session), so no literal ceiling lives in code and the incumbent `claude-sonnet-4.5` is priced out and measured by no cell; and a run is published only if its terminal status is on an allowlist of statuses that measure the *model*, everything else aborting the sweep unrecorded.
**Because**: A cost table is worth exactly what its worst cell is worth — a provider outage published as a model scoring 0/5, or a billed completion recorded at $0.00, corrupts the comparison the milestone exists to produce; and an empty section with no guard becomes an estimated section the moment someone is in a hurry.
**Enforced by**: `evals/adversarial/analysis-ablation-table-not-estimated.json`, `ablation-env-failure-is-a-result.json`, `gateway-model-reaches-planner.json`, `gateway-model-not-allowlisted.json`, `ablation-preflight-refuses-old-build.json`

---

## Context

M9's deliverable is "≥2-model OpenRouter ablation · cost/latency tradeoff table ·
ADR for the default-model choice", validated by "table built from committed
report runs, not estimates". The plan's own stated risk is the one that shaped
every decision below: *paying for runs that answer no question — fix the question
per ADR before running.*

Two facts constrain the shape of this PR, and neither is negotiable.

**The paid runs happen on the deployment.** `OPENROUTER_API_KEY` lives in
Zeabur's service environment and deliberately nowhere else (CLAUDE.md rule 8);
no local shell has it, so nothing in this repository can spend money by being
run. The ablation is therefore driven over HTTP against
`https://whaleforce-browser-agent.zeabur.app/`.

**The deployment could not vary the model.** `POST /tasks` called
`live_planner()` with no argument. So the model parameter has to be merged and
redeployed *before* the first ablation run can exist, and **this PR cannot
contain the numbers.** That is a sequencing fact, not a shortfall, and the only
question it raises is how to be honest about it for the duration.

## Decision 1 — the question, fixed before any spend

> **Which affordable popular model should replace the default, and what does the
> cheapest one cost in correctness?**

That is the second version of the question. The first was "does the default buy
anything the cheap ones do not, and at what price and latency?" — and it was
overtaken by an owner constraint that arrived mid-milestone (Decision 2b): a
price ceiling that the incumbent default is 2x over on prompt and 5x over on
completion. **If the owner will not pay above the ceiling, `anthropic/claude-
sonnet-4.5` cannot remain the default on cost grounds alone, without any
measurement at all.** So the comparison is no longer "incumbent versus
challengers"; it is a run-off among the affordable candidates, and the thing left
to measure is which of them to promote and what the cheapest one gives up.

This is a reframing, not a hole, but it costs something real and the cost is
stated here rather than discovered later: **no committed run measures the
incumbent.** Nothing in the resulting table licenses any claim about what
sonnet-4.5 was worth, because no cell contains it.

Narrower than it sounds, and the narrowness is the point. Everything downstream
of the planner — resolver, executor, verifier, budgets, recovery ladders — is
byte-identical across models, and four of the five pages are fixtures the
deployment serves itself. The only variable is the plan. So the ablation is a
**planning-quality** measurement, and it is the first one in this repository:
every pass rate in `docs/analysis.md` §1–§6 stubs the planner at the module
boundary, which §1 already calls its single most important caveat.

What it is not: a benchmark, a general capability claim, or a statement about
these models. Five tasks on one agent's prompt is a measurement of *this system
with that model*, and it will be published as that.

## Decision 2 — four models, owner-selected, every id verified against the live list

| Id | Role | List price prompt / completion (per M) | Context |
|---|---|---|---|
| `deepseek/deepseek-v4-pro` | the ceiling itself — most capable price point allowed | see the snapshot | 1,048,576 |
| `openai/gpt-5.6-luna` | mid, different vendor | see the snapshot | 1,050,000 |
| `tencent/hy3` | cheap, third vendor | see the snapshot | 262,144 |
| `deepseek/deepseek-v4-flash-0731` | cheapest, and the most-used model on OpenRouter | see the snapshot | 1,310,720 |
| — | — | — | — |
| `anthropic/claude-sonnet-4.5` | incumbent default — **accepted by the endpoint, NOT ablated** | see the snapshot | 1,000,000 |

**Prices are not quoted here any more, and that is Decision 15.** They live in
`evals/labels/openrouter-models-20260820.json`, which is the one place they are
allowed to live, because during this milestone one of them moved.

Read directly from `https://openrouter.ai/api/v1/models` (readable without a
key) on **2026-08-20**; all four ids were present in that response (414 models),
and the prices above are the list prices it carried on that date. The four
entries are frozen verbatim in `evals/labels/openrouter-models-20260820.json`,
because the endpoint needs no key — anyone can re-read it — but list prices move,
so a table quoting them needs the snapshot it was read from. The allowlist is
pinned against that snapshot by `gateway-model-reaches-planner`, so editing
either list without re-verifying is a red case rather than a stale sentence
here (spec-drift audit, M9). They are **list prices,
not measurements**, which is exactly why they are here and not in the tradeoff
table in `docs/analysis.md`: what a task actually costs depends on how many
planning calls it makes and how long its observations are, and that is the thing
being measured.

Why these four. They span the allowed band end to end — from
`deepseek/deepseek-v4-flash-0731`, the cheapest entry, up to the ceiling model
itself — which is the widest read on capability-versus-price the band permits,
and price is the axis the owner's constraint made decisive. (No multiple is
quoted: an earlier draft said "10x", a reviewer computed 11.4x from the same
figures, and the true value moved again when the ceiling model's price did. A
hard-coded ratio over a drifting input is a wrong number waiting to happen; the
snapshot carries the arithmetic.) Two of
the four are DeepSeek, deliberately: same family at opposite ends of that spread
isolates price from vendor, which no cross-vendor pair can. So the honest
description of the coverage is **three vendors across four cells, one of them
sampled twice on purpose** — not "four vendors", which would be the flattering
way to say it.

A reasoning-tier model above the default was considered and dropped before the
constraint even arrived: it answers "could we do better by spending more", which
is not the question, and it is the expensive direction.

A typo'd id is a run that fails at spend time, which is why the ids are pinned
in code (`planner.ABLATION_MODELS`), accepted at the endpoint via the wider
`planner.ALLOWED_MODELS`, listed row-by-row
in an eval case, and pinned against the frozen snapshot above. A different fault
the allowlist cannot catch — a correctly-spelled id that the provider rejects
today (deprecated, rate-limited, briefly down) — surfaces as `failure:env`, and
the driver aborts on that rather than publishing it as a `0/5` at `$0.000000`
indistinguishable from a model that plans terribly (spec-drift audit, M9).

## Decision 2b — the selection criteria are the owner's, and one of them is not about quality

The model set is **not** an engineering choice made here. It was set by the owner
on 2026-08-20, mid-milestone and after the mechanism had already been committed
(`d0094d8`), on two criteria:

1. **Popular** — drawn from `https://openrouter.ai/rankings#leaderboard-table`
   ("Usage data through Aug 19, 2026"). All four are top-10 that week: #1
   `deepseek-v4-flash-0731`, #2 `tencent/hy3`, #4 `openai/gpt-5.6-luna`, and the
   #10 DeepSeek V4 Pro family.
2. **Not expensive** — "the most expensive one I can accept is
   `deepseek/deepseek-v4-pro`". The owner later ruled that this fixes the ceiling
   **by model, not by number** — that model sits exactly at the bar, at whatever
   it lists for (Decision 15).

The first criterion has a limitation the source page states about itself, quoted
verbatim because it is the kind of thing that gets quietly dropped:

> "These rankings measure adoption, not quality. They do not rank models by
> accuracy, reasoning ability, or benchmark performance"

So *popular* is the owner's criterion for **what to test**, and it is not evidence
about **what is good**. Nothing downstream may read "these are the popular models"
as "these are the capable models" — producing evidence about capability is the
ablation's whole job, and it has not run.

Provenance, stated exactly. The leaderboard's disclaimer and its date range were
read first-hand from the page; the rank positions come from the coordinating
session's in-app browser read of the same page, because the table itself is
script-rendered and did not come back in a plain fetch. Every **id and price** in
this ADR was read directly from `https://openrouter.ai/api/v1/models` here — not
taken on report — and frozen in `evals/labels/openrouter-models-20260820.json`.

## Decision 3 — five tasks, four fixture and one live, with ground truth reused

| Task | Page | Ground truth from |
|---|---|---|
| price of a named product | `shop-lamp-std.html` fixture | `evals/golden/tc1-shop-price.json` |
| search then name the result | `shop.html` fixture | `evals/golden/tc2-shop-search.json` |
| navigate to a detail page and read a field | `shop.html` fixture | `evals/golden/tc3-shop-detail-nav.json` |
| sort, then name the cheapest | `shop.html` fixture | `evals/golden/tc4-shop-sort-cheapest.json` |
| open a book in a category and read its price | books.toscrape.com, live | `evals/golden/live-books-travel-price.json` |

Fixtures carry four of the five because they are deterministic and free of
live-site drift, which is what isolates planning from everything else: the same
bytes are served to every model, so a difference in outcome is a difference in
plan. One live task is included anyway, because a fixture this repository wrote
cannot show that a model copes with a DOM nobody here authored, and external
validity is worth one row.

The fourth task is deliberately the one whose *shape* has a documented planning
failure. `docs/support-matrix.md` records that there is no compare/rank/filter
step in the plan vocabulary, so "which is cheapest" is planned as "extract the
whole list": deployed run `734d3d1f` answered £45.17 for £23.21 and reported
`success`. Two honesty notes on that evidence, since it is the ADR's only live
one: `734d3d1f` is a *different* task ("find the cheapest book in Travel", no
sort instruction) on a *different* site, and the fixture task chosen here passes
its golden case with a **stubbed** plan, which says nothing about planning it. So
the claim is about the task shape, not a prediction for this row — what makes the
row worth its spend is that a task set on which every model scores 5/5 measures
nothing.

Five, not fifty: this is a tradeoff table, and every extra row is spend against a
question already answered.

**Correct** means the run reported `status: success` **and** its answer matches
ground truth under `verifier.answers_match` — the production comparison the eval
adapter already grades `expect.answer` with. A confident wrong answer scores
zero, which given that "confident wrong answer reported as success" is this
system's best-documented failure mode (support-matrix D5, D7) is the only
definition worth using.

Ground truth is not invented at M9, and after the cold review it is not *copied*
either: the driver holds five golden-case **ids** and reads the task text, the
start URL and the answer out of those files (`evals.ablation.load_tasks`). A copy
would have made "reuses the committed hand label" a claim nothing checks — a
fixture edit that correctly updated the golden case would leave the driver
grading against a stale label and score every model 0/5 on that row, with no case
red. Reading it means the claim is true by construction, and a case that stops
pinning an answer, or that pins a deliberately-wrong one (`answer_is_known_wrong`
— this repo commits two), aborts the driver instead of silently mis-grading.

The comparison is strict, and that is a real bound rather than a detail:
`answers_match` compares numbers structurally and everything else by normalized
equality, so a plan that extracts a correct but wider element ("Price $39.00"
where ground truth is "$39.00") is scored **incorrect** and appears in the table
as a planning deficit. Loosening it would mean inventing a second grading rule
that exists nowhere else in the repo, which is worse; the strictness is declared
instead (support-matrix D12).

## Decision 4 — the metric is the triple, never a single score

Per model: **correct / 5**, total LLM cost, cost per run, total tokens, and
latency p50 / p95. Cost and tokens roll up through `evals.run.aggregate`, the
same function the eval suites use, so those fields mean what they mean everywhere
else in `evals/report/`.

Latency does not, and the cold review is why. The obvious source — the driver's
own wall clock around each submit-and-poll — carries two artefacts that have
nothing to do with the model: the poll's 2-second granularity, and the gateway's
`asyncio.Semaphore(1)`, which means a run submitted while a reviewer is using the
public demo page sits queued behind them. On a five-sample percentile where p95
*is* the slowest of the five, one bystander decides a column. So the published
latency comes from each run's own `budgets_spent.ms`, timed by `run_task` from
inside the semaphore. Client wall time is still recorded per row and rolled up as
`latency_p50/p95` in `totals` — it is the honest measure of "how long did driving
this take" and the dishonest one for "how slow is this model", so they are kept
under different names and only one of them may reach the table.

There is no combined score and there will not be one. A weighting of correctness
against dollars against seconds is a product decision, and inventing one here
would let the ablation appear to make a choice that a human has to make.

## Decision 5 — the decision rule, written before the numbers exist

This is the half of the ADR that has to be written now or it is worthless.

**Input, not measurement, and it comes first.** The owner's price ceiling
(whatever `CEILING_MODEL` lists for — Decisions 2b and 15) is a *constraint on
the decision*, not a finding. It is applied before any number is read, and it already
disqualifies the incumbent: 2x over on prompt, 5x over on completion. Numbers
cannot argue with it, which is exactly why it is recorded as an input. The
ceiling is enforced in code, not just written here — `gateway-model-reaches-
planner` fails if an ablated model exceeds it *or* if the incumbent stops
exceeding it, so if prices move the exclusion gets re-decided rather than
re-asserted.

Given the ceiling, the rule picks the **replacement**, not "whether to replace":

- **Highest correctness wins**, and ties go to the cheaper model. Correctness is
  the scarce quantity here — this system's documented failure mode is a wrong
  answer reported as success, and buying more of that at a discount is a worse
  deal, not a better one.
- **A tie on correctness is broken by cost, then by p95 latency.** All four
  candidates are already inside the affordable band, so a further 3x on cost is
  worth less than a second of p95 a reviewer actually waits through.
- **`deepseek/deepseek-v4-flash-0731` is promoted over a pricier sibling only if
  it does not lose correctness.** It is the cheapest cell and the most-used model
  on OpenRouter, so it is the tempting answer; being tempting is not a reason.

What would **not** decide it:

- **A tie on this task set read as equivalence.** Five tasks, one run each, is
  evidence of no observed difference, which is not the same thing and never has
  been in this repository (support-matrix, the "no case demonstrates this" rows).
- **Any result on the live task alone.** One live page is external validity, not
  a domain claim.
- **A latency win with no correctness or cost win.** The dominant term in
  end-to-end latency is unmeasured (`docs/analysis.md` §3), so a planner-latency
  difference cannot be projected onto the run.
- **Popularity.** It selected the candidates (Decision 2b); it breaks no ties.

If every candidate scores badly, the recorded outcome is "nothing in the
affordable band is good enough, and here is what each one got wrong" — a result,
published as one, and a genuinely useful input to the owner's ceiling. What is
**not** available as an outcome is "the default stays because it was better",
because no cell measures the default.

## Decision 6 — the default is unchanged in this PR, and the incumbent is not measured

`DEFAULT_MODEL` is still `anthropic/claude-sonnet-4.5`. Changing it now would be
choosing on the same absence of evidence this ADR exists to stop other people
choosing on — and the price ceiling, while it rules the incumbent out, does not
say which of the four replaces it. That is what the run is for. The
no-model-supplied default path is pinned as row 1 of
`gateway-model-reaches-planner`, so the default cannot move as a side effect of
anything.

Stated plainly because it is the one thing about this table most likely to be
misread later: **`anthropic/claude-sonnet-4.5` is not in the ablation set, and no
committed run measures it.** It is over the owner's ceiling, so ablating it would
spend on a cell whose answer cannot change any decision. The consequences, all of
them:

- The table will have four rows and none of them is the model the system runs on
  today. A reader comparing rows is comparing candidates to each other, never to
  the incumbent.
- No claim of the form "the cheap model is as good as what we had" is available
  from this data, in either direction.
- The endpoint still **accepts** the default by explicit name (Decision 7), so
  the default path stays exercisable — it is priced out of the comparison, not
  out of the system.
- If the ceiling is ever raised, adding the incumbent back is a one-line change
  to `ABLATION_MODELS` plus a re-run; the graded ceiling check will have gone red
  first and forced the conversation.

Recorded in `docs/support-matrix.md` as D14.

## Decision 7 — the public endpoint's model field is allowlisted, not free

`POST /tasks` is public and unauthenticated. OpenRouter bills whatever model id
it is handed, and the run budgets (30 actions, 100k tokens) count *tokens*, not
price, so they would not notice a caller pointing this deployment's key at the
priciest model on the platform. The field is therefore gated on
`planner.ALLOWED_MODELS` and anything else is refused 422 with a `model blocked`
detail — the same status and shape as the URL guard's refusal, so the frontend's
existing rejection path renders it unchanged.

Membership is tested with `is not None`, not truthiness. An **absent** field and
an explicit **`null`** both mean "not specified" and fall back to the default —
JSON null is the absent value for an optional field, and Pydantic cannot
distinguish them here anyway. `""` is different: a caller who sent it sent
something, and something not on the list is refused. All three are pinned as rows
(PR #15, R8 — the earlier wording said only an absent field defaulted, which was
not what the code did).

**Two lists, not one.** `ALLOWED_MODELS` is what the endpoint accepts —
`[DEFAULT_MODEL, *ABLATION_MODELS]`, five ids. `ABLATION_MODELS` is what the
driver runs, four. They were the same list until the owner's ceiling priced the
incumbent out of the comparison, at which point one list doing both jobs meant
the deployment refused its own default by name. The driver checks the narrow list
(ablating the default would spend on a cell the table has no column for); the
endpoint checks the wide one (the default path must stay reachable). Both are
graded, and by different cases.

One bound, stated carefully because two looser versions of it were wrong: every
**other** model on the allowlist is cheaper **per token** than the default, on the
list prices read on 2026-08-20 and frozen in
`evals/labels/openrouter-models-20260820.json`. (The default is itself on the
list, at parity with itself — spec-drift audit.) That does **not** bound per-*run* cost — a model that plans
worse replans more, and two extra planning calls at a third of the price is a
wash. So the honest claim is the narrow one: the field cannot point the key at a
model more expensive per token than the one this deployment already uses by
default. The pre-existing absence of per-IP rate limiting (declared at M5, still
backlog) is unchanged and remains the real spend exposure. (Correction from the
M9 cold review, which caught the loose version claiming a per-run bound.)

## Decision 8 — the empty table is graded, not promised

A cost/latency table that sits empty across at least one PR boundary is exactly
where a plausible illustrative row gets pasted in "just to show the shape",
survives review because it looks like data, and reads as a measurement six weeks
later. Prose asking future sessions not to do that is worth nothing.

So `analysis-ablation-table-not-estimated` (tagged `invariant`) grades the
section in `docs/analysis.md` in two modes:

- **pending** — the section names no report and declares itself pending: the
  table under the `ablation-table` marker must contain **zero data rows**;
- **report** — the section names a committed `-ablation.json` file: every row
  must equal what `evals.ablation.markdown_rows` derives from that file. One
  formatter, two callers — the driver prints the table and the case re-derives
  it, so the table is machine-derived in effect and a hand-typed cell is red.

Report mode has no committed report to point at yet, and dead-on-arrival is how
a two-stage delivery loses its guard between the stages. It is exercised against
a synthetic report whose model ids do not exist on OpenRouter, precisely so no
number in the case file can ever be misread as a result: the driver's own
formatter must be accepted, one edited cell must not, and a named-but-absent
report must not.

Watched red both ways. Pending mode: with no such section in `docs/analysis.md`,
and then, with the section written, by pasting a fabricated row under the
separator — `numeric_rows_with_no_report_behind_them`. That hand check used a
`google/gemini-2.5-flash` row, from the model set this ADR was first written
with; the committed variant pins the same shape with `tencent/hy3`, which is what
the case file and the support-matrix row name today (Decision 12 replaced the
set). Report mode: by ablating the row
comparison in the grader, which turned the case red on
`accepted_a_number_the_report_does_not_support`; ablating the pending-mode row
check turned it red on `accepted_a_tampered_section`.

Stated precisely, because the loose version of this was in an earlier draft: the
two branches that decide whether numbers may exist are each **singly** pinned —
remove either and the case goes red on its own variant. The header check and the
duplicate-table count overlap (a dropped column changes the header *and* the
count), so neither is singly pinned; both are covered, jointly. The
"table unreadable" branch is pinned by a variant that renames the marker. The
variants themselves are not counted here: three descriptions of this one case
carried three different totals, all stale inside one PR (PR #15, R19). The file
is `evals/adversarial/analysis-ablation-table-not-estimated.json`; it cannot go
stale, and a number that must be hand-maintained will be wrong again by M10.

## Decision 9 — the driver aborts rather than reporting a partial run

`evals/ablation.py` fails loudly and **writes no report** on a non-2xx, an
unreachable host, an unknown model, a run that never leaves `running`, a run the
gateway attributes to a different model than the one submitted, or a run that
ends `failure:env` **for an environmental reason**. An outer exception net around
each run catches whatever the named faults miss, so a connection dropped mid-poll
cannot lose the completed rows this decision promises to echo.

That qualifier is the correction in Decision 13, and it matters more than it
reads: `failure:env` is *not* infrastructure-only, and an earlier draft of this
decision said it was. A run
still in flight is not a slow result; it is no result, and recording it with the
numbers spent so far is the fabrication CLAUDE.md rule 4 bans.

The one concession: the rows already completed are echoed to **stderr** before
the abort, because that spend really happened and destroying the record of it
would be its own dishonesty. A dump on stderr is not a result, nothing
downstream reads it, and no committed artifact contains it.

The allowlist is also checked client-side before the first submission — a typo
found after fifteen paid runs is fifteen paid runs wasted.

And one preflight, which is the check that matters most and was nearly missed.
Zeabur keeps serving the previous build until the deploy flips, and the app
exposes no `/version` (`.github/workflows/deploy-smoke.yml` records the same
ceiling for the same reason). A build without the model parameter answers **200
and a run_id** to a `model` field it silently drops — indistinguishable from
success — so running the driver too soon after the merge would produce four rows
that are all the default model wearing four names, with nothing in the table to
say so. The driver therefore probes the guard before it spends: it submits a
model that is *not* on the allowlist and requires a 422. An old build accepts it
instead, and the driver aborts naming the redeploy as the fix.

The probe task trips the scope screen (`agent.screen`, which `run_task` applies
before it plans), so even on the old build that accepts the field the probe run
ends `unsupported` having made **zero planner calls and spent $0.00**. That is
now measured rather than asserted: `ablation-preflight-refuses-old-build` installs
a planner factory that *succeeds* and counts calls, submits the probe, and
requires `status == "unsupported"`, `llm_usd == 0.0` and zero calls. It used to
assert only that `screen(probe)` was truthy — a proxy — and the composite property
was exercised nowhere, because on a machine with no key `live_planner` raises as
an argument expression and the probe run ends `failure:env` before `run_task`
reaches the screen at all (PR #15, R5). Both preflight branches are also
exercised against the in-process app: the current build returns 422 and the driver
proceeds; an app patched to accept any model aborts it.

## What is deliberately NOT done

- **The numbers.** Impossible in this PR (Context). Stage two is: merge, let
  Zeabur redeploy, run `python3 -m evals.ablation`, commit the report, paste the
  table, name the report in the section.
- **No repeats per cell.** One run per (model, task); nothing here says anything
  about variance, and a model that wins 3/5 to 2/5 on n=1 cells has not been
  shown to be better. Repeats are the honest upgrade and they multiply the spend
  by the repeat count; the sample size is stated wherever the table is.
- **TC5 (form submission) is not in the task set.** Its ground truth is
  server-side state read from `/fixtures/forms/state`, which would put a second
  correctness mechanism in the driver for one more row.
- **No per-phase latency.** The published columns are the run's own duration
  end to end; the planner call is not timed separately, so a latency difference
  cannot be attributed to the planner with confidence. Named here rather than
  implied by the table.
- **`answers_match` is strict on free-form answers.** A correct extraction with a
  wider span scores incorrect (Decision 3). It will understate every model
  equally, including the default, so it cannot flatter a challenger — but a
  `correct/5` column read as "planning quality" is reading it more precisely than
  it deserves.
- **The default model is not changed.** Decision 6 — and it is not measured
  either, which is a stronger statement and the one that matters.
- **The incumbent is not ablated despite being allowlisted.** Running it would
  spend on a cell that cannot change a decision the ceiling has already made.
- **The guard cannot tell a real report from a hand-written one.** It proves the
  table matches a committed `-ablation.json`; it does not prove that file came
  out of a run. Nothing in a repository can prove that. What it leaves for a
  human is a per-row `run_id` and the deployment's `GET /tasks/{id}` — checkable
  only while that process lives, since the run store is in-memory (analysis §4).
  Stated here rather than left as an implied guarantee.
- **No ZH task in the set.** ZH support is declared character-level, not
  planning-level (support-matrix, M5 rows), and measuring it per-model would be
  a second question in the same spend.

## Decision 10 — cold review round, before the commit

A cold reviewer read the diff without the reasoning behind it and returned three
findings. All three were about the same thing: **a guard whose scope is narrower
than the claim it is written under.** Each is fixed here rather than declared,
because each was cheap and each sat on the money path or the honesty path.

1. **The driver would happily run against a deployment that predates the model
   parameter.** A pre-M9 build answers 200 to a `model` field Pydantic drops, so
   twenty paid runs would return four rows that are all the default model wearing
   four names — and four rows within noise of each other maps, under Decision 5,
   onto "the default stays", the one outcome that makes nobody look again. Fixed
   by the preflight in Decision 9. This had been added between the review's read
   and its report, so credit for finding it independently belongs to both.
2. **The honesty guard read exactly one table in a section with room for many.**
   It graded the marked table and nothing else, so a second "expected shape"
   table under a `###` sub-heading — which stays inside the graded section,
   because the section ends at the next `##` — carried per-model numbers past a
   green invariant case whose whole subject is that no such numbers exist. Fixed
   with two nets: no second copy of the ablation table, and no table row anywhere
   in the section naming a model. Prose may still name the four models; a table
   row that does is a results row wherever it sits. Two new committed variants.
   The reviewer also noted, correctly, that §9's own budgeting estimate was the
   precedent making this the natural edit — that paragraph now lives here, in an
   ADR, not in the graded section.
3. **The latency columns were the driver's client wall clock.** Decision 4 has
   the full argument; the short version is that the semaphore queue and the 2s
   poll would have been published as model latency, under a decision rule that
   turns p95 into a reason to change the default.

Also fixed from the same review, without a case each: the task set's ground truth
is now read from the golden cases instead of copied beside them (Decision 3); an
outer exception net around each run so a dropped connection mid-poll cannot lose
the completed rows Decision 9 promises to echo; row matching made order-independent,
because requiring the doc's row order to equal the report's made "sort the table
by cost" a red case whose cheapest fix is hand-editing the committed report; a
duplicate `--models` id refused; and a documented `--base http://127.0.0.1:8000`
invocation removed, since the deployment's own URL guard refuses loopback and it
could never have worked.

Two findings from that review are **declared, not fixed**, and both are in the
"not done" list below: the strictness of `answers_match` on free-form answers, and
the fact that nothing can prove a committed report came out of a real run.

## Decision 11 — spec-drift audit round, same sitting

A spec-drift audit read the declarations against the code and found fifteen
items. The pattern was different from the cold review's and worth naming: the
cold review found guards narrower than their claims; the audit found **claims
wider than their evidence**. Fixed here:

- **Three of the four M9 cases existed in no committed report.** Every "watched
  red / runs green" sentence in this PR was prose-only. Both suites are now
  committed: `evals/report/20260820-131950-fast.json` (90/90, 68.06s, $0.0000)
  and `evals/report/20260820-131838-invariant.json` (26/26).
- **The model-id verification had no artifact.** Anyone can re-read OpenRouter's
  public list, but list prices move, so the four entries are frozen in
  `evals/labels/openrouter-models-20260820.json` and pinned against the allowlist
  by a case. Decision 2.
- **`preflight` was the one M9 code path with no case.** It is also the one
  guarding twenty paid runs. Now `ablation-preflight-refuses-old-build`, which
  drives both branches against the real app on loopback and additionally asserts
  the property that makes the probe safe — that its task is refused by the scope
  screen before anything plans.
- **A provider-rejected model id would have been published as `0/5`.** An id can
  be on the allowlist, correctly spelled, and rejected today. The run comes back
  `failure:env`; the driver now aborts on that rather than letting infrastructure
  land in the table as a planning result. Decision 9.
- **Four claims were wider than their evidence and are narrowed in place**: the
  grader's branch-pinning (only two of its branches are singly pinned, and this
  ADR said all of them were); "the only two real spend observations" (there are
  three — `734d3d1f`, $0.005454, is recorded in `docs/analysis.md` §8b and was
  missing from the count); "every model on the allowlist is cheaper than the
  default" (the default is on the allowlist); and task 4's "the incumbent is
  known to fail here", whose live evidence is a different task on a different
  site. Each now says what a reader can re-derive.
- **Stale counts this PR itself falsified**: `docs/analysis.md` §1 and two README
  numbers still read 86/96 cases. Corrected to 90/100, with the M9 report named.
- **`docs/evals/evaluation-methodology.md` gained a Metrics row** for the new
  published metric, with its five limitations — the doc's own contract is that
  every published metric has one.
- **The frontend advertised a guard its own form cannot reach.** The page claimed
  a model allow-list while the form never sends a `model`; it now says the field
  is on the API and that runs started from the page use the default.

Two audit items are **not** acted on, deliberately. `specs/` gains nothing for
the `model` field: `specs/001` documents no `POST /tasks` request shape at all
(the URL guard is not there either), so adding one field would be a half-contract
— the gap is real and belongs to M10's freeze, not to a milestone about cost.
And `CLAUDE.md`'s Commands block does not list `python3 -m evals.ablation`; that
file is the working contract and editing it is the owner's call, so it is flagged
rather than changed.

## Decision 12 — owner spec change, after the mechanism was committed

The model set above is not the one this ADR was first written with. Commit
`d0094d8` shipped the mechanism with `anthropic/claude-sonnet-4.5`,
`anthropic/claude-haiku-4.5`, `google/gemini-2.5-flash` and
`meta-llama/llama-3.3-70b-instruct`. The owner then set the two selection
criteria in Decision 2b, and **all four ids failed them** — the two Anthropic
models on price, the other two on not being on the leaderboard at all. (The
nearest leaderboard substitute for the Gemini row, `google/gemini-3.6-flash` at
$0.75/$3.75, is also over the ceiling; only its `:batch` variant fits, and batch
is asynchronous and unusable for interactive planning.)

Three things follow, and the third is the one worth the section:

1. **The set was replaced wholesale**, ids and prices re-read live from
   `https://openrouter.ai/api/v1/models` and the frozen snapshot regenerated from
   that response rather than hand-copied.
2. **The allowlist and the ablation set had to split.** Until then one list did
   both jobs, which was invisible while the default was also the first ablated
   model. The moment the default was priced out, the endpoint started refusing
   `anthropic/claude-sonnet-4.5` by name — the deployment rejecting the model it
   actually runs on. Watched red exactly there (`gateway-model-reaches-planner`,
   row 2: `want {http: 200, planner_model: anthropic/claude-sonnet-4.5}`, `got
   {http: 422, planner_model: null}`).
3. **The question changed, and pretending otherwise would have been the easy
   dishonest move.** The original question — "is the default worth its price?" —
   is unanswerable now, because the answer's subject is not in the table. The
   easy thing is to leave Decision 1 alone, run four cheap models, and let a
   reader assume the incumbent was in there somewhere. Decisions 1, 5 and 6 are
   rewritten instead: the ceiling is an owner **input** applied before any number
   is read, the incumbent is disqualified by it without measurement, and the run
   is a run-off among affordable candidates.

Every case that hard-codes a model id was re-watched red on the new constants
rather than edited into agreement — including one that would otherwise have
passed while grading nothing. `ablation-preflight-refuses-old-build` simulates an
old build by patching a module attribute **by name**, and that name had just
changed; a patch landing on the wrong name is a silent no-op, after which the
endpoint keeps refusing, `preflight` keeps raising, and the case reports PASS.
It failed loudly here only because the old attribute no longer existed at all.
That is luck, not a guard, so the case now proves the simulated door is actually
open before drawing any conclusion from it — and that assertion was itself
watched red by aiming the patch at a decoy object.

## Decision 13 — review round 1 (PR #15): `failure:env` is not one thing

A reviewer with fresh context returned 8 findings. The one that matters:

**`failure:env` is four events wearing one class, and only some are the
environment's.** `agent.py` returns it for a planner exception — including
`PlanError` from `parse_plan`, i.e. *the model answered with prose instead of a
JSON array* — for a replan that raised, and for budget exhaustion. Decision 9 and
the driver both asserted it was "infrastructure, never a statement about
planning", so the driver aborted the whole sweep on it.

The abort was the visible half. The real defect is what it refuses to record:
**the entire reason a $0.14/M model is in this set is to find out whether the plan
vocabulary breaks down at the bottom of the price range, and "emitted prose
instead of a plan" IS that finding.** The driver treated the ablation's most
likely and most valuable observation as a reason to discard up to fifteen
already-paid runs and write no artifact. A measurement instrument that aborts on
its own expected result is not an instrument.

Split on the reason prefix, not on the class:

| Reason starts with | Meaning | Driver |
|---|---|---|
| `planner rejected:` | the call worked; the model's answer was not a plan | scored — an incorrect cell, at the cost the provider billed |
| `replanner rejected:` | same, on the recovery plan | scored |
| `budget exhausted:` | it flailed through 30 actions / 100k tokens | scored |
| `planner failed:` / `replanner failed:` | the CALL failed — 4xx/5xx, dropped connection, malformed body | **abort, write nothing** |
| anything else | missing key, no result produced | **abort, write nothing** |

The word is `rejected`, and the distinction is made in `agent.py` by catching
`PlanError` — the type `parse_plan` raises, and the only thing in the system that
means "the response arrived and was not a plan" — separately from every other
exception. **This is the correction from round 2 (Decision 14) and the table above
is the corrected version;** the first attempt matched `planner failed:`, which
`agent.py` writes for *every* planner exception, so a provider 402 scored as a
model producing 0/5 at $0.000000.

Prefixes at all rather than a new failure class because "the model cannot plan"
has no class in `docs/evals/failure-taxonomy.md`, and adding one changes what
`specs/000-invariants.md` pins — which a cost milestone has no business doing on
its way past. What makes them safe now is that they are *authored where the type
is known* and merely named here, rather than pattern-matched by a consumer
guessing at a message it did not write. The row carries `reason` so a reader can
tell a model that flailed from a run nobody made. Recorded as a ceiling, with the
taxonomy change as the upgrade path (support-matrix D15).

**The run record now echoes its planner model** (R4). It carried none, so every
row's attribution was the driver's loop variable, checked once by `preflight` at
the start of a ~20-run sweep — and Zeabur auto-deploys from `main`, so a redeploy
mid-sweep produced rows indistinguishable from correct ones. `RunResult` gains a
`model` field (`specs/001-browser-contract.md`), `run_one` aborts if the echo
differs from what it submitted, and both contract cases went red on the new key
first, which is the shape guard doing its job.

**The honesty guard leaked in two directions** (R2, R3), both reproduced against
the committed §9 text. Its stray-number net matched model ids *literally*, so a
second results table spelling them "Tencent Hy3" and "DeepSeek V4 Flash" was
accepted, as was a bullet list. And `_doc_section` cut the section at the next
`## `, so a copy of the graded table under `## 9a. Preliminary ablation numbers`
was invisible to every check while sitting directly under the pending table for
any reader. Now: the section runs through continuation headings (`## 9a`, `## 9.1`);
the duplicate-table sweep is document-wide, since a second ablation table is a lie
wherever it sits; and the stray net also matches the *shape* of a result figure
(`$n`, `n/5`, `p50`/`p95`) on any table row or list item. **Declared ceiling:** free
prose is not covered. A paragraph can still carry a fabricated number, and no
pattern short of reading the prose stops that — the guard covers the shapes
results actually get written in.

Three smaller ones, each fixed: report mode never re-checked the pending banner,
so a section could name a report, carry matching rows, and still tell the reader
none existed (R7); the gateway-model case installed its recorder *above* the
snapshot-verification block, so a renamed snapshot file left it installed for
every later case in the process (R6); and `{"model": null}` defaulted while
Decision 7 claimed only an absent field did (R8) — the rule is now written as it
behaves, since JSON null *is* the absent value for an optional field, and pinned
by a row rather than left to drift again.

R5 is the family this repo escalates over — a decision claiming a property
nothing measures — and it is now measured; see Decision 9.

## Decision 14 — review round 2 (PR #15): the round-1 split was backwards

A second reviewer, briefed that round-1 repairs in this repo have twice moved a
defect one step rather than closing it, found that three of five findings were
exactly that. The two HIGHs are one story, and it is the milestone's story: **M9
exists to produce a cost table, and both findings put a wrong number in the same
cells.**

**R9 — the round-1 repair inverted the defect.** Splitting on `planner failed:`
looked right and was backwards: `agent.py` writes that prefix for *every* planner
exception, transport included. `env_is_fatal("planner failed: HTTP Error 402:
Payment Required")` returned `False`, so an OpenRouter outage would be published
as a model scoring 0/5 at `$0.000000` — the precise artifact Decision 9 claims to
prevent, arriving through the repair meant to prevent it. The case could not have
caught it: its one fatal HTTP row was spelled `HTTPError: HTTP Error 402: ...`,
the gateway catch-all's format, reachable only when `live_planner()` fails at
*construction*, never when a request is rejected.

The fix is not a wider pattern. A third widening of a guessed pattern would have
been the same defect a third time, so the distinction moved to where it actually
exists: `PlanError` is a type, `parse_plan` is the only thing that raises it, and
`agent.py` now catches it separately at both planning call sites. The driver's
list only has to *name* what the agent deliberately authors.

**R10 — and the cells it does score were free.** `live_planner` built `usage`
*after* `parse_plan`, so a completion the provider billed for and that turned out
to be prose discarded its own cost. Four documents said "with their real cost and
tokens still counted"; none of them were true. A cheap model that emits prose on
three of five tasks would have published roughly 40% of its true spend — into a
`Cost/run` column that Decision 5's rule compares across models. `PlanError` now
carries the usage of the call that produced it, `live_planner` builds it before
parsing, and `agent.py` charges it to the model that emitted the prose.

**R11 — the third widening of the same net.** The stray-figure guard matched
table rows, then table rows plus `- `/`* ` bullets; a numbered list, a `+`
bullet, a blockquote and an indented code block all still walked through. The net
is now **syntax-blind**: any result-shaped figure anywhere in §9 outside the
graded table. That is shorter than the enumeration it replaces and cannot be
walked around by inventing markdown, and it forced the four list prices out of §9
into Decision 2 above — which is the right place for them anyway. A section whose
subject is "no numbers exist yet" is trivially checkable when it contains no
numbers at all. The declaration in §9 and D12 now describes that class rather
than a list of syntaxes that kept being wrong.

**R12 — the sharpest finding, and the one worth generalising.** The
document-wide duplicate-table sweep added in round 1 was never applied to the real
`docs/analysis.md`: the live grading call omitted the `document=` argument, which
defaulted to `None` and silently fell back to the section. Only the synthetic
variants passed it, so the property was proved against inputs the case
constructed and never against the artifact it is published as protecting. **A
guard that passes by grading nothing is the failure mode this repo ranks worst.**

Two changes, because the obvious one was not enough. `document` is now a
**required** parameter — a forgotten argument is a TypeError, not a quiet
downgrade, which deletes the failure mode instead of guarding it. And the
committed-file check and every whole-document variant now go through one
function, `_grade_document`, so the variants exercise the same entry point the
real file does; before that, narrowing the live call left the case green, because
a clean document narrows to the same answer either way. The discrimination pass
caught that the first fix was unpinned, which is the same lesson one level up.

**R13 — accepted, though rated LOW.** The round-1 R4 repair put an eval-only
branch (`ECHO_MODEL_OVERRIDE`) in the gateway's execution path, while this PR's
own adapter docstring argues that a stub backdoor on a public endpoint is a trade
worth declining. The reviewer was right that the PR contradicted itself. The
mismatched-echo simulation now wraps `agent.assemble_result` from the eval side
and `server.py` carries no eval-only code.

The discrimination pass on this round found **two of the six fixes unpinned**
(R10's `live_planner` half, R12's call site) — both because the case exercised a
value it constructed rather than the production path. Both are now pinned by
probes of the real code, and reverting either turns the case red.

## Decision 15 — the ceiling is the model, not the number (owner ruling, and round 3)

`deepseek/deepseek-v4-pro` moved from **0.00000144 / 0.00000288** to **0.0000016
/ 0.0000032** per token — up about 11% on both — **inside a single working
session.** Review round 3 caught it (PR #15, R16) by comparing the committed
snapshot against the live endpoint; the coordinating session confirmed it across
two reads two hours apart, and I confirmed it again here. The other four entries
were unchanged to the digit and `_total_models_in_response` was 414 in every
read. **The snapshot was accurate when it was frozen.** This is real supplier
drift, not a transcription error, and it is the strongest argument this
repository has yet produced for why the snapshot mechanism exists at all: a list
price quoted in prose goes stale in hours, and four documents were quoting it.

The owner's ruling: **the ceiling is the model, not the number.**
`deepseek/deepseek-v4-pro` stays in the ablation set at whatever it lists for.
Three consequences, all implemented:

1. **The snapshot is re-read and re-frozen** from the live endpoint, with the
   drift, both prices and both read times recorded in the file itself.
2. **No price literal survives in code.** `planner.py` names `CEILING_MODEL` and
   nothing else; the effective ceiling is *derived* from that model's snapshot
   entry. The old `PRICE_CEILING` constant is gone. It could only ever have
   detected two transcriptions of the same number disagreeing — never that the
   ceiling model had moved in reality, which is precisely what happened. It also
   could not have lived on the production side much longer: `evals/` is
   `.dockerignored`, so a shipped module cannot read the snapshot, and a number
   in the image that must track an external list is the defect in miniature.
3. **The check keeps its teeth, in both directions**, and this was confirmed
   rather than assumed: every ablated model must price at or under the ceiling
   model on prompt *and* completion, and the incumbent must remain **over** it.
   At $3.00 / $15.00 against the new $1.60 / $3.20, `anthropic/claude-sonnet-4.5`
   is still excluded by a wide margin — Decision 6 and support-matrix D14 are
   unaffected. Watched red by hand-raising the snapshot's ceiling entry until the
   incumbent fitted: `default_now_fits_the_ceiling`.

## Decision 16 — review round 3 (PR #15): the argument was on the wrong axis

The round-2 repairs held — the first round in this PR whose predecessor's fixes
survived. What a third reviewer found instead is that three rounds had been spent
refining *which `failure:env` reasons* count, while a **different failure class
was never inspected at all**.

**R14 — a dead site published as a model's incompetence.** `agent.py` writes
`failure:nav` from the *pre-plan* navigation, before the planner is ever called,
always at $0.00. The driver only ever looked at `failure:env`, so that landed in
the table as `| 0/1 | $0.000000 |`. Task 5 of the fixed set is live and gets hit
once per model, and this repository has already been bitten twice by exactly that
— M6's openlibrary outage, and the post-M6 fix where one hanging subresource made
a fully readable page `failure:nav`.

The fix is the inversion, not another entry. **A denylist extended three times,
each time by a reviewer rather than by the code, is a rule that will be extended
a fourth time.** It is now an allowlist: a status must be *named* as a
measurement to be published, and anything unrecognised — including a failure
class a later milestone adds — aborts the sweep. Five statuses qualify (all of
them require a plan to exist and to have run), with two reason-scoped exceptions
that are agent-authored prefixes rather than guesses at someone else's message.
`failure:nav` is excluded outright rather than only in its pre-plan spelling: a
page that will not load is reachability, and a plan-issued `navigate` that times
out cannot be told from a slow site. That under-measures in the safe direction —
it can abort a sweep it might have scored, never publish a cell it should not
have.

**R15 — the `try:` was drawn around the parse, not around the response.** The
round-2 repair keyed everything on `PlanError`, but `content` was extracted one
line *above* the guarded block. So `content: null` — what a reasoning model
returns on `finish_reason: length`, and the ceiling model defaults to high
reasoning effort — raised `AttributeError`, was classed as a transport failure,
aborted the sweep, and discarded the cost the provider had already billed. Both
round-2 properties failed on one input. The whole of "what the model sent back"
is now inside the guard, and anything unreadable in it becomes a `PlanError`
carrying the usage; a 200 that carries a provider *error object* stays an
ordinary exception, because that is the provider failing rather than the model
answering. The lesson worth keeping: a guard drawn around the parse instead of
around the response handling leaves exactly this gap.

**R17 — the third iteration of one net.** Round 1 enumerated model ids, round 2
enumerated markdown syntaxes, round 3 enumerated number spellings: the same
results table written "4 of 5" with unsigned costs sailed through. The rule is
now **structural** — §9 contains exactly one table, the graded one — which cannot
be respelled and is shorter than what it replaces. §9's "where the pieces live"
table became a bullet list to make the rule exception-free. The figure net stays
for prose, bullets, blockquotes and code. The in-code comment that still
described a net the round-2 repair had deleted is also corrected; a comment
describing a guard the code no longer has is the declaration-vs-code drift M8
escalated over.

**Stage-two writability, demonstrated rather than asserted.** A guard that would
have to be weakened to publish correct content is a defect now, not later. The
case drives the real §9 through the exact transition a human makes after the
ablation runs — drop the pending banner, name the committed report, paste the
driver's own table under the marker — and requires it to grade clean with no
change to the grader. It does: two rows published, `[]` from the guard.

## Decision 17 — review round 4 (PR #15): the catch-all, flipped

The round-3 repairs held — the second consecutive round whose predecessor's
fixes survived. Three findings, no HIGH, and the interesting one is a shape this
PR has now produced twice with opposite polarity.

**R18 — `except Exception -> PlanError` is the R9 defect inverted.** Round 3
asked for the whole response handling to sit inside the guard, and the guard I
wrote absorbed *everything it did not recognise* into "the model's fault". So a
200 with no `choices` key, a string `error` field (an `isinstance(..., dict)`
test missed it), `choices: null`, or a plain gateway envelope all became
`planner rejected:` and would have published a provider outage as a model
scoring 0/5 — while `docs/analysis.md` §9, the section this milestone ships,
already said an unreadable body aborts.

Both R9 and R18 are the same mistake: a catch-all silently sweeping the unknown
into whichever bucket is adjacent. The principle that fixes it is the one already
adopted for R14's status allowlist — **default-deny** — and it is now applied at
the response boundary too. Only a response positively recognised as *"the model
answered, and the answer is not a plan"* is scored: the envelope must yield a
choice with a message object, and then a missing/empty `content` or unparseable
content is the model's. Anything else stays an ordinary exception and aborts.

**One round-3 expectation is deliberately reversed.** R15's acceptance pinned
`choices: []` as "the model did not produce a plan" (scored); it is now an
envelope that aborts. The two rounds' principles genuinely conflict, and
default-deny wins: an empty choices list carries no completion to judge, so it is
not the model answering badly, and aborting is the direction that can never
publish a wrong cell. Recorded here rather than quietly re-pinned.

**The stale truth-table row was the better half of R18.** The table pinned
`planner failed: KeyError: 'choices'` — a string production had stopped emitting
when the response guard moved — so it graded a dead state while the live one went
untested. Fixed for the class rather than the instance: every prefix
`is_measurement` keys on must now appear literally in the production source *and*
be exercised by a row in the table, so renaming one without updating the other is
red. Watched red by renaming `planner rejected:` to `planner declined:`.

**R19 — three descriptions, three counts, all stale inside one PR.** The variant
totals are deleted rather than corrected. A count that must be hand-maintained
will be wrong again by M10; the file name cannot go stale.

**R20 — the third recurrence of a defect fixed twice by hand.** D14 — the
disclosure that no ablation cell measures the model the system actually runs on —
had drifted a blank line away from its table, so it rendered as a paragraph of
pipes. `parse_matrix` is line-based and picked it up anyway; every cell-count
check stayed green. PR #12 fixed exactly this for D10 and added no guard, which
is why it came back. A table block whose second line is not a delimiter is now a
loud `ValueError`, with a `matrix-drift` variant behind it. The point is not the
blank line: it is that an honesty row can silently stop being part of its table,
and this time the row was the one the owner's whole ceiling decision rests on.

The discrimination pass again caught one of this round's own fixes unpinned —
broadening the provider-error test from `isinstance(dict)` to any truthy `error`
was covered by the envelope guard in every probe, so a probe carrying an error
field *alongside* a readable `choices` array was added to give it teeth.

## Consequences

- The deployment's public surface grows one optional, allowlisted field.
- `docs/analysis.md` gains a section that says "no numbers exist" and is graded
  on continuing to say so until numbers do.
- Two invariant-tagged cases stand between the ablation and its two silent
  failure modes: a refused model that is not refused, and a supplied model that
  never reaches the planner and would have made all four rows the same model.
- M9 is not closeable on this PR alone. The A-exit criterion ("cost/model
  ablation table in `docs/analysis.md` from committed runs") is met only after
  stage two, and `tasks/TODO.md` should reflect that rather than reading M9 as
  done when the mechanism merges.
