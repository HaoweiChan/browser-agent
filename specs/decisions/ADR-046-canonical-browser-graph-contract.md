# ADR-046: define one canonical browser graph and cited evidence contract

Date: 2026-08-30
Status: accepted

**Ruling**: The future browser runtime has one graph — `observe → route → evidence → plan → act → evaluate → decide` — with bounded retry only to `plan`; deterministic `decide` alone routes to publish, review, or loud failure.
**Because**: the current `plan`/`loop`/`escalate` cadences duplicate control-flow explanations while finance failures need cited state and table evidence, not site recipes.
**Enforced by**: `canonical-contract-schema-binds-cited-evidence`, `canonical-budget-stops-before-next-run`, and M49's six red-first evidence contracts.

---

## Decision

1. M50 will implement exactly this graph:

   ```text
   observe → route → evidence → plan → act → evaluate → decide
                                  ↑                    │
                                  └── bounded retry ────┘
   ```

   `decide` is deterministic. It may publish only an accepted verifier result,
   retry only while the state retry budget remains, otherwise emits
   `review_required` or one existing loud `failure:<class>` through deterministic
   `route: failure`. M48 defines the
   contract only; it adds no LangGraph dependency or runtime.

2. Every evidence item is a cited packet bound to document id, URL, source bytes,
   and canonical rendered-text hash. Canonical text is UTF-8 HTML text nodes in
   document order with whitespace collapsed to one space; text citations carry
   half-open offsets into it. Table citations carry headers plus zero-based
   data-row/column coordinates; live-region citations name `running` or a
   terminal state. The model may propose actions but never
   creates evidence or overrides `evaluate`/`decide`.

3. Completed-run aggregate calls, tokens, USD, and wall-time limits stop the
   next submission at `>=` the frozen limit. This is honestly a stop line, not
   an absolute cap over an already in-flight call.

4. `plan`, `loop`, and `escalate` remain untouched until M50 supplies parity
   evidence: one canonical trace, shared resolver/executor/verifier/RunResult,
   unchanged INV-0 through INV-3 and screen, and no rule-6 selector or recipe.
   They are temporary comparators, not three permanent production flows. Their
   final retirement/replacement is an explicit M50 ADR ruling after that parity.

5. M44's 27/252 journal and reports remain historical evidence. Its old runner
   and cases are archived after the reusable budget-stop invariant is active;
   M48 does not add `X-LLM-Access-Key`, resume it, combine its journal, or make
   a default-mode claim.

## Consequences

- M49 supplies deterministic evidence extraction against the six frozen finance
  contracts, with companion offline same-origin-export and no-recipe checks.
- M51 may add bounded model nodes only behind this evidence and decide contract;
  the ADR-045 model ceiling and access control remain in force.
- RunResult, TraceStep, resolver, executor, verifier, screen, and rule 6 remain
  authoritative existing interfaces; the canonical state is an internal graph
  envelope, not a replacement result shape.

## Amendments

This amends ADR-027 Decision 1 only where it calls `loop` a peer mode rather
than a temporary comparator, ADR-028 only where it presents the loop driver as
a permanent control flow, and ADR-037 only where it rejects orchestration or
keeps `escalate` as a permanent third route. Their shared machinery, action
rules, RunResult/trace semantics, and all existing safety invariants remain.
