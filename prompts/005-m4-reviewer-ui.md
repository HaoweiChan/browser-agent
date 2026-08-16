# 005 — M4: a UI is the first component that can lie quietly

**Date**: 2026-08-16 · **Milestone**: M4 · **Outcome**: 52/52 fast, 12/12
invariant, $0.00; SSE trace stream, trace viewer, live support matrix; ADR-004.

## Context

M4's validation is a stranger test: someone who has not read the repo submits a
task, watches it, and inspects a failure. The framing that shaped the whole
milestone came from asking what is *new* about this risk surface. Every earlier
stage could only fail loudly — nothing stood between the trace and the reader.
A UI can fail quietly, by rendering a truthful run in a flattering way, and no
execution-shaped check goes red for it.

So the milestone's first artifact was not the page. It was a case written
against *presentation*.

## Assumption → Eval contradiction → Correction

- Assumed: the progress stream is plumbing — the trace is already the
  deliverable, so streaming it is a transport detail.
  Eval said: `stream-shows-every-step`, mutated to emit only steps whose
  execution raised nothing, still produced a **successful run, a matching
  terminal status, and step ids in order** (1,3,4). Every execution-shaped
  check stayed green while the viewer hid the failed text-tier click that the
  M3 relocation ladder recovered from.
  Corrected: every attempt is emitted, including superseded ones, and the case
  asserts the failed attempt's presence rather than just ordering.

- Assumed: the gateway returns the documented `RunResult` on every path.
  Found by *driving the UI*, not by reading it: with no `OPENROUTER_API_KEY`
  the result came back `{status: failure:env, evidence: null,
  budgets_spent: null}` — correctly classified, loud, and not the contract
  shape the frontend renders. `live_planner()` validates the key at
  construction, so it raises as an argument expression before `run_task` is
  entered, and `contract-trace-schema` never saw the path because that case
  grades `run_task`'s return value.
  Corrected: one assembler for every result; case
  `gateway-error-contract-shape`.

- Assumed: a rejected submission is a dead end the user simply retries.
  Found by clicking the button twice: the rejection path never re-enabled it,
  so the URL guard working *once* disabled the form permanently. The UI looked
  broken by its own success.
  Corrected in the JS, with the reason written next to it.

- Assumed (briefly): the fix for the hung-run bug could be a bigger try block.
  Reality said: while fixing the contract-shape bug, the error path *itself*
  raised, the run sat in `running` forever and the SSE never closed — a hung
  connection on a public endpoint.
  Corrected: a `finally` that guarantees a terminal record.

## Method note

Three of the four corrections above were found by operating the interface, not
by reading the diff. That is the argument for the stranger test being a real
step with a real browser rather than a checklist item.
