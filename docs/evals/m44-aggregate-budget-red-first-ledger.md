# M44 aggregate campaign budgets — red-first ledger

Date: 2026-08-30

| Case | Before implementation | After implementation |
|---|---|---|
| `m44-campaign-enforces-aggregate-budget-stops` | `passed: false`, `unknown_check: aggregate-budgets` | missing metadata is rejected; exact token/call boundaries stop before I/O; below-boundary totals continue; changed recovery limits are rejected |

The case is synthetic: zero network, browser, or model calls. The discovery came
from the live-campaign preflight, but no paid M44 run was submitted.

Fixed-point reports: `evals/report/20260829-204709-invariant.json` was 112/116,
recording four derived publication reds at the new 116-case count; after those moved,
`evals/report/20260829-205053-invariant.json` was 115/116 with only its own
previously-uncitable report artifact red. The following no-report gate is the
green proof.
