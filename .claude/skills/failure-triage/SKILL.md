---
name: failure-triage
description: SOP for classifying a new failure case before fixing it. Use whenever an eval case fails, a user-reported or held-out input breaks the pipeline, or output looks wrong for unknown reasons.
---

# Failure triage

Never jump from "it failed" to "fix it". Classify first — the class decides
where the fix goes and whether the eval set grows.

## Steps

1. **Reproduce minimally.** Shrink the input to the smallest thing that still
   fails. The minimal repro becomes the adversarial case, not the original blob.
2. **Classify** into exactly one:
   - `input-variant` — a legitimate format/structure we don't handle yet.
     Fix in the pipeline; case goes to `evals/adversarial/`.
   - `invariant-gap` — output violated a property no invariant was checking.
     FIRST add the invariant (watch it fail), THEN fix.
   - `spec-ambiguity` — it's genuinely unclear what correct means here.
     Do not code. Write/extend an ADR with the judgment call, then encode it.
   - `flake` — nondeterminism (network, LLM sampling, timing). Fix the
     determinism problem or quarantine the case; never retry-until-green.
   - `eval-bug` — the case or adapter itself is wrong. Fix the eval, note it
     in the case's `"provenance"`.
3. **Record**: one line per triaged failure in the case JSON
   (`"triage": {"class": ..., "note": ...}`).
4. **Only then fix.** The fix is done when the new case passes AND the fast
   suite hasn't regressed.

## Smell checks

- Fixing the same class in the same module twice → the abstraction is wrong,
  stop patching and write an ADR.
- A fix that flips >2 previously-passing cases → revert, re-triage.
