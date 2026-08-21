# ADR-013: TinBoker terminal styling belongs to the evidence surface

Date: 2026-08-21
Status: accepted

**Ruling**: The reviewer UI uses the TinBoker terminal language—amber commands, cyan interaction/recovery, compact squared surfaces, dark terminal and light paper-terminal palettes—without changing the trace-first information architecture or its stable DOM hooks; it remains a single inline page with no build step or external font dependency.
**Because**: The visual system should make command, recovery, failure and evidence states easier to scan without turning the review surface into a decorative dashboard or creating a second frontend architecture.
**Enforced by**: `evals/adversarial/ui-tinboker-style.json`, `stream-shows-every-step`, `gateway-error-contract-shape`

---

## Context

The original M4 page was intentionally plain: one inline HTML string, no
framework, and no build step. That architecture still fits the size of the
interface. The requested restyle uses the same TinBoker language applied in
`sec-10k-extract` PR #18, but this page is a run reviewer rather than a filing
inspector, so its existing order remains the design: command first, live trace
second, support evidence and declared limitations after it.

## Decision

Amber is reserved for the command path and section indexing. Cyan remains the
interactive accent and therefore also fits the existing recovery state. Green,
red and amber continue to carry success, failure and warning semantics. A
subtle grid, top keyline, monospaced type, squared chips, dark default palette
and light paper-terminal palette provide the TinBoker character without
introducing images, web fonts, JavaScript effects, or new dependencies.

The restyle also keeps the interface's evidence rules visible: superseded steps
remain fully legible rather than being faded, failed attempts keep their red
edge, recovery keeps its cyan edge, `postcondition_ok: null` still renders as
`unverified`, and the final trace still replaces provisional stream records.
All existing element ids used by the inline JavaScript are pinned by the style
case so a visual edit cannot quietly disconnect the form or evidence panels.

## Consequences

The page now adapts to the OS light/dark preference, provides explicit focus
outlines and reduced-motion handling, and lets wide evidence tables scroll on
narrow screens. Exact pixels and spacing are deliberately not part of the
case; the executable contract guards the style's distinguishing decisions and
the stable UI hooks, while ADR-004's existing cases continue to guard what the
page says about a run.
