# ADR-044: Require aggregate token and planner-call stops before M44 spends

Date: 2026-08-30
Status: accepted

**Ruling**: M44 execution and recovery require explicit USD, token, and
planner-call stop lines; all three are frozen in the journal and checked between
completed runs before another task is submitted.
**Because**: the zero-spend campaign preflight found that the report already
totalled tokens and planner calls but `execute()` bounded neither aggregate.
**Enforced by**: `m44-campaign-enforces-aggregate-budget-stops` and
`m44-campaign-partial-evidence-stays-loud`.

## Decision

1. `--execute` and `--recover` require the operator to spell out
   `--max-usd`, `--max-tokens`, and `--max-planner-calls`. There is no implicit
   authority to use the historical US$160 suggestion.
2. Store the exact three stops in `campaign_start`. Recovery with different
   values fails before build discovery, readiness checks, or task submission.
3. Before every next submission, compute totals through the same `summarize()`
   path that publishes campaign metrics. Reaching any stop appends a durable,
   attributed abort containing all completed totals.
4. Keep the runner sequential and add no dependency, service, or second
   accounting implementation.

## Evidence and limits

The synthetic red-first case initially failed as an unknown check. The green
case builds one valid completed run, sets the token and planner-call stops at
that run's exact totals, and proves recovery writes an abort without any build,
readiness, or HTTP attempt. It separately proves values below the boundary do
not stop and a changed recovery value is refused.

These are completed-run stop lines, not absolute caps. One already-delivered
run can cross any line before the result is readable; production loop limits
are themselves post-call, judge attempts still have no per-run token/USD cap,
and client scheduling can overshoot wall time. Every report continues to state
those limits. This decision authorises no paid campaign run; spend still needs
separate operator approval.
