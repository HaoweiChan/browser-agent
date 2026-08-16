# Analysis — Task 1 (browser agent)

Rubric cell E4: runtime performance, cost, scalability, correctness
verification. Every number below is read out of a committed report in
`evals/report/`, not estimated. Where a number does not exist, this document
says so rather than supplying a plausible one.

Baseline: `evals/report/20260816-210730-fast.json` plus the `live` and
`invariant` runs of the same working tree.

## 1. What was measured, and on what

| Suite | Cases | Score | Wall | p50 | p95 | Cost |
|---|---|---|---|---|---|---|
| `fast` (offline gate) | 59 | 59/59 | 31.98s | 0.34s | 2.52s | $0.0000 |
| `invariant` (must-always-hold) | 17 | 17/17 | 3.5s | 0.00s | 2.47s | $0.0000 |
| `live` (books.toscrape.com) | 1 | 1/1 | 2.14s | 2.14s | 2.14s | $0.0000 |

60 distinct cases. 103 browser actions in a `fast` run; 37 of the 59 cases drive
a real Chromium end to end, the remaining 22 are pure-code probes of a single
component (the grader, the classifier, the URL guard, the matrix parser).

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

So the defensible statement about cost is: *one* observed task cost about
a third of a cent with `anthropic/claude-sonnet-4.5` as the planner, one
planning call per task plus one per replan. Everything beyond that — cost per
task class, cost under recovery, the price of a task that replans twice — is
**not measured**. A cost-per-task table here would be fabrication.

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

p50 0.34s, p95 2.52s per `fast` case. The distribution is bimodal and the shape
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

The live case runs in 2.14s for 3 actions against a real site over the public
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
  backlog (`docs/plans/active/task1-b-level-plan.md`).

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
same author as the verifier. There is **no hand-labeled precision/recall
sample** — it is in the B-strong list and was not reached.

Two anchor holes are known, declared, and unfixed (`docs/support-matrix.md`):
a near-miss entity whose name contains the target's, and aggregate pages where
every candidate is in the page text so the anchor certifies the wrong answer
too. Both are caught only by ground truth, which a live run does not have.

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

Across five milestones, **9 of the defects found in this system were found by
cold review or by adding a new domain — not by the suite**, in code that was
green at the time (3 at M2 close-out, 6 at the M3/M4 review, ADR-005). Adding
the first live domain immediately exposed a tenth: `observe()` spent its entire
60-element budget on banner and sidebar navigation, so on a real listing page
none of the products were ever observed and the planner planned blind about the
only part of the page the task concerned. Every fixture was too small for that
cap to bind.

The conclusion is not that the suite is bad — it is that **an eval set written
by the author of the code is blind in the direction the author was already
looking**, and that adversarial review and unfamiliar domains are the two things
that move that blind spot. That is the argument for treating the cold review as
a gate rather than an option.

## 6. Coverage

60 cases. Empty cells are shown, not hidden.

| Task class | Cases | | Difficulty | Cases |
|---|---|---|---|---|
| TC1 extract-on-page | 9 | | L1 | 16 |
| TC2 search-then-extract | 4 | | L2 | 11 |
| TC3 navigate-then-extract | 6 | | **L3** | **0 — deferred to B-strong** |
| TC4 interact-then-extract | 13 | | L4 (mutation/recovery) | 8 |
| TC5 form submission | 5 | | L5 (refusal) | 6 |
| mechanism/unit probes | 23 | | untagged (unit probes) | 19 |

| Domain | Kind | Cases |
|---|---|---|
| shop fixture | self-authored | TC1–TC4 + all 3 mutations |
| forms fixture | self-authored, POST ground truth | TC5 |
| hello fixture | self-authored | TC1 |
| nav-heavy fixture | self-authored | observation budget |
| offsite fixture | self-authored | URL-guard enforcement |
| **books.toscrape.com** | **live** | **TC3, 1 case** |

Also: 6 ZH-language cases (character-level, all with stubbed plans, so ZH
*planning* is unmeasured), 5 refusal cases, 6 trap cases, 3 DOM mutation types.

## 7. What is not measured — the complete list

The reviewer-facing version of this list, with per-row evidence, is
`docs/support-matrix.md`. In short:

1. **Planning quality — entirely.** Every case stubs the planner.
2. **Real cost and end-to-end latency**, beyond one M1 run at $0.0029.
3. **Verifier precision/recall** — no hand-labeled sample; traps are a floor.
4. **Live-domain breadth** — one domain, one task class, one case.
5. **The deployed system end-to-end** — see below.
6. **L3-difficulty tasks** — none exist.
7. Seven mechanism-level gaps carried deliberately, listed in ADR-005
   (anchors satisfiable by discarded evidence, relocation rung 1 ignoring the
   target's role, the progress-stream case grading the executor hook rather than
   the SSE endpoint, and four more), plus `near:` — advertised in the target
   schema in `specs/001` and never implemented in the resolver, which is why
   live table extraction is currently positional.

## 8. Deployment status — stated, not implied

The deployed instance at `https://whaleforce-browser-agent.zeabur.app/` is
**alive and serving the M1 deploy-spike build**. M2, M3 and M4 have not been
deployed: `/support-matrix` returns 404 there and the page still titles itself
"deploy spike". The reviewer UI, the trace viewer, the SSE progress stream and
the post-navigation URL-guard enforcement therefore exist in the repository and
in the local verification recorded in ADR-004, **not yet on the public URL**.

Until that is redeployed and re-verified, B-floor criteria 1 and 5 (deployed
frontend passes the smoke path; guards live on the public deployment) are
**not met**, and the held-out probe (T9) has not been run. This section is the
one a reviewer should read first, and it is deliberately not phrased as done.
