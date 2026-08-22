# Prompt records

The assignment reviewers read this folder. One layer:

- `00N-<topic>.md` (this directory) — curated records in reading order, one per
  meaningful chunk of work (ADR-001). Each contains: context, the prompt
  (condensed), the resulting decision, whether the AI recommendation was
  accepted / rejected / modified, and why.

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
