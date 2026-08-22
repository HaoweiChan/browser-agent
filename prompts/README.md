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
rewritten to look right in hindsight — the same principle ADR amendments
follow (struck, not deleted; `specs/decisions/ADR-015-a-freeze.md`'s M29
amendment is the example). A later correction gets a new numbered file (the
M5 reopen is `prompts/008-a-level-reopen.md` after `007`) or a cross-link
from the current source of truth (`specs/decisions/`), not an edit to the
original. A prompt file's own outcome line reading stale after later events
is expected, not a defect — that is precisely what distinguishes a dated
record from a live one (PR #28 R3).
