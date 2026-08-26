# ADR-030: the sec-10k inspector probe is pre-registered, its ground-truth endpoint is eval-only, and the row it declares measures mode B

Date: 2026-08-26
Status: accepted

**Ruling**: before any run of the M41 inspector probe executes, this ADR freezes the two-task set, the exact task text and start URL for each, the protocol (3 runs per task via `POST /tasks` on the deployed URL with no `model` override, every run's `run_id`/answer/terminal status/cost/wall time published regardless of outcome, ground truth re-verified through the inspector's `/api/extract/fixture` at probe time, both build shas recorded), the four ADR-025 metrics and the pass/fail thresholds in §Thresholds — and rules two boundaries that outlive the probe: the inspector's ground-truth endpoint is reachable from the eval side only and never from the planner or executor, and the `docs/support-matrix.md` row this milestone declares measures **mode B only** and says so, with M44 named as the owner of its loop-mode column.
**Because**: this is the same act ADR-025 pre-registered for T-M40-5 and the same reason applies with one addition — the target site is our own other deployment, so a row here is a claim about two builds, not one (postmortem §2), and the thresholds must be frozen before the numbers exist because M41's own acceptance clause requires a row whatever the numbers say; the eval-only boundary is CLAUDE.md rule 6's third allowance used deliberately rather than drifted into, because an executor that can ask a site's API for the answer passes every case on that domain without reading the page and no other check in this repo would notice.
**Enforced by**: the pre-registration half is procedural (the commit that carries this file precedes the probe, and the probe's results land in §Outcome below); the ground-truth boundary is enforced by `sec10k-ground-truth-endpoint-eval-only`; the mode-B scoping is enforced by the row's own text and by ADR-022's live-declaration rule.

---

## Context

The 2026-08-24 demo failed on our own sec-10k inspector, and
`docs/evals/2026-08-24-demo-sec10k-inspector-postmortem.md` is the retrospective:
four page shapes (S1 fetch-then-render, S2 answers-are-not-accessible-names,
S3 three identical "Extract" buttons, S4 unauthored async settle), each
individually sufficient to end a run, none of them replayed from a surviving
trace because `RUNS` is in-memory (D19). `tasks/TODO.md` M41 is the remediation
block. Its cross-repo dependency — sec-10k-extract's display-layer legibility
row — **has since deployed**: `/api/meta` answered `git_sha` `5a44758598f5` when this
section was written, at pre-registration — the sha moved before the probe ran
and the page was already serving the newer build even then, which §Outcome
records and which this line is deliberately NOT edited to hide; the
deep link `?fixture=<id>&run=1` preloads and extracts on page load, `#banner`
carries `role="status" aria-label="doc_status"`, the extracted-text panes carry
`role="region" aria-label="Item <n> extracted text"`, and the three Extract
buttons carry distinct `aria-label`s. The postmortem's ordering note is
therefore satisfied: the page shape probed here is the one that stays deployed.

### The scope ruling, stated rather than left as a tension

M41's `Update 2026-08-25` says the declared matrix row "should wait for M42 and
be probed under both modes", while M41's own Acceptance requires the row. This
ADR rules: **declare the row now, as a mode-B row, and make the row say so.**
The block itself calls the update "sequencing guidance, not a hard Depends"; the
stated reason to wait (probing the old page) is gone now that the page-side row
deployed; and M44 "owns folding the loop-mode results back into this row", which
cannot fold into a row that does not exist. The row must state plainly that it
measures mode B, that loop mode is unprobed, and that M44 owns that column.
Nothing in loop mode, `select_option`, frame-piercing observation or a default
post-click settle is built here — all four are M42's.

### ADR-number collision check

Highest ADR on `origin/main` is `ADR-027-loop-mode-is-a-deliverable.md`.
`gh pr list --state open --json headRefName,number` (checked 2026-08-26, from
this branch) returns three open PRs: `task/M42` (#57), which adds decision files
numbered **028 and 029**; `task/M45` (#56), which adds a decision file also
numbered **028** — the two collide with each other at 028, the way #42 and #44
collided at 023 when ADR-025 ran this check; and
`chore/m39-done-and-id-uniqueness` (#54), which adds none. This ADR therefore
takes **030**, the number after the highest reserved anywhere, rather than 028
after `main`'s maximum: ADR-025 took `main`+1 and was safe because the collision
was between two other branches, whereas 028 here would make an existing two-way
collision a three-way one.

## Frozen task table

Both task texts are quoted verbatim from the M41 block; neither is chosen after
seeing any result. One start URL, because one deep link is the whole point of
the page-side row: a parameterised start URL is per-site data CLAUDE.md rule 6
allows, and it is the only inspector knowledge that reaches a run.

| # | Task (verbatim, frozen here) | Start URL | Ground truth | Source of ground truth |
|---|---|---|---|---|
| 1 | `What is the doc_status of the aapl-2025 fixture?` | `https://whaleforce-sec10k.zeabur.app/?fixture=aapl-2025&run=1` | `success` | `POST /api/extract/fixture {"fixture":"aapl-2025"}` → `doc_status`, re-verified at probe time |
| 2 | `How many items are extracted?` | same | `18` (with 5 more `incorporated_by_reference`, 23 items total) | same call → `counts.extracted`, re-verified at probe time |

An answer counts as **correct** if it carries the ground-truth value. The page
renders both values inside one status line — `doc_status: success — 18 extracted
· 5 incorporated_by_reference fixture: aapl-2025` — so an answer that returns
that whole line carries the value and is graded correct; this is decided here,
before the runs, because it would otherwise be exactly the kind of judgment call
ADR-025 exists to prevent being made after the fact. An answer of `18` alone is
also correct for task 2. An answer of `23` is **wrong** for task 2 (that is the
item count, not the extracted count) and, if it terminates `success`, is a
wrong-success.

### The wrong-success shape this probe predicts before it runs

Pre-registered so that finding it cannot be presented afterwards as an expected
result. The deep link removes the click, not the race: measured while writing
`live-sec10k-authored-wait-reaches-the-doc-status`, the observation the planner
is given is taken before the page's own extraction round-trip lands, and with
the settle deleted from the plan, 3 reps produced two runs terminating
`success` with the answer `"Extracting…"` and one `failure:semantic`. If a
live run answers `"Extracting…"` or `"No filing extracted yet."` and terminates
`success`, that is a **wrong success** under §Metrics and trips threshold (a).
It is not a refusal, not a loud failure, and not a footnote.

## Validity precondition

This probe counts only if run against the deployment of `main@9c3340c` or a
later `main` commit (`deploy-smoke` run `32926527916`, conclusion `success`,
2026-08-26T03:27:42Z — read off the workflow timeline, since there is still no
`/version` endpoint to compare against, the declared ceiling T-M40-4 names), and
only while the inspector reports `git_sha` `5a44758598f5`. If the inspector's
sha has moved at probe time the probe is re-run against the new one and the sha
recorded is that one: D28's build-expiry rule applies to the target site's build
too, which is the postmortem's §2 finding.

**Nothing in the PR that carries this ADR changes what is measured.** Stated
precisely, because a first draft of this paragraph said "no production file
moved" and two did. What the branch touches under `src/browser/` is
`eval_adapter.py` (the new check plus one scanner-scope exclusion) and
`server.py` (an `EXAMPLES` card for the new matrix row — forced, not optional:
`ui-examples-cover-matrix` requires one for every live row). What it does NOT
touch is the execution policy: `agent.py`, `planner.py`, `observe.py`,
`resolver.py`, `verifier.py` and `judge.py` are unchanged. `EXAMPLES` is a
list of demo cards the gateway renders and nothing a run reads. And the probe
ran against the DEPLOYED build, which is `main` — none of this branch is on it.
So the probe measures the mode-B agent as it already stands, twice over.

## Protocol

1. Each of the 2 tasks is run **3 times** against
   `https://whaleforce-browser-agent.zeabur.app` via `POST /tasks`, `url` set to
   the frozen start URL and **no `model` field** — 6 runs total.
2. For every run record `run_id`, the final `answer`, terminal `status`, cost
   and wall-clock time, read from `GET /tasks/{run_id}`.
3. Ground truth is re-verified at probe time through the inspector's
   `/api/extract/fixture`, and `/api/meta`'s `git_sha` is read before and after
   the probe. The endpoint is called by the probe script and by nothing the
   agent runs — the boundary below.
4. Every run_id is published, whatever it did. No run is dropped.
5. Runs are serialised, not parallel: the deployment holds one run slot
   (`/readyz`), and the deep link makes the inspector re-extract on every hit.

## The ground-truth-endpoint boundary

Rule 6 allows three pieces of per-site data anywhere: a start URL, a rate limit,
and a ground-truth API endpoint. M41 uses the first and the third. The rule that
keeps the third honest is direction: `/api/extract/fixture` may be reached by
the probe script, by `evals/` and by an eval adapter, and by nothing that
decides what the agent does. `sec10k-ground-truth-endpoint-eval-only` enforces
three conjuncts, each watched red before it was green: the endpoint path appears
in no module of `src/browser/` except `eval_adapter.py`; the inspector host
appears in none except `eval_adapter.py` and `server.py`, which carries a start
URL per declared matrix row in `EXAMPLES` (rule 6's first allowance, and
`ui-examples-cover-matrix` requires one for every live row); and every eval case
tagged with that domain that carries an `expect.answer` names the endpoint its
ground truth came from.

Both halves of that are allowlists, and they became allowlists because a cold
review found them narrower than the sentence above. The host rule first named
the six execution-policy modules explicitly, which left `cli.py` and `mutate.py`
free to carry per-site knowledge with nothing red — and the host is the string a
navigation recipe would travel in. The case rule was keyed on the FILENAME
pattern `*sec10k*.json`, so renaming a case would have dropped it out of the
scan in silence. Naming what MAY carry a string is a rule a new module cannot
walk around; naming what may not is a list somebody forgets to extend.

**What a reviewer may reasonably push back on, recorded rather than argued
away.** The start URL is `?fixture=aapl-2025&run=1`, and `run=1` is an
imperative: it performs, page-side, the action an executor would otherwise have
to author. Read strictly it is still a URL and rule 6 allows a start URL; read
functionally it is a navigation recipe that happens to live in a query string,
and it is the only per-site knowledge in this milestone that reaches shipped
code (`server.py`'s demo card). Two things make it defensible rather than
convenient, and neither is decisive: the page's own repo shipped the parameter
as a display-layer affordance for any client, not as an agent hook, and the
probe's own §Outcome finding 2 shows the agent does not actually rely on it —
every task-2 run authored a click anyway. Declared here so the next reader
argues with a position instead of discovering one.

## Metrics — reported separately, never blended

The four ADR-025 metrics, unchanged and quoted rather than restated loosely:
**correct answer** (terminal `success`, judge-certified, answer carries the
re-verified ground-truth value), **loud failure** (any `failure:*` terminal
status), **wrong success** (terminal `success` with an answer that does not
carry the ground-truth value), **refusal** (the gateway rejects the task before
a run starts, or the run reports a defined refusal state distinct from the
three above). Four separate numbers per task. Never combined into one rate.

## Pre-registered thresholds (fixed, verbatim)

(a) **HARD**: zero wrong-success across all 6 runs. Any wrong-success = probe
verdict FAIL regardless of every other number, and — per ADR-027's Invariants
and M44's Acceptance — is a stop-ship finding routed to a queue block, not a
row footnote.
(b) The matrix status is decided by the correct-answer rate over the 6 runs,
and by this rule rather than by judgment after the fact: **6/6 → `supported`;
3–5 of 6 → `unreliable`; 0–2 of 6 → `unsupported`.** A verdict of FAIL on (a)
overrides this row-status rule and the row is declared `unsupported` whatever
the correct-answer rate.
(c) Refusals are counted separately and never counted toward (b).
(d) The row records both build shas, every run id, and the repeat count. A row
that cannot name the inspector's `git_sha` it was probed against is withdrawn,
not softened.

## Commitment

Whatever the outcome, results land in §Outcome below and in
`docs/support-matrix.md` as declared limitation **D30** plus a
`whaleforce-sec10k.zeabur.app (live)` row, in the same commit, including
declaring the row `unsupported` where the thresholds say so. Every run_id from
every one of the 6 runs is published there, not just the ones that support the
verdict. Raw per-run evidence is committed under `evals/report/`.

## Consequences

- The row this declares is a mode-B row and is labelled as one. It is not
  evidence about loop mode in either direction, and M44 owns re-declaring it
  under both modes.
- Shapes S3 and S4 are not fixed here. S3 is fixed page-side on this one page
  (`sec10k-extract-buttons-are-distinguishable`) and the capability gap behind
  it stays with M38/ADR-026. S4 is declared, with `l4-shop-render-delayed` as
  its existing offline pin and M42 as owner of the default settle.
- A new failure shape found by this probe is a new adversarial case (rule 2),
  not an adjustment to this ADR's frozen task list or thresholds.

## Outcome

Probe run 2026-08-26T06:59Z against `main@9c3340c` (`deploy-smoke` run
`32926527916`, conclusion `success`). 6/6 runs terminal, $0.004742 of model
spend in total, no `model` override on any run.

**The inspector's build moved under this milestone, and the story is not the
simple one this section first told.** Corrected after a cold review read the
committed fixture: `/api/meta` answered `5a44758598f5` when this milestone
started and `6b37ffa99d05` at probe time, unchanged before and after the probe
itself. But the page's own footer, which it fills from that same `/api/meta`
field, already read `build 6b37ffa99d05` in the FIRST capture — taken while a
`curl` to the same endpoint was still answering `5a44758598f5`. Two reads of one
field disagreed inside one session, which is what a rolling deploy across
containers looks like; that explanation is INFERRED and is written as an
inference. What is measured: the committed snapshot is a capture of the build
that reported itself as `6b37ffa99d05`, which is the build this probe ran
against, so the fixture and the probe agree on one build instead of straddling
two. §Validity precondition's rule applies as written — the probe is graded
against the build actually deployed — and `6b37ffa99d05` is the sha the row
records. The page shape was re-verified rather than assumed: the capture was
re-taken after `/api/meta` had caught up and diffed against the committed one,
byte-identical apart from one `total_ms` figure inside the extraction evidence
(227.6 → 221.1). Nothing this repo grades changed. Nothing in this repo reads
either sha back either, which is `tasks/TODO.md` T-M41-3.

### Every run

| # | Task | Rep | run_id | Terminal status | Answer | $ | tokens | run ms | submit→terminal |
|---|---|---|---|---|---|---|---|---|---|
| 1 | doc_status | 1 | `a413fbf9` | `success` | `doc_status: success — 18 extracted · 5 incorporated_by_reference fixture: aapl-2025` | 0.00014978 | 1798 | 4502 | 6.51s |
| 1 | doc_status | 2 | `1e43220d` | `success` | same string | 0.00014378 | 1793 | 3916 | 6.56s |
| 1 | doc_status | 3 | `e996cc7d` | `failure:semantic` | — (extracted `Extracting…`, judge rejected) | 0.00033338 | 1951 | 6343 | 6.55s |
| 2 | item count | 1 | `79c8dc32` | `failure:env` | — | 0.00117442 | 4385 | 9845 | 12.77s |
| 2 | item count | 2 | `5da0441b` | `success` | the same status line as task 1's runs | 0.00105742 | 4278 | 9949 | 12.96s |
| 2 | item count | 3 | `81172a2f` | `success` | the same status line as task 1's runs | 0.00188314 | 7128 | 18051 | 19.20s |

**Two gaps in this artifact, named rather than left for a reader to find.**
(1) The probe harness recorded no `model` echo per run, so the artifact cannot
itself back the "no `model` override" claim above — that claim rests on the
submission payload, which carried no `model` field, and `POST /tasks` defaults
when the field is absent (`server.py`, pinned by `gateway-model-reaches-planner`).
`specs/001-browser-contract.md` puts `model` in the run record precisely so
attribution is not the driver's own assertion, and this harness did not read it
back. (2) FIVE of the six runs report `judge_calls: 1` with
`judge_tokens: 0` and `judge_usd: 0.0`, including `e996cc7d`, whose judge
returned bespoke prose. The sixth, `79c8dc32`, reports `judge_calls: 0` and
correctly so: it died on the drill-down's no-progress guard before an answer
existed, and there is nothing for a judge to grade. This sentence said "every
one of the six" until PR #58 R5 read the artifact back — a note whose whole
subject is an accounting gap, wrong about the accounting. Per the contract those are zero for a stub or a cache
hit, and the aborted attempt had already run the same two tasks against the same
page, so a cache hit is the likely reading — likely, not established. Either way
the published `$0.004742` is planner spend; judge spend on these runs is
unaccounted rather than measured at zero, and it is small on any reading.

Ground truth re-verified at probe time through `/api/extract/fixture`:
`doc_status: "success"`, `counts: {extracted: 18, incorporated_by_reference: 5}`,
23 items. Raw per-run evidence, including each run's step sequence and the
verifier reason, is committed at
`evals/report/20260826-065901-m41-inspector-probe.json`.

### The four metrics, separately

| | Task 1 (doc_status) | Task 2 (item count) | Both |
|---|---|---|---|
| Correct answer | 2/3 | 2/3 | **4/6** |
| Loud failure | 1/3 | 1/3 | **2/6** |
| Wrong success | 0/3 | 0/3 | **0/6** |
| Refusal | 0/3 | 0/3 | **0/6** |

### Verdicts against the pre-registered thresholds

- **(a) HARD, zero wrong-success: PASS — 0/6**, and the interesting part is
  *how*. §Frozen task table predicted, before the runs, that an answer of
  `"Extracting…"` terminating `success` would be a wrong success. Run
  `e996cc7d` produced exactly that answer — the executor extracted
  `Extracting…` from the status line — and the ADR-017 judge rejected it:
  *"The candidate answer 'Extracting…' does not provide the doc_status of the
  aapl-2025 fixture; it appears to be a progress message."* The run terminated
  `failure:semantic`. The predicted wrong success was produced and converted
  into a loud failure by the last rung of the ladder. That is the first live
  evidence of the judge catching the grading-quality class D25 declared
  unverified on a shape a probe predicted in advance.
- **(b) Row status by the frozen rule: 4/6 → `unreliable`.** Not `supported`.
  The rule was written before the numbers existed and is applied as written.
- **(c) Refusals: 0.**
- **(d)** Both build shas recorded (ours `9c3340c`, the inspector's
  `6b37ffa99d05`, which is ALSO the build the committed snapshot captures —
  `5a44758598f5` was the reading `curl` got from `/api/meta` at capture time,
  not the build captured, and calling it "the capture sha" survived the
  nine-document correction in this one place until PR #58 R5), all six run ids published, repeat count 3 per task.

Overall verdict: **PASS on (a), `unreliable` on (b).**

### Two findings beyond the threshold numbers

1. **The two loud failures are two different shapes, and neither is S2.**
   `e996cc7d` is S1/S4 reaching the answer slot: the page was still rendering
   when the extraction ran, and only the judge stopped it. `79c8dc32` is the
   ADR-020 drill-down's own refusal — the plan clicked, then asked to `observe`
   `{role: main}`, and the replan came back identical, so
   `observe-drilldown-no-progress-stops-the-run`'s guard ended the run rather
   than letting the queued steps run against an unchanged page. It is
   classified `failure:env`, which is D15's declared imprecision and not a new
   defect.
2. **The planner does not need the deep link's click, and half the time takes
   it anyway.** Runs `a413fbf9` and `1e43220d` planned `navigate → extract` and
   answered in 4,502ms and 3,916ms of run time for $0.00015 each. Every task-2 run planned a
   `click` first — pressing Extract on a page that had already extracted — and
   the two that succeeded cost 7-13x more and took 2-4x longer. The deep link
   removes the NECESSITY of the click, not the planner's inclination to author
   one, and the runs that authored one are the runs that hit S1's race and the
   drill-down's refusal. No conclusion is drawn about *why* from three reps per
   task; it is recorded as an observation with its run ids.

### The aborted harness attempt, recorded rather than passed over

A first attempt to run this protocol was killed by a two-minute local shell
timeout before it wrote anything. It had already submitted runs against the
same frozen tasks and the same start URL. One run id was recovered by reading
`/readyz`'s `active_run_id` while it was still executing — `6045555d`,
terminal `failure:semantic`, judge rejected for not naming the count,
$0.00131975, 66,023ms — and it is published here with the six above. **The
rest are unrecoverable.** `6045555d` is a task-2 run, so the attempt had
already worked through task 1's three reps; on the order of three further run
ids exist and cannot be retrieved, because `RUNS` is in-memory
(`docs/support-matrix.md` D19) and the deployment exposes no listing endpoint.

This is a hole in this probe's evidence and is stated as one. The metric tables above count the SIX probe runs, which is what the frozen
protocol defines; `6045555d` is recorded here and in the artifact's
`aborted_harness_attempt` block and is deliberately not folded into them,
because a protocol whose reps are chosen after the fact is the thing this ADR
exists to prevent. It changes nothing if it were: it is a loud failure, so
(a) is 0 wrong-success over six graded runs and over all seven on the record.
What the lost runs mean is that "zero wrong-success" is a claim about the seven
runs that exist as evidence, not about every run this protocol caused. It is the same finding D19
already carries, arriving as a cost rather than as a note — and it is why
ADR-025's "every run_id is published" clause needs a harness that writes
incrementally, not one that writes at the end.
