# ADR-002: Performance thresholds set from the M2 baseline

Date: 2026-08-16
Status: accepted; all six decisions stand as written. **Decision 4 (fast wall clock ≤ 60s) was knowingly breached from M8 to M12** — the gate measured 66.6-68.3s — and the breach is **closed at M12 without moving the ceiling**: `specs/decisions/ADR-011-fast-suite-wall-clock.md` measured 11.3s of the 67.0s as per-case browser process lifecycle, removed it, and left the deliberate 42.2s of timeouts untouched. The suite now measures 56.47s over 95 cases. **Decision 4 is also amended in scope**: the ceiling is per-environment since ADR-011 Decision 3 — 60s locally, 75s on CI via `EVAL_WALL_BUDGET_S`, both measured and both enforced — because CI had been running `fast` in 89.62s against this same 60s for its entire existence with nothing checking. Enforced by `evals/run.py` and graded by `fast-wall-clock-budget` rather than asserted in this file.

**Amended by**: ADR-009 (Decision 4's 60s wall-clock ceiling, declared breached rather than reset); ADR-011 (that breach closed, enforcement added, and the ceiling made per-environment — 60s local, 75s CI — in its Decision 3)

**Ruling**: Sets the pre-commit gate: `fast` suite ≥ the committed baseline (1.000), `invariant` suite = 100% unconditional, trap-catch ≥ 90% as a floor never a verifier-accuracy claim, `fast` suite cost = $0.00 exactly, and `fast` suite wall clock ≤ 60s locally / ≤ the environment's own measured ceiling elsewhere (breached M8-M12, restored, then made per-environment — see Amended by).
**Because**: Naming performance targets before a baseline exists invites goalpost-moving in a history reviewers read.
**Enforced by**: `.eval-baseline.json` + `.githooks/pre-commit` (fast-suite gate); `invariant` suite = 100% enforced unconditionally in `evals/run.py`; wall clock by `fast-wall-clock-budget` (ADR-011).

---

## Context

`docs/evals/evaluation-methodology.md` fixes two thresholds a priori, because
they are integrity properties rather than performance claims: invariant suite
100%, trap-catch ≥ 90%. Everything else — E2E success, recovery, mutation
recovery, latency, cost — was deliberately left unnamed until a baseline
existed. Naming performance targets before measuring anything invites
goalpost-moving in a history reviewers read.

The M2 baseline now exists: 41 cases, `fast` suite, committed at
`evals/report/20260816-002725-fast.json`. It is the *post-cold-review*
baseline: the first run (36 cases, `…-001708-fast.json`, also committed) was
taken before the close-out cold review, which found three ways a wrong answer
could still be graded PASS. Both reports are kept — the pair is the record that
the number did not move while the population it describes got harder.

## Observed baseline

| Signal | Observed | How |
|--------|----------|-----|
| `fast` suite score | 41/41 = 1.000 | offline, LLM stubbed at the planner boundary |
| `invariant` suite | 5/5 = 1.000 | INV-0, INV-1, INV-2, URL guard, grader numeric precision |
| Trap-catch | 6/6 = 100% | the 6 `trap-*` cases; all reach a FAIL verdict |
| Latency p50 / p95 | 0.32s / 0.59s per case | across all 41 cases, 11 of which are pure-code and land at ~0s; browser cases run 0.29–0.62s with a cold Chromium launch each, against loopback fixtures. Not comparable to live-site latency. |
| Wall clock, whole suite | ~13s | pre-commit gate stays cheap |
| Cost, `fast` suite | $0.0000, 0 tokens | the offline guarantee, measured rather than asserted |
| Cost, live planner | ~$0.0029 per task | M1 run 09b21b3a, `anthropic/claude-sonnet-4.5` via OpenRouter |
| Actions per task | 79 actions / 30 browser cases ≈ 2.6 | well under the 30-action budget |

Coverage at baseline: TC1 9 · TC2 4 · TC3 5 · TC4 7 · TC5 5 · 11 mechanism
cases. Levels: L1 12 · L2 10 · L4 3 · L5 5. ZH sample in 7 cases (≥1 per TC).
Domains: 2 (shop fixture, forms fixture) — the ≥1 live domain required at
B-floor is still missing and lands with the `full` suite.

## Decision

Thresholds, effective now and gated by the pre-commit hook via the baseline
file:

1. **`fast` suite ≥ 1.000.** The baseline is the gate; it moves only via
   `--update-baseline` plus an ADR. Set at the observed value because every
   case in it is either deterministic or fixture-served — a flake here is a
   bug, not variance.
2. **`invariant` suite = 100%**, unconditional (already enforced in code,
   independent of baseline).
3. **Trap-catch ≥ 90%**, reported as a *floor* on silent-failure detection,
   never as verifier accuracy. Observed 100% on 6 traps; 6 traps is a small
   sample of imaginable wrongness and is stated as such. The cold review makes
   the point sharper than any prose could: it produced three wrong-answer
   inputs the trap set did not contain.
4. **`fast` suite wall clock ≤ 60s.** At ~13s there is room for M3–M4 cases;
   past 60s the pre-commit gate stops being run honestly. (Breached M8-M12 at
   66.6-68.3s and declared rather than reset; closed at M12 at 56.47s and now
   applied by `evals/run.py` to the run it measured. **Per-environment since
   ADR-011 Decision 3**: 60s is the local number and stays the tight one; CI
   carries its own measured 75s, from four runs of one commit at 59.77 / 60.84 /
   64.61 / 64.67s — an 8% spread on identical code, which is why one number could
   not be both tight here and true there.)
5. **`fast` suite cost = $0.00 exactly.** Not a budget — a boundary. Any
   non-zero figure means an LLM call escaped the stub and is a defect.
6. **Live cost ≤ $0.01 per task** at the current model, alarm rather than a
   hard cap; the OpenRouter key spend limit is the actual ceiling.

## Deliberately not set yet

- **Recovery rate** — there is no recovery mechanism to measure. A number now
  would be a guess dressed as a target, which is the exact failure this ADR
  exists to prevent. Set in ADR-003 after M3, from the injected-failure cases.
- **Mutation-recovery rate** — the B-floor exit criterion already fixes the
  bar at 3/3 tier-breaking mutations. Today 2 of 3 pass (`ids-renamed`,
  `wrapper-nesting`) and they pass *without recovering anything*: plans carry
  no stable-attr or structural dependency, so nothing broke. The honest count
  of mutations the agent currently survives **by relocating** is 0/3, and
  `l4-shop-button-text-renamed` is committed red-in-spirit — it expects
  `failure:locate` — precisely so that M3 has to flip it.
- **E2E success on live domains** — no live case exists yet; a threshold from
  fixture-only data would not transfer. Set from the first `full` run.

## Consequences

Buys: gates that cite observations, and a written record of which numbers are
measured versus committed-to. Costs: three thresholds remain open until M3/M5,
so the reviewer-facing analysis must show the empty cells rather than a full
table. That is the intended trade — `docs/evals/evaluation-methodology.md`
already requires empty cells to be visible.

**Addendum, same day.** `contract-trace-schema` landed immediately after this
ADR was written — a conformance case that found `anchor` specced into
TraceStep and never emitted. Current figures are 42/42 fast, 6/6 invariant.
The observed table above is left at the numbers of the report it names: an ADR
records a decision at a point in time, and the normative part of this one is
the thresholds, not the case count.

The `fast` suite baseline moving from 1.000 (9 cases) to 1.000 (41 cases) is
recorded here as a deliberate baseline event: the score is unchanged, the
population behind it is four and a half times larger, and five of the new cases
are ones the code failed when they were written.
