# Failure taxonomy, self-correction, and self-maintenance — Task 1

Self-correction and self-maintenance are **distinct mechanisms with distinct
tests**: correction = diagnose a failed step and switch strategy; maintenance =
detect that a previously working locator no longer matches and relocate the
semantic target. Conflating them into "retry" is the failure mode the
assignment explicitly grades against.

## Failure classes — 7 top-level, subclasses accrete

Subclasses are NOT pre-designed. They accrete through the failure-triage loop
(`.claude/skills/failure-triage/`) as real runs reveal them — pre-built
taxonomies measure fidelity to our own guesses. Every run's failure carries
**exactly one** top-level class.

| Class | Meaning | Detection signal | Evidence stored |
|-------|---------|------------------|-----------------|
| `nav` | navigation didn't reach a usable page | URL/load-state mismatch vs expected_state, timeout | URL history, response codes |
| `locate` | semantic target could not be resolved to a usable element | resolver returns 0 or >1 unresolvable candidates; stale cached locator | a11y snapshot digest, candidate list + scores |
| `act` | action executed but had no observable effect, or was blocked | postcondition unchanged after action; overlay intercepts; input rejected | pre/post observation diff, screenshot |
| `extract` | extraction empty or inconsistent with the visible page | empty result; extracted value absent from page text | extracted value, page-text digest |
| `semantic` | executed "successfully" but the goal is not satisfied | OutcomeVerifier verdict (incl. identity-anchor miss) | verifier verdict + cited evidence |
| `env` | browser/network/runtime failure, incl. bot-blocked | crash, net error, challenge page detected | error, screenshot. Bot-block → **stop + mark unsupported, never evade** |
| `task` | task itself out of scope | pre-flight screen or mid-run discovery (login wall) | refusal reason |

## Self-correction loop

```
OBSERVE → CLASSIFY → HYPOTHESIZE → SELECT STRATEGY → EXECUTE → VERIFY
```

- **CLASSIFY** is deterministic (rules over Playwright errors + page state) —
  no LLM in the classifier at B-level.
- **Recovery ladders are evidence-driven, not pre-built.** The M2 baseline run
  produces the observed failure distribution; the scope checkpoint then selects
  the **highest-value families, up to 3, minimum 2 genuinely distinct**,
  prioritized by frequency × reviewer value × engineering feasibility — never a
  third family just to fill a quota. All other classes get detect + classify +
  loud stop [MUST]; their ladders are BACKLOG.
- Ladder rungs must be *different strategies*, not parameter-stepping. Example
  shapes: `locate` → re-observe fresh snapshot → relocation via next semantic
  tier → **alternate-path replan** (e.g. use the site's search instead of menu
  navigation) → evidence-fed LLM replan → stop. `act` → dismiss overlay →
  alternative control for the same intent → replan → stop.
- **Retry vs recovery is a trace-level flag**: re-observe/scroll/wait rungs are
  logged as `retry`; only classify → strategy-switch → verified-success counts
  toward the recovery metric. "Retry with LLM" is structurally impossible to
  log as recovery.

### Budgets (invariant-backed, enforced in code)

≤ 2 corrections per step · ≤ 2 replans per task · global action budget (~30) ·
global token budget per run. Exhaustion → loud classified failure with the full
trace; never a quiet stop.

### What the frontend exposes

Per step: failure class, hypothesis, chosen rung, retry-vs-recovery flag,
before/after screenshots. An evaluator can see *that the strategy changed and
why* — this is the E1 (`mechanism-substance`) evidence.

## Self-maintenance

- **Locator abstraction**: plans reference `SemanticTarget{role, name, text?,
  near?}` — never concrete selectors. A deterministic Resolver compiles a
  target against the current accessibility snapshot into ranked candidates.
- **Tier order and tradeoffs**: role+accessible-name (survives cosmetic change,
  needs decent ARIA) → text/label (robust, breaks on copy changes) → stable
  attrs id/data-*/name (precise, most brittle under refactors) → structural
  relations (last resort, most fragile). Ranking = uniqueness × visibility ×
  tier prior × cached history.
- **Stale detection**: a cached locator fails to resolve OR resolves to an
  element failing sanity checks (role/text mismatch vs the SemanticTarget).
- **Relocation loop**: stale → re-observe → regenerate + rank fresh candidates
  from the a11y snapshot → act → verify postcondition. Success = the *semantic*
  outcome matches the unmutated baseline.
- **Locator cache** per (site, target) so drift is *detectable* (a hit that
  goes stale is a logged drift event).
- Adaptive tier reordering / per-site learning: **BACKLOG** — state persistence
  and cold-start questions weaken the generalization story; static tiers +
  relocation is already substantive.

### Quantified test

The committed mutation suite (`docs/evals/evaluation-methodology.md`) breaks one
locator tier at a time: `ids-renamed` kills stable attrs, `button-text-renamed`
kills text matching, `wrapper-nesting` kills structural assumptions. A pass
means the agent recovered the *same semantic result* as the unmutated base —
controlled, reproducible evidence of "detect UI/selector change and adjust
dynamically" (T4), independent of real sites deciding to change.

### How an evaluator tells recovery was meaningful

1. The mutation case fails when relocation is disabled (each L4 case is watched
   red first — repo rule 2).
2. The trace shows: cached/first-choice locator failed → fresh candidates
   generated → different tier chosen → postcondition verified.
3. The recovery metric excludes retries by construction.
