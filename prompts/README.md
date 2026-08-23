# Prompt records

The assignment reviewers read this folder. One layer:

- `00N-<topic>.md` (this directory) — curated records in reading order, one per
  meaningful chunk of work (ADR-001). Each contains: context, the prompt
  (condensed), the resulting decision, whether the AI recommendation was
  accepted / rejected / modified, and why.

## Index

| # | Record |
|---|---|
| [001](001-project-planning.md) | Project planning: Task 1 scoped, reviewed, compressed |
| [002](002-m1-walking-skeleton.md) | M1: walking skeleton, deploy spike, first real failures |
| [003](003-m2-eval-backbone.md) | M2: eval backbone, and the grader turning out to be the weakest link |
| [004](004-m3-reliability.md) | M3: recovery ladders, and the metrics that refused to flatter them |
| [005](005-m4-reviewer-ui.md) | M4: a UI is the first component that can lie quietly |
| [006](006-cold-review-and-freeze.md) | The cold review, and what a live domain found in one afternoon |
| [007](007-m5-freeze-and-held-out-probe.md) | M5: the freeze, and the probe that made it worth doing |
| [008](008-a-level-reopen.md) | Reopening after the freeze: the A-level directive |
| [009](009-m6-live-breadth.md) | M6: live breadth, and what a suite going green does not prove |
| [010](010-navigation-wait-condition.md) | The outage that was half ours |
| [011](011-external-review-pr9.md) | An outside reader on PR #9: best-effort ≠ bounded |
| [012](012-m7-verifier-accuracy.md) | M7: verifier accuracy, and the audit that changed the headline |
| [013](013-m8-mutation-hostility.md) | M8: mutation & hostility, and a counter that took two rounds to become true |
| [014](014-a-freeze.md) | M10: A-freeze, and the probe that failed the milestone it was gating |
| [015](015-agent-control-after-the-probe-regression.md) | After the probe regression: MCP, tool-calling loops, and what actually limits completion |
| [016](016-m40-demo-surface-and-investment-domains.md) | M40: the demo surface, and what 43 live runs said about finance pages |

## Curated file format

The valuable artifact is not the final polished prompt — it is the correction
chain. Every curated file ends with:

```
## Assumption → Eval contradiction → Correction
- Assumed: <what we believed when writing the prompt/code>
- Eval said: <the case/run that contradicted it, with case id>
- Corrected: <what changed — prompt, code, invariant, or ADR>
```

One chain entry per real correction. If a curated file has no chain entries,
it probably wasn't worth curating.

## Append-only

A curated file records what was known and decided on its date and is never
silently reworded to look right in hindsight. Two things are both true at
once, the same way they are for an ADR: nothing is deleted, and a claim the
record shows was later falsified gets struck in place with a dated pointer
to the correction — exactly `specs/decisions/ADR-015-a-freeze.md`'s M29
amendment convention (struck-not-deleted, per its own citation of the
A-level plan's criterion-7 precedent), applied here to `prompts/014-a-freeze.md`
(PR #28 R5). A new milestone's own reopening still gets a new numbered file
(the M5 reopen is `prompts/008-a-level-reopen.md` after `007`) rather than an
edit to the prior one — striking is for a specific sentence later evidence
falsified, not for narrating a new chapter of work. An UNSTRUCK claim that
later turned out false is a live defect, not a dated record, which is why
`docs-numbers-are-derived`'s criterion5 check scans `prompts/` like any other
tracked markdown rather than excluding it (PR #28 R5).
