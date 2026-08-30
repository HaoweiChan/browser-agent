# ADR-047: publish only the canonical browser runtime

Date: 2026-08-30
Status: accepted

**Ruling**: Public HTTP and CLI runs use only the canonical graph; `decide` is the sole deterministic publish/retry authority, with at most one safe retry and hash-bound snapshot evidence.
**Because**: keeping three public cadences made it possible for a request to bypass the one evidence and decision boundary that M50 proves.
**Enforced by**: `m50-public-canonical-only`, `m50-canonical-verifier-retry-clears-attempt`, `m50-canonical-state-change-retry-refused`, and `gateway-canonical-selects-planner`.

---

## Decision

1. `POST /tasks` accepts omitted or explicit `canonical` only; its default is
   canonical and its model/default/environment failures retain the existing
   loud RunResult shape. The CLI passes `mode="canonical"`. Public UI language
   describes the run outcome, not internal cadence names.

2. The gateway always constructs a live planner and calls
   `run_task(mode="canonical")`; it never constructs a legacy driver. `plan`,
   `loop`, and `escalate` remain direct injected `run_task` comparators for
   bounded evals, not gateway or CLI options.

3. `observe → route → evidence → plan → act → evaluate → decide` is the only
   public control flow. `decide` may publish a deterministic PASS, issue one
   retry only back to `plan`, request review, or emit an existing loud failure.
   A judge never overrides this decision.

4. Retry is refused after any unsuperseded action in `STATE_CHANGING`, even if
   its postcondition failed or a later read failed. A verifier-only retry drops
   only the prior attempt's answers/extractions and supersedes its read before
   the next attempt; it does not erase the trace.

5. Snapshot evidence remains bound to source and canonical text hashes.
   Citation offsets are half-open offsets into that canonical text; non-rendered
   head/title bytes stay source-hash-bound but are not selectable visible text.

## Consequences

- Canonical runs retain the same RunResult interface and add their control-flow
  projection after completion.
- Planner, navigation, and environment errors fail loudly; deterministic
  verification, not a model judge, settles final authority.
- The legacy implementations and their historical ADR evidence remain available
  only to the bounded eval comparators that exercise them.
- The clean local invariant band is republished in ADR-019 §3; its measured
  39.91s still leaves the existing 70s ceiling unchanged.
- The clean local fast run measured 114.81s. ADR-013's existing rule derives
  135s, so ADR-019 §2 and `WALL_BUDGET_S` move 130 → 135; the pre-fix guard
  failed exactly on that requirement in
  [`20260830-112130-invariant.json`](../../evals/report/20260830-112130-invariant.json).

## Amendments

This supersedes ADR-027 Decision 1, ADR-028, and ADR-037 only where they expose
`plan`, `loop`, or `escalate` as public gateway/CLI cadences. It also updates
ADR-045's public-gateway enforcement citation. Their historical records,
direct-comparator semantics, action safety rules, and evidence remain intact.
