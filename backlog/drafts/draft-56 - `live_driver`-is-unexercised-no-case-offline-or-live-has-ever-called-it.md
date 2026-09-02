---
id: DRAFT-56
title: '`live_driver` is unexercised: no case, offline or live, has ever called it'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-2
  - M42 implementation
  - 2026-08-26.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`planner.live_driver` builds the OpenRouter tool-calling payload, sends it, and turns the response into a step through `parse_tool_call`. Its pure parts are reachable and partly graded — `build_driver_user`, `trace_digest`, `TOOLS`, `parse_tool_call` are all module-level and pure — but the function itself has been executed exactly zero times, offline or live, because `OPENROUTER_API_KEY` is not set in this environment and no `full`-tagged case asks for `driver: "live"`. The eval adapter accepts `input.driver == "live"`, so the hook exists; nothing pulls it. This is the same epistemic split ADR-027 declares for the loop generally ("what the stub cannot grade is the live model's step choices"), but it is WIDER than that sentence admits: what is ungraded here is not only the model's choices, it is whether the request this code builds is one OpenRouter accepts at all — a wrong `tools` shape, a provider that ignores `tool_choice: "required"`, or a `tool_calls` envelope shaped differently from the assumption in `parse_tool_call` would each be invisible until the first live run.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a `full`-tagged case with `driver: "live"` against a fixture, run manually with a key, its run id and cost published — plus, if the first attempt finds an envelope mismatch, an adversarial case pinning that shape through `parse_tool_call` at $0. Blocked on a key, not on design; M42's live smoke is the natural place it gets exercised for the first time.
<!-- AC:END -->
