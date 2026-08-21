# ADR-011: `/readyz` answers whether the agent can take work; `/healthz` stays liveness

Status: accepted · 2026-08-21 · follows M9 (PR #19), prompted by support-matrix D18

**Ruling**: `/readyz` reports whether the single run slot is free, as structured JSON (`ready`, `busy`, `active_run_id`, `running`, `reason`), and always answers HTTP 200 — including when not ready; `/healthz` is unchanged and remains liveness only.
**Because**: through five aborted ablation sweeps `/healthz` answered in ~0.2s while submissions were failing, so the one operational question nobody could ask was whether the agent could take work — and a 503-when-busy readiness probe would invite the platform to restart a concurrency-1 service that is behaving exactly as designed.
**Enforced by**: `evals/adversarial/readyz-tracks-the-run-slot.json`

---

## Context

Support-matrix D18 records five ablation sweeps that aborted on transport or
wall clock, with `/healthz` fast throughout and — per the Zeabur dashboard — CPU
and memory far below capacity and no restart. The cause is still unknown. What
that episode did establish is a gap in observability rather than in capacity:
`/healthz` returns a literal `{"ok": true}` and proves only that the process is
running. It cannot distinguish "idle and able to start a task" from "busy with a
run" from "alive but wedged".

This ADR adds the smallest endpoint that closes that gap. It deliberately does
**not** add CPU or memory telemetry: the platform already publishes both, and
duplicating them in the app would be building a worse copy of evidence that
already exists.

## Decision 1 — readiness means "the run slot is free", not "submission would succeed"

`POST /tasks` always accepts a well-formed request and queues it behind
`asyncio.Semaphore(1)`. So readiness is about the capacity to **begin**
immediately, not permission to submit. `ready: false` means a task submitted now
will queue; it does not mean it will be refused.

Stating it this way keeps the endpoint honest about what a caller can conclude.
An operator who reads `ready: false` and infers "the service is rejecting work"
would be wrong, and the field naming plus `reason` are chosen so that inference
is hard to make.

## Decision 2 — always HTTP 200, including when not ready

This inverts the usual Kubernetes convention, deliberately. On a concurrency-1
demo service, "busy with a run" is the normal healthy state and can last minutes.
A readiness probe that returns 503 in that state invites the orchestrator to pull
the container out of rotation or restart it — turning a working service into an
outage precisely when it is doing its job.

The consequence is that `ready` lives in the body, not the status line, and any
consumer must read the body. That is the correct trade here and it is the reason
the case grades the JSON rather than the status code.

## Decision 3 — the contract, and its invariants

```json
{"ready": true, "busy": false, "active_run_id": null, "running": 0, "reason": null}
{"ready": false, "busy": true, "active_run_id": "1a2b3c4d", "running": 1,
 "reason": "a run is executing (1a2b3c4d)"}
```

Invariants, all graded:

1. `ready == not busy` — the two never disagree, so a reader may use either.
2. `active_run_id` is non-null exactly when `busy`, and is the id of the run
   holding the slot. A boolean alone cannot answer "which run is wedged", which
   is the question an operator actually has.
3. `reason` is non-null exactly when not ready.
4. `running >= 1` whenever busy (it counts records still in `running`, so it
   includes anything queued behind the slot as well as the one holding it).
5. Reading `/readyz` starts nothing, launches no browser, and spends nothing.

## Decision 4 — what it proves, and what it does not

**Proves**: the event loop is serving requests, and the slot state as the app
understands it. The second one matters more than it looks: `/readyz` is served by
the *same* event loop that runs the agent, so a prompt `busy: true` answer while
a run executes is positive evidence that the loop is **not** blocked — one of the
named open candidates in D18. Measured in the case: 5 ms, mid-run.

**Does not prove**: that a browser can launch, that the outbound network is
healthy, that a submitted run will succeed, or that the container is not about to
be restarted. It reads process-local state. In particular it cannot diagnose the
D18 failures on its own — it narrows them, by making one candidate testable.

## Decision 5 — graded as a transition, not a status code

A readiness endpoint is trivial to fake. `ready: true` hardcoded passes any check
taken against an idle service; `ready: false` hardcoded passes any check taken
mid-run. So the case takes **all three samples from one submission** — idle,
busy-with-this-run-id, idle again — and asserts the sequence.

Discrimination measured rather than assumed: seven wrong implementations were
written and all seven turn the case red — `ready` pinned true, `ready` pinned
false, `busy` pinned false, `active_run_id` never set, `active_run_id` never
cleared, `reason` always present, and `running` pinned to zero.

The busy window is made deterministic by stubbing the planner to hold for a fixed
interval. The planner is awaited inside `async with SEM`, so the slot is
genuinely held, with no browser work and no spend.

## Decision 6 — the soak, and what it concluded

`evals/soak.py` runs five representative tasks sequentially against a deployment
and records, per task: `/readyz` before, submission outcome, `/readyz` and
`/healthz` mid-run, terminal status, answer, correctness, the run's own duration,
the client's wall clock, `/readyz` after, and any transport failure **tagged with
the phase it happened in**. The phases exist because D18's unanswered question is
*where*: client could not connect, server rejected, accepted but stalled, poll
path failed, or completed-but-result-lost. "It timed out" does not distinguish
those, and they have different fixes.

Correctness is recorded and is deliberately **not** the pass criterion. One task
in the set carries a known capability limitation (D17), and picking a set that
scores 5/5 would mean picking tasks that flatter the system.

**Result: 10/10 across two back-to-back sequences, zero infrastructure failures**,
no transport error in any phase, client wall clock 4.68-13.53s with no upward
drift. Spend $0.0622.

**Conclusion: the current 2 vCPU / 8 GB deployment is demo-ready under
interview-shaped sequential workloads** — demonstrated, on the deployment, not
argued from headroom.

Three things that conclusion does not carry:

- It does **not** retro-diagnose D18. The honest reading of the contrast between
  ten clean runs and five aborted sweeps is that **workload shape** differs, not
  capacity — same container, same limits. No mechanism is inferred from it, and
  D18's open candidates stay open.
- The runs were served by the **deployed** build, whose default is still
  `anthropic/claude-sonnet-4.5`. PR #19's move to `openai/gpt-5.6-luna` is not
  merged, so the latency and correctness numbers belong to the previous default.
  The infrastructure conclusion holds either way; the per-task numbers should be
  re-read after the merge.
- `/readyz` answered **404 on all thirty probes**, because it is not deployed
  yet. The soak records the 404 rather than dropping the column, so the gap is
  visible in the artifact. The readiness-transition half of this evidence is
  pending a redeploy, and re-running the soak afterwards is the one outstanding
  step — not a new experiment, the same one with the column filled in.

**If it had failed**, the discipline was fixed in advance: classify the phase
first, then propose the single smallest experiment that discriminates between
event-loop blocking, ingress, and client timeout handling — never patch a timeout
constant or add a retry as the first move. The existing side-effect rule stands
either way: a connection-phase failure that provably never reached the server may
be retried; an ambiguous read timeout must not be, because execution may already
have started.

## Decision 7 — the soak re-run, with `/readyz` deployed

Decision 6 left one step open: `/readyz` existed but was not on the deployment,
so all thirty probes in the first soak returned 404. PR #19 merged, Zeabur
flipped, and the same command was re-run — not a new experiment, the same one
with its missing column.

**Result: 10/10 again, zero infrastructure failures**
(`evals/report/20260821-145535-soak.json`), now serving the new default
`openai/gpt-5.6-luna`. Client wall clock 4.71-13.73s, spend $0.0063.

The readiness evidence, which is what the re-run was for:

- **30/30 probes answered 200 with the contract intact** — ready before every
  submission, busy during every run, ready after.
- **`active_run_id` matched the submitted run id 10/10.** The endpoint does not
  merely report *a* busy state, it reports the right run.
- Probe latency 0.128-0.218s overall, and the **while-busy** probes are the same
  0.128-0.218s (mean 0.174s).

That last figure is the one worth keeping. `/readyz` is served by the same event
loop that runs the agent, so ten prompt answers taken *while a run held the
semaphore* are positive evidence the loop is not blocked during a run. **Of
D18's three named candidates, event-loop blocking is now the weakest.** It is
narrowed, not eliminated — this measures an idle-ish loop under one run, not the
loop under whatever conditions produced the aborts — and the other two
candidates, Zeabur ingress and the client's own connection handling, are
untouched by it.

The soak still does not retro-diagnose D18, and the contrast between ten clean
runs and five aborted sweeps on the same container still says **workload shape**
rather than capacity. No mechanism is inferred from it here either.

**Two observations that arrived with the model change**, recorded because they
cut against a comfortable reading rather than for it:

1. Correctness moved 8/10 to 7/10. Correctness is context in this exercise, not
   the criterion, and the set was chosen to include a known limitation.
   `live-books-travel-price` failed both sequences on a `near:` proximity
   ambiguity — D17's family, and notably a task this same model answered
   correctly during the ablation.
2. **`tc5-forms-submit` failed once and passed once — same model, same page,
   same build, minutes apart.** That is first-hand nondeterminism inside a single
   soak, and it is direct support for ADR-010 Decision 18's refusal to read the
   ablation's four-way correctness tie as equivalence. A cell that flips between
   two runs of one sequence is a cell that cannot carry a between-model
   comparison at n=1.

## Decision 8 — the soak driver was ungraded, and it was wrong in four places

Decisions 6 and 7 publish every number `evals/soak.py` produced. A PR #21 review
asked the question nobody had: **what grades the thing that produced them?**
Nothing did — 206 lines with no eval case of any kind, next to a sibling
(`evals/ablation.py`) with three. The measured consequence is that four defects
were live in a tree the gate scored 29/29 invariant and 93/93 fast:

1. **A run that never got off the ground counted as a clean completion.**
   `completed` was every row without a *client-side* transport error, and a
   terminal record of `failure:env` — the answer a deployment gives when its
   planner cannot start at all — carries none. A soak against such a deployment
   would have printed `5/5 completed without an infrastructure failure` and
   published `demo_ready: true`. The driver already computed
   `measured=is_measurement(...)`, False for exactly those rows, and aggregated
   it nowhere. A completion is now a row `is_measurement` accepts; everything
   else is listed under `not_a_measurement` and blocks `demo_ready`.
2. **The phase taxonomy — the stated reason the soak exists — mis-tagged the one
   distinction this repo has already established matters.** Only `HTTPError`
   mapped to "server rejected"; every other exception fell to
   `1-client-could-not-connect`, which is a claim that *nothing was delivered*.
   A read timeout raises a bare `TimeoutError` and happens only **after** the
   POST landed; an unparseable body and a 200 with no `run_id` are the same
   family. Those now report `2b-delivered-but-outcome-unknown`, because a run
   may be executing and billing while the client calls it a connect failure.
3. **A retried transport failure left no trace.** `_http` retries connect-phase
   failures up to three times — precisely the D18 family the soak was written to
   observe — and neither printed nor returned the swallowed attempts, so
   "zero infrastructure failures, no transport error in any phase" was not
   readable off the artifact it cites. Retries are now collected per row.
4. **Correctness was not this repo's correctness metric.** Raw `str ==` rather
   than `verifier.answers_match`, and without requiring `status == "success"`,
   while Decision 7 point 1 cross-compares the figure against the ablation's
   `answers_match` cells. Two of the five tasks are currency answers where the
   rules can diverge (`answers_match('$39.00', '39.00')` is True).

**What this does and does not change about Decisions 6 and 7.** Every committed
soak row is `measured: true`, and recomputing correctness under the ablation's
rule returns **the same 8/10 and 7/10** — so the published figures stand, and
they are now the same metric the ablation's cells are. The one claim that is
genuinely narrowed is "zero infrastructure failures": for the three committed
reports it means *no connect failure that survived up to three retries*, and
those artifacts cannot say more. That bound is recorded in D20 rather than
retro-fixed, because the soak spends real money and a re-run to improve the
wording of a past result is not a reason to spend it.

**Because** the general lesson is the one this repo keeps relearning: a number's
credibility comes from the case behind the code that produced it, not from the
document that prints it. `soak-counts-only-real-completions` drives the real
`run_one` against a stubbed transport and pins the exception→phase table, the
completion rule, the retry ledger and the correctness rule; `docs-numbers-are-derived`
stops README's case counts and D8's wall-clock range being hand-maintained at all.
Both watched red against the pre-fix tree. No network, no browser, $0.00.
