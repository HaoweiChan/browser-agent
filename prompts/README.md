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
