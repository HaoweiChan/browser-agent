# ADR-004: The reviewer UI, and what it is not allowed to hide

Date: 2026-08-16
Status: accepted

**Ruling**: The SSE trace stream emits every attempted step in order, including ones a recovery ladder superseded, and `postcondition_ok` renders three-valued (`null` = unverified, never a tick); `docs/support-matrix.md` is parsed live at request time, never duplicated into JSON; every gateway failure path returns the RunResult contract shape through one shared assembler.
**Because**: A UI can fail quietly by rendering a truthful run flatteringly, in a way no execution-shaped eval would ever catch.
**Enforced by**: `evals/adversarial/stream-shows-every-step.json`, `support-matrix-cites-real-cases.json`, `gateway-error-contract-shape.json`

---

## Context

M4's validation is a stranger test: someone who has not read this repo should be
able to submit a task, watch it run, and inspect a failure. That makes the
frontend an evidence surface, not a demo. The risk it introduces is specific and
new — every earlier milestone could only fail loudly, because nothing stood
between the trace and the reader. A UI can fail *quietly*, by rendering a
truthful run in a flattering way, and no eval in the suite would go red.

## Decision 1 — the stream is the trace, not a highlight reel

`GET /tasks/{id}/stream` emits every attempted step, in order, including the
ones a recovery ladder supersedes (contract: specs/001). The executor gained one
`on_step` hook; the gateway turns it into SSE.

The temptation this refuses is real: the tidy version of the M3 recovery run is
two steps that worked. The honest version is four, one of which died at `locate`
and was superseded. `stream-shows-every-step` was watched red on exactly that
mutation — emitting only steps whose execution raised nothing. Under it the run
still returns `success`, the terminal status still matches, and the surviving
ids are still in order (1,3,4); only the failed-attempt check goes red. A
presentational lie needs a case shaped to catch presentation, because every
execution-shaped check stays green through it.

Three-valued `postcondition_ok` is rendered three-valued. `null` shows as
`unverified`, not as a tick: the contract calls a null postcondition on a click
an unverifiable action, and a green tick there would contradict the invariant
that produced it.

## Decision 2 — one source for the support matrix

`docs/support-matrix.md` is parsed at request time and served to the frontend.
The alternative — a JSON copy beside the markdown — puts the graded honesty
artifact in the one shape guaranteed to drift, where the README says one thing
and the deployed page says another. Cost of this choice: the image now ships
that one doc file (`.dockerignore` excludes `docs` except this file).

`support-matrix-cites-real-cases` checks that citations **resolve**, never that
a declared status is correct. Declaring stays a human act
(`docs/evals/evaluation-methodology.md`); a pass rate that thresholds itself
into "supported" is what that document forbids. Watched red by renaming a cited
case id in the doc.

Stated so the coverage is not overread: the case does not catch a citation that
resolves but is stale in its claim. M4 had exactly one — a row reading
`unsupported until the M3 relocation loop` whose cited case had already flipped
to success — and the case was green throughout. It was corrected by hand. The
gap is real and not currently closable by code: nothing distinguishes "cites a
case that still fails" from "cites a case that encodes a limitation and
therefore passes" (`trap-near-miss-entity` is the second kind).

## Decision 3 — the gateway's failure path is a RunResult

Found by driving the UI rather than reading it: with no `OPENROUTER_API_KEY`,
the gateway returned `{status: failure:env, evidence: null, budgets_spent: null}`
— correctly classified, loud, and not the contract shape. `live_planner()`
validates the key at construction, so it raises as an argument expression before
`run_task` is entered, and `contract-trace-schema` never saw the path because
that case grades `run_task`'s return value.

The catch-all now goes through `assemble_result`, so there is one assembler and
no hand-built results. Fail-fast is deliberately kept: a missing key is
diagnosed before a browser launches, so the empty trace is correct and only the
shape was ever wrong.

A `finally` guarantees a terminal record. This is not hypothetical — while
fixing the above, the error path itself raised, the run sat in `running`
forever, and the SSE stream never closed. On a public endpoint that is a hung
connection and a reviewer watching a spinner with no end.

## Consequences

Buys: a reviewer can see a strategy switch happen, expand the failed attempt,
and look at the screenshot taken at the moment it failed — the M3 mechanisms
become visible rather than merely reported. Three UI-shaped failure modes now
have cases, one of which (the stream) can only be caught by a case written
against presentation.

Costs: the frontend is a single inline page with no build step and no
framework — deliberate, but it means the trace viewer is not independently
unit-tested; `stream-shows-every-step` grades the data it receives, not the DOM
it produces. The rendering was verified by hand against a real recovery trace,
which is evidence for this commit and not a standing check.

Not done, and not pretended otherwise: the stranger test has been run against a
local instance, and the guard, stream, screenshot and matrix paths verified
there. The live-planner submit path needs a key, so end-to-end on the deployment
is verified at M5 with the held-out probe, together with the first `full`-suite
numbers.
