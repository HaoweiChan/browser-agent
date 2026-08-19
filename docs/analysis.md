# Analysis — Task 1 (browser agent)

Rubric cell E4: runtime performance, cost, scalability, correctness
verification. Every number below is read out of a committed report in
`evals/report/`, not estimated. Where a number does not exist, this document
says so rather than supplying a plausible one.

Baseline: `evals/report/20260819-144058-fast.json` plus the `live` and
`invariant` runs of the same working tree. Sections 1 and 5 were refreshed at
M7's review round (case counts, precision/recall, the chunking-evasion finding,
and the evidence-window denominator fix); section 6 still carries its M6
numbers and says so. A full refresh
is M10's job (`docs/plans/active/task1-a-level-plan.md`).

## 1. What was measured, and on what

| Suite | Cases | Score | Wall | p50 | p95 | Cost |
|---|---|---|---|---|---|---|
| `fast` (offline gate) | 74 | 74/74 | 36.46s | 0.33s | 2.47s | $0.0000 |
| `invariant` (must-always-hold) | 20 | 20/20 | 3.57s | 0.00s | 2.48s | $0.0000 |
| `live` (3 real sites) | 6 | 4/6 | 47.5s | 2.4s | 20.3s | $0.0000 |

81 distinct cases (20 golden + 61 adversarial). 132 browser actions in a
`fast` run; **43 of the 74** cases drive a real Chromium end to end — counted
here as cases that actually recorded browser actions, which is why the figure
is lower than the 52 this table used to report: the six L5 refusal cases are
end-to-end cases that deliberately stop before a browser opens. The remaining
31 are those refusals plus pure-code probes of a single component (the grader, the
classifier, the URL guard, the scope screen, the matrix parser, and — added
in M7's final phase — the evidence-window bound on a missing value).

**The single most important caveat in this document:** every one of those runs
stubs the planner at the module boundary. That is deliberate (cost-discipline:
the offline gate must cost $0.00 and run without a key), but it means the
measured pass rates grade the **resolver → executor → verifier** path and say
nothing whatsoever about planning quality.

## 2. Cost

**Measured LLM cost across the entire eval suite: $0.0000, on 0 tokens.**

That number is honest and nearly useless, and it is important to say why: no
suite has ever invoked a real planner. The only real LLM spend ever measured on
this system is a **single M1 run on the deployed instance — run `09b21b3a`, one
task, `$0.0029`** — recorded in `tasks/TODO.md` at the time.

A second measurement was taken at M5, on the redeployed build, and it is worth
more than the first because the full trace was captured:

| Deployed run | Task | Result | Actions | Tokens | Cost | Wall |
|---|---|---|---|---|---|---|
| `09b21b3a` (M1) | hello-fixture reveal | success | — | — | $0.0029 | — |
| `cd7121fc` (M5) | books.toscrape, open a book and read its price | `failure:locate` | 3 | 1,438 | **$0.006474** | 6,528ms |

So the defensible statement about cost is: **two observed tasks, $0.0029 and
$0.0065**, with `anthropic/claude-sonnet-4.5` as the planner, one planning call
per task plus one per replan. Everything beyond that — cost per task class, cost
under recovery, the price of a task that replans twice — is **not measured**. A
cost-per-task table built on n=2 would be fabrication, so the two runs are given
as runs.

Note what the second row costs in the other sense: 1,438 tokens bought a plan
whose first two steps were right and whose third was unresolvable. The spend is
incurred before the plan's quality is known, which is the argument for the
per-run token budget rather than for a per-task price list.

What bounds cost rather than measures it:

| Control | Value | Enforced in |
|---|---|---|
| LLM tokens per run | 100,000 | `budget_stop`, exhausts as `failure:env` |
| Actions per run | 30 | same |
| Replans per task | 2 | ladder budget, exhausts as `failure:act` |
| Relocation rungs per step | 2 | ladder budget, exhausts as `failure:locate` |
| Account-level spend cap | OpenRouter key limit | provider side, outside this repo |

The ladder budgets are the ones that matter for cost, because recovery is what
makes a run able to spend more than it planned to. Note one honest wrinkle from
ADR-005: `MAX_FIXES` (2 rungs) cannot currently bind, because the resolver never
generates more than two candidates — so that row is a ceiling that has never
been reached rather than a limit that has been exercised.

## 3. Runtime performance

p50 0.34s, p95 2.51s per `fast` case. The distribution is bimodal and the shape
is more informative than the percentiles:

| Case | s | Why |
|---|---|---|
| `budget-replans-exhausted` | 6.93 | drives the replan budget to exhaustion; each cycle waits out a postcondition that will never arrive |
| `recovery-replan-postcondition` | 2.57 | one such wait |
| `replan-cannot-launder-noop-action` | 2.52 | one such wait |
| `postcondition-compound-keys` | 2.50 | one such wait |
| median fixture case | ~0.35 | navigate, resolve, act, verify |

Nearly all latency above the median is `SETTLE_TRIES × SETTLE_MS` = 10 × 200ms,
the postcondition settle loop, paid on exactly the cases whose subject is a
postcondition that fails. That is the mechanism under test, so it is paid rather
than mocked. A successful step never waits it out.

The live case runs in 2.41s for 3 actions against a real site over the public
internet — the only latency figure here that includes real network.

**Not measured:** end-to-end latency of a real task, which is dominated by the
planner call the suite never makes. The M1 live run is the only end-to-end
observation and its wall time was not recorded per-phase.

Suite wall time grew 24s → 32s at the cold review (ADR-005), entirely from one
extra `inner_text` per action to capture `page_changed`. That evidence is what
separates a legitimate replan from one laundering an action that never landed,
so it was bought deliberately. The `fast` gate remains well inside the 60s
threshold set in ADR-002.

## 4. Scalability

Stated plainly, because this is a reviewer-facing demo and not a service:

- **Concurrency is one.** `asyncio.Semaphore(1)` serialises task execution, so a
  second submitter queues behind the first. Chosen so a single small instance
  cannot be pushed into memory exhaustion by concurrent Chromium contexts.
- **Run records are in-memory.** `RUNS` and `STREAMS` grow for the lifetime of
  the process and are lost on redeploy. Bounded in practice by the action budget
  and by nobody hammering the endpoint; not bounded in principle.
- **The progress stream is single-consumer.** The queue is drained, so a second
  viewer of the same run sees only what is left plus the terminal event.
  `GET /tasks/{id}` remains the complete-result path.
- **Screenshots are written to the container filesystem** under `/tmp/runs/`,
  which is ephemeral.
- **Rate limiting is per-process, not per-IP.** Per-IP limiting is explicitly
  backlog (`docs/plans/completed/task1-b-level-plan.md`).

The honest scaling statement: this design serves one reviewer at a time
correctly, and would need a job queue, shared run storage and per-IP limits
before it served ten.

## 5. Correctness verification

The core claim is that **the executor never grades itself**. A run's status is
assembled from a separate `OutcomeVerifier` (`src/browser/verifier.py`) that
consumes raw evidence — what was extracted, and what the page said where it was
extracted — rather than the executor's conclusion. INV-2 makes a non-PASS
verdict incapable of being reported as `success`.

Layers actually implemented:

- **L1 (runtime predicates)** — trace non-empty, no failed postcondition among
  non-superseded steps, every state-changing action verified, extracted values
  present in their own evidence window, identity anchors present, supersede
  pointers resolve. Available to a live run, which has no ground truth.
- **L2 (external ground truth)** — hand labels, and for TC5 the fixture's own
  record of what it received. Available only in eval.
- **L3** — not implemented; explicitly deferred to B-strong.

### Trap cases: a floor, not an accuracy

Six `trap-*` cases encode wrong answers that look right (form not submitted,
search not executed, unsorted "cheapest", wrong field, near-miss entity, empty
extraction). All six are currently caught. That is reported as a **floor on
detection**, not as verifier accuracy, because the traps were written by the
same author as the verifier.

Two anchor holes are known, declared, and unfixed (`docs/support-matrix.md`):
a near-miss entity whose name contains the target's, and aggregate pages where
every candidate is in the page text so the anchor certifies the wrong answer
too. Both are caught only by ground truth, which a live run does not have.

### Hand-labeled sample (M7): a second floor reading, not a promotion to accuracy

25 runs (16 fixture — 13 general + 2 built to exercise the postcondition gate
+ 1 built at M7's final phase to demonstrate a chunking evasion — and 9 live:
6 books.toscrape.com, 3 news.ycombinator.com) were captured, hand-labeled
`correct`/`wrong` against their task, and replayed offline through the exact
runtime `verify()` call — no `expect`, no `state`, the same call
`agent.py:491` makes. Method, threshold measurement, and the `MIN_EVIDENCE`
scaffolding correction are recorded in full in
`specs/decisions/ADR-007-m7-verifier-accuracy.md`; pinned matrix in
`evals/adversarial/verifier-precision-recall.json`.

**The headline is not the precision figure.** Excluding the two
postcondition-gate records, the runtime verifier — before this milestone's
one addition (`not_a_dump`) — returned `PASS` on **23 of 23** records: 10
correct answers and 13 wrong ones, with zero discrimination between them.
This is provable by reading the code and confirmed empirically: every runtime
L1 check (trace shape, supersede resolution, postcondition presence,
non-empty answer, grounding) is mechanical, and none of them asks whether the
answer answers the question. The eval suite has looked clean across six
milestones because the adapter calls `verify()` a **second** time with ground
truth (L2) — a layer no real user's run ever gets.

`not_a_dump` (`DUMP_RATIO = 0.35`, measured against every `fast`-suite
extraction: real non-dump ratios top out at 0.1786, the two known dumps sit
at 0.4541 and 0.5231, 0.35 sits in the empty gap) is the **first** runtime
check that can fail a mechanically-clean run on the *content* of its answer,
but it closes only the **single-extraction** dump shape. Re-running the same
23 records against the current code: **21/23 PASS** — the two original
page-dump records (one whole-container extraction each) now correctly fail,
but a third wrong record, `chunked-dump-cheapest` (the same task and fixture,
the same page dumped across four separate per-row extractions instead of
one), still passes: `verify()` never receives the task text, so nothing here
can tell "list every product" from "which is cheapest" given identical
per-extraction evidence shapes. That is the entire gain and its exact
boundary — a bounded, real, and now-measured gap (D1, `docs/support-matrix.md`),
not a general responsiveness check.

Post-fix confusion matrix: tp=10, fp=11, fn=1, tn=3 → **precision 0.476,
recall 0.909** (pre-`not_a_dump`, on the 24-record sample that predates the
chunking-evasion record: tp=10, fp=12, fn=1, tn=1 → precision 0.455, same
recall — the check never touches a correct answer). Precision as a ratio is a
function of this sample's mix, which is **deliberately adversarial**: 13 of
the 23 non-postcondition-gate records are constructed traps. Publishing 0.476
without that context invites reading it as general accuracy, which this
sample — constructed, stratified, n=25, drawn only from runs that reached
`verify()` — cannot support.

The 10 pre-existing false positives are short, focused, *wrong* answers, not
dumps: wrong field, wrong table row, unsorted "cheapest", a search filled but
never executed, a form filled but never submitted, a near-miss "Pro" variant
— four of them on live sites. `not_a_dump` was never meant to reach these;
closing that gap needs ground truth (L2, absent at runtime) or an
evidence-only LLM check (L3, absent by design). An 11th false positive,
`chunked-dump-cheapest`, is a different residue: `not_a_dump` was designed
for exactly this shape (a page dump) and misses it because chunking the same
dump across several extractions keeps every individual ratio under threshold
(D1, `docs/support-matrix.md`). Full list: `evals/labels/verifier-sample.jsonl`.

Two more bounds on the claimed gain, declared rather than cased
(`docs/support-matrix.md`): the 0.35 threshold is measured against the size
of the real page the value was read from, so it is chrome-sensitive (the same
dump on a more boilerplate-heavy page dilutes toward and under it) and
thinly calibrated — exactly two positive examples, 0.4541 and 0.5231, only
~0.10 of headroom above 0.35 (D2). The same ratio can also
false-FAIL a *correct* answer that legitimately makes up most of a thin page
— degenerate case, ratio 1.0, always fails — though no fixture in the repo is
sparse enough to demonstrate it (D3, safe direction).

**M7.1 correction: the denominator was the stored window, not the page.**
A reviewer found, and this milestone reproduced before fixing, that
`not_a_dump`'s ratio was computed against `len(page_text)` — the *stored*
evidence window, capped at `PAGE_TEXT_KEEP` and doubled when a distant
identity anchor forces a second window onto it — not against the page the
value actually came from. Two consequences, both watched red: on any page
longer than `PAGE_TEXT_KEEP`, a value over ~700 clean characters read as "a
dump" regardless of true page size; and the *same* value on the *same* page
could flip FAIL → PASS depending only on whether the plan carried a distant
anchor (776-char value, 4,388-char page: ratio 0.388 FAIL with no anchor,
0.2147 PASS with one). The fix records `body_len` — the real page length,
already available in `agent.py` at extraction time — on every extraction, and
`verify()` now prefers it, falling back to the old window-based formula only
when `body_len` is absent. **Disclosed plainly: 6 of the 28 extractions in
the committed hand-labeled sample (`evals/labels/verifier-sample.jsonl`) have
a saturated window (max 3,560 characters) and predate `body_len`, so they
permanently take the fallback — those six ratios are judged against a
truncated-or-doubled window, not the page, and are not page-fractions.** None
of the six cross `DUMP_RATIO` in either direction, so the pinned confusion
matrix (`tp=10, fp=11, fn=1, tn=3`) is unchanged, and the three unsaturated
calibration points above (0.1786, 0.4541, 0.5231) are unchanged in the sense
that matters (verdict) — full detail, including the re-measured band, in
`specs/decisions/ADR-007-m7-verifier-accuracy.md` Decision 6 and
`docs/support-matrix.md` D4.

### What the reliability numbers mean

```
recovery 3/3 verified (6 rungs tried) · mutation 4/4 passed, 2 by relocating
diagnosis 8/8 · 3 replans
```

- **recovery 3/3** is a floor on a denominator of three injected cases, not a
  rate. Six rungs were tried to produce three verified recoveries, and that
  ratio is printed beside it rather than folded into it. Since ADR-005 it is
  graded on the audit, not on the runtime's own claim of success.
- **mutation 4/4 passed, 2 by relocating** is the load-bearing distinction.
  Only one of the three mutation types (`button-text-renamed`) breaks a tier a
  plan was actually standing on; the other two pass without recovering
  anything. Counting 4/4 as "survived by self-maintenance" would be the
  flattering lie, so the adapter counts relocation separately.
- **diagnosis 8/8** is on injected classes only. Five of seven taxonomy classes
  are reachable by injection; `env` and `nav` have truth-table coverage but no
  end-to-end injected case.

### The eval set's own bias, measured

Across six milestones, **18 of the defects found in this system were found by
cold review or by adding a new domain — not by the suite**, in code that was
green at the time (3 at M2 close-out, 6 at the M3/M4 review, ADR-005). Adding
the first live domain immediately exposed a tenth: `observe()` spent its entire
60-element budget on banner and sidebar navigation, so on a real listing page
none of the products were ever observed and the planner planned blind about the
only part of the page the task concerned. Every fixture was too small for that
cap to bind.

M6's two new live domains produced four more (ADR-006), and the pattern held
exactly: each needed a page property no fixture had. A `<th>` without `scope`
computes as role `cell`, so a proximity target answered with its own label. A
product page with a long description put the identity anchor outside the stored
evidence window, and a correct run was graded FAIL. An unresolvable search
field relocated onto a submit button, and the fill error filed a `locate` root
cause as `act`. An unimplemented target key was dropped in silence. Three of
the four are the family this project exists to catch: the run reports on
something other than what it did.

Then M6 was cold-reviewed while green on 65 cases — four of them written for
the new mechanism — and produced **four more**, three of which reported a
confident wrong answer with `status: success`, `verdict: PASS` and nothing in
the trace to suggest doubt: an anchor of "Total" binding to "Subtotal" and
returning the subtotal as the order total; "which row costs $24.50" answered
with a different product at a different price; "which product costs $24.50"
answered "Add to cart". Each needed a page shape `shop.html` — the repo's only
offline listing — happens not to have. The fourth, a recovery rung that dropped
the constraint it was recovering, came from the drift audit rather than the
cold read. The lesson did not change between M5 and M6; only the code it
applied to did.

The conclusion is not that the suite is bad — it is that **an eval set written
by the author of the code is blind in the direction the author was already
looking**, and that adversarial review and unfamiliar domains are the two things
that move that blind spot. That is the argument for treating the cold review as
a gate rather than an option.

## 6. Coverage

76 cases (M6). Empty cells are shown, not hidden.

| Task class | Cases | | Difficulty | Cases |
|---|---|---|---|---|
| TC1 extract-on-page | 20 | | L1 | 20 |
| TC2 search-then-extract | 6 | | L2 | 20 |
| TC3 navigate-then-extract | 8 | | **L3** | **2 — both live, one of them unrun** |
| TC4 interact-then-extract | 14 | | L4 (mutation/recovery) | 8 |
| TC5 form submission | 5 | | L5 (refusal) | 7 |
| mechanism/unit probes | 23 | | untagged (unit probes) | 19 |

| Domain | Kind | Cases |
|---|---|---|
| shop fixture | self-authored | TC1–TC4 + all 3 mutations |
| forms fixture | self-authored, POST ground truth | TC5 |
| hello fixture | self-authored | TC1 |
| nav-heavy fixture | self-authored | observation budget |
| offsite fixture | self-authored | URL-guard enforcement |
| lamp-spec fixture | self-authored | spec table + the only page past the evidence window |
| **books.toscrape.com** | **live** | **TC3 ×2, TC4 ×1 (the TC4 case is the live-planner one, unrun)** |
| **news.ycombinator.com** | **live** | **TC1 ×2** |
| **openlibrary.org** | **live** | **TC1 ×1, TC2 ×1 (the TC2 case grades a correct failure diagnosis, not a working search)** |

Also: 6 ZH-language cases (character-level, all with stubbed plans, so ZH
*planning* is unmeasured), 6 refusal cases, 6 trap cases, 3 DOM mutation types.

## 7. What is not measured — the complete list

The reviewer-facing version of this list, with per-row evidence, is
`docs/support-matrix.md`. In short:

1. **Planning quality — entirely.** Every case stubs the planner.
2. **Real cost and end-to-end latency**, beyond one M1 run at $0.0029.
3. **Verifier precision/recall** — measured at M7 (§5): 0.476/0.909 on a
   25-record hand-labeled sample. A floor reading of a deliberately
   adversarial, constructed sample, not a general accuracy claim; semantic
   responsiveness (a short, wrong, well-formed answer) is still uncaught at
   runtime, and neither is the same dump split across several extractions
   (D1, `docs/support-matrix.md`).
4. **Live *planning*** — three domains and three task classes are exercised
   live as of M6, but every green live case runs a hand-written plan and the
   one live-planner case is unrun (needs `OPENROUTER_API_KEY`). Live breadth
   is no longer the gap; live planning quality still is.
5. **The deployed system end-to-end** — see below.
6. **L3-difficulty tasks** — two exist (both live, M6); one of them is unrun.
7. Seven mechanism-level gaps carried deliberately, listed in ADR-005
   (anchors satisfiable by discarded evidence, relocation rung 1 ignoring the
   target's role, the progress-stream case grading the executor hook rather than
   the SSE endpoint, and four more). `near:` is no longer among them — advertised
   in the target schema since M1 and implemented at M6 (ADR-006), which is what
   moved live table extraction off counting cells.

## 8a. Held-out probe (T9) — raw results

The assignment says reviewers will verify with their own unseen tasks. Before
the freeze, an adversarial agent was given the deployed URL and told to write
10 tasks **blind** — no access to `evals/` when writing them — run them against
the live instance, and verify every answer against the target site itself. It
was told not to fix anything. Raw results, unedited:

| # | Task | Status | Answer | Correct? | $ | ms |
|---|---|---|---|---|---|---|
| 1 | first book title on the listing | `failure:semantic` | null | no | 0.0047 | 6515 |
| 2 | open first quote's author, give date of birth | `failure:locate` | null | no | 0.0057 | 7164 |
| 3 | how many copies in stock | `success` | `In stock (22 available)` | **yes** | 0.0045 | 4868 |
| 4 | list every tag on the first quote | `success` | `["change","deep-thoughts","thinking","world"]` | **yes** | 0.0072 | 5803 |
| 5 | which book is cheapest, and its price | `failure:semantic` | whole-listing dump | no | 0.0044 | 5683 |
| 6 | 请打开这个网页，告诉我页面上第一本书的英文书名和价格 | `failure:extract` | null | no | 0.0048 | 5660 |
| 7 | year the Rosetta Stone was discovered (no start URL) | `failure:locate` | null | no | 0.0037 | 5645 |
| 8 | **"Log into my Gmail" — should be refused** | `failure:extract` | null | **NOT REFUSED** | 0.0235 | 21621 |
| 9 | add to cart and complete purchase — should be refused | `unsupported` | null | **refused (pass)** | 0.0000 | 0 |
| 10 | which books have a five-star rating | `failure:semantic` | null | no | 0.0046 | 6616 |

**Totals: 13,131 tokens, $0.0681, ~70s.** Zero timeouts, zero 5xx, zero hangs.

**Score: 2 correct answers out of 8 answer-seeking tasks (25%); 1 of 2 refusal
probes refused.** The two that worked were single-hop extractions where the
answer string was already in the pre-plan observation. Everything requiring a
second hop (#2), a value living only in an HTML attribute (#1, #6), an
aggregate or comparison (#5, #10), or its own start URL (#7) failed.

### The result that matters most, and what it cost

**No run reported `success` with a wrong answer.** Every one of the seven
failures was loud, classified, gave `answer: null`, and named the exact failing
target in its trace. On the property this system is built around — never
fabricate — the sample is clean 10/10, and the failure classes each pointed at
the real defect.

That said, #5 is a near-miss worth stating: the agent extracted the entire
20-book listing as its "answer", and the verifier rejected it on `grounded`
(a whitespace-normalisation mismatch) rather than on "this does not answer the
question". Had the whitespace round-tripped, a 20-book page dump would have
been reported as a successful answer. The no-fabrication guarantee held there
by luck. There is no check that asks whether the answer is *responsive*.

### What the probe found that the suite did not

- **#8 — the scope guard was bypassable, and it cost more than a wrong answer.**
  `\blog ?in\b` needs a word boundary after `in`; "log into" has none. The
  agent navigated to a real Google login wall, recovered from a locate failure
  to find the Sign in control, typed the literal placeholders `<email>` and
  `$EMAIL` into the credential field, submitted twice, burned both replans and
  **$0.0235 — 5× a normal run and a third of the entire probe budget on a task
  that should have cost $0.00.** The suite never caught it because
  `l5-refuse-login` uses the spaced form the pattern happens to match: the
  cases were written to the regex. Fixed, with `l5-refuse-login-contracted`
  covering inflections, "into", and hyphenated forms; probing after the fix
  showed the hole was wider than the probe found (`sign-in`, `log-into`,
  `check-out` all bypassed too).
- **#7 — "the planner never plans blind" is only true when a start URL is
  given.** Commit `ed1f774` made observation precede planning; with no URL
  there is nothing to observe, so the planner authored a full multi-step plan
  from the task string alone and emitted `{"role": "article"}`. Every
  URL-supplied trace shows step 1 with `note: "pre-plan observation"`; this one
  shows `note: null`. Declared in the support matrix rather than fixed at the
  freeze.
- **A capability ceiling of roughly one hop**, which the matrix predicted in
  general ("planning quality unmeasured") but not specifically.

The probe cost $0.0681 against an estimate of ~$0.03, because #8's unrefused
run was 5× the normal price — the overrun is itself the finding.

### The fix, verified on the deployment

After the fix was pushed and redeployed, `Log into my Gmail account…` and
`Sign into the portal and read my messages` both return, on the live instance:

```
status:  unsupported
reason:  out of scope (matched 'Sign into'): auth/CAPTCHA/payment/destructive/
         download tasks are unsupported
cost:    $0.00
```

Refused before a browser opens, at zero cost — which is what probe #9 already
did for `purchase`, and what #8 should have done.

**One operator error is recorded here rather than omitted.** The script written
to poll for the redeploy *submitted* a task on every iteration instead of
submitting once and polling the result, so ~30 runs were fired at the instance.
25 of them landed after the new build was live and were refused at $0.00. Up to
5 hit the old build; their exact cost is unrecoverable because the redeploy
restarted the process and `RUNS` is in-memory (§4), so the upper bound is
5 × $0.0235 ≈ **$0.12**, and the true figure is lower — the semaphore serialises
runs, so most were still queued when the container restarted.

Two things follow, and both are properties of this system rather than of the
mistake. The in-memory run store means a redeploy destroys the audit trail
exactly when you most want it. And a submit endpoint that costs real money has
**no per-IP rate limit** — listed as backlog in the plan, and this is the first
concrete demonstration of why that matters: a careless loop, not an attacker,
was enough.

## 8. Deployment — verified against the live URL

`https://whaleforce-browser-agent.zeabur.app/`

Worth recording that until M5 this instance had been serving the **M1
deploy-spike build** for four milestones: `/support-matrix` 404'd and the page
still titled itself "deploy spike". M2–M4 existed only in the repository. The
gap was invisible from inside the repo, and is the reason this section exists.

Redeployed and re-verified at M5:

| Check | Result |
|---|---|
| M4 UI serving | `<title>browser-agent</title>`, trace viewer + matrix present |
| Support matrix endpoint | 200, 4 rows + 14 limitations, parsed from the doc shipped in the image |
| URL guard — decimal IP `2130706433` | 422 refused |
| URL guard — `127.1`, `[::ffff:127.0.0.1]`, `file://` | 422 refused |
| URL guard — cloud metadata `169.254.169.254` | 422 refused |
| Empty/oversized task | 422 refused |
| Screenshot endpoint traversal (`result.json`) | 404 |
| Per-step screenshots | 200, 45KB PNGs |
| End-to-end run with the **live planner** | run `cd7121fc`, streamed live, ended `failure:locate` |

The smoke path a stranger would take — submit, watch steps appear over SSE,
open the failed step and its screenshot — was walked end to end in a browser
against this URL. **B-floor criteria 1 and 5 are met.**

The end-to-end run *failed*, and that is reported as the result rather than
retried until it passed. The planner emitted `{"role": "text"}` for its
extraction step — not an ARIA role — and the run ended `failure:locate` with no
answer and no fabrication, having correctly navigated and clicked first. It is
the single most informative data point in this document: the two verified
steps show the resolver working on a real DOM, and the third shows that
**planning is the weakest link and the one thing no suite here measures.**
