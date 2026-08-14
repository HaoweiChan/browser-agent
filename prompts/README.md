# Prompt records

The assignment reviewers read this folder. Two layers:

- `raw/` — auto-dumped by the SessionEnd hook: every user prompt from each
  Claude Code session, one file per session. Unedited exhaust.
- `YYYY-MM-DD-<topic>.md` (this directory) — curated records, distilled from
  raw/ after each meaningful chunk of work.

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
