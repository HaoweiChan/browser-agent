# 018 — M51: two fresh reviews changed the public truth

**Date**: 2026-08-30 · **Milestone**: M51 · **Outcome**: cold review and a
separate spec-drift audit added seven falsifications before the gate was
allowed to close. Evidence is in
`docs/evals/m51-multimodel-policy-red-first-ledger.md`.

## Context and condensed prompt

After the focused M51 suite first reached 8/8, the implementation was handed
to two fresh readers: one asked for the three most likely silent production
failures; the other compared implementation, contract, ADR, and tracker text.
Neither reviewer was asked to confirm the design.

## Decision

The recommendation was **accepted**: every M51-severity finding became an
offline adversarial case before repair. The final focused suite grew from 8 to
11 cases and reached 11/11 without provider, network, or paid-model calls.
Pre-existing contract gaps found by the drift audit were repaired in the same
milestone where they affected the public result envelope.

## Assumption → Eval contradiction → Correction

- Assumed: returning the requested primary model at the top level was an
  adequate description of a fallback-capable run.
- Eval said: `m51-cli-attributes-the-actual-served-model` reproduced GPT-5 mini
  serving the plan while the CLI still claimed DeepSeek V4 Pro.
- Corrected: server and CLI derive the public planner model only from actual
  `plan` node telemetry; critic calls cannot contaminate that field.

- Assumed: a provider completion without usage data could be counted as zero
  and cached because the content itself was valid.
- Eval said: `m51-provider-usage-is-required-before-cache` showed this silently
  certified unaccounted spend and replayed it.
- Corrected: required usage fields are validated before spend mutation or
  cache insertion; incomplete accounting fails closed.

- Assumed: any under-ceiling route override was safe at the central boundary.
- Eval said: the extended `m51-node-policy-is-central-and-price-bounded` case
  routed planning through Flash even though the node's frozen route excluded it.
- Corrected: an override must be a subset of that node's frozen route as well
  as satisfy the global price ceiling.

- Assumed: a cached string that later failed plan parsing could remain cached.
- Eval said: the extended cache case replayed the same malformed plan without
  reaching transport again.
- Corrected: parse failure evicts that exact cache record, so the next attempt
  is a bounded transport retry rather than a permanent poisoned hit.
