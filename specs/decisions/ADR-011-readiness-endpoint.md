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
