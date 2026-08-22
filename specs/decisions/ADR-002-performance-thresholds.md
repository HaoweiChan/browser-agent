# ADR-002: Performance thresholds set from the M2 baseline

Date: 2026-08-16
Status: accepted; all six decisions stand as written. **Decision 4 (fast wall clock ≤ 60s) was knowingly breached from M8 to M12** — the gate measured 66.6-68.3s — and the breach is **closed at M12 without moving the ceiling**: `specs/decisions/ADR-013-fast-suite-wall-clock.md` measured 11.3s of the 67.0s as per-case browser process lifecycle, removed it, and left the deliberate 42.2s of timeouts untouched. **Decision 4 is also amended in scope**: the ceiling is per-environment since ADR-013 Decision 3 — **60s locally, 80s on CI** via `EVAL_WALL_BUDGET_S`, both measured and both enforced — because CI had been running `fast` in 89.62s against this same 60s for its entire existence with nothing checking. ADR-013 Decision 4 tried re-measuring the local number to 70s on the M9-stage-2 merge, then withdrew that the same day on round-5 review when the band behind it did not reproduce; the local number ships unchanged at 60s. Enforced by `evals/run.py` and graded by `fast-wall-clock-budget` rather than asserted in this file.

**Amended by**: ADR-009 (Decision 4's 60s wall-clock ceiling, declared breached rather than reset); ADR-013 (that breach closed, enforcement added, the ceiling made per-environment in its Decision 3; its Decision 4 tried and withdrew a 60s -> 70s local re-measurement the same day); **ADR-017** (the local number re-derived 60 -> 80 after M31 grew the suite, a second suite — `invariant` — given a ceiling of its own at 20s, CI's `fast` number re-measured on CI to 90s, and every band computed from the committed ledger rather than by hand)

**Ruling**: Sets the pre-commit gate: `fast` suite ≥ the committed baseline (1.000), `invariant` suite = 100% unconditional, trap-catch ≥ 90% as a floor never a verifier-accuracy claim, `fast` suite cost = $0.00 exactly, and each suite's wall clock ≤ its own environment's measured ceiling — **`fast` 80s local / 90s CI, `invariant` 20s local / 20s CI, since ADR-017** (breached M8-M12, restored, made per-environment, a local re-measurement to 70s tried and withdrawn at M12, then re-measured to 75s at M31 when the suite grew — see Amended by; `invariant` has had its own 15s ceiling since ADR-017).
**Because**: Naming performance targets before a baseline exists invites goalpost-moving in a history reviewers read.
**Enforced by**: `.eval-baseline.json` + `.githooks/pre-commit` (fast-suite gate); `invariant` suite = 100% enforced unconditionally in `evals/run.py`; wall clock by `fast-wall-clock-budget` (ADR-013).

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
4. **`fast` suite wall clock ≤ the environment's measured ceiling** —
   **60s locally**, 80s on CI. At ~13s there is room for M3–M4 cases; past the
   ceiling the pre-commit gate stops being run honestly, which is what the number
   is for. (Breached M8-M12 at 66.6-68.3s and declared rather than reset; closed
   at M12 and applied by `evals/run.py` to the run it measured;
   per-environment since ADR-013 Decision 3. The local number was **tried at
   70s in ADR-013 Decision 4** when the M9-stage-2 merge put the suite at
   59.4-60.2s across seven runs — straddling the old line, with the excess
   measured to be evidence rather than waste — but the seven-run band that
   justified going to 70s did not reproduce under round-5 review (~22 runs
   across three independent measurers, idle and deliberately CPU-loaded
   alike, landed at 58.96-59.87s), so the amendment was withdrawn the same
   day and the local number ships at **60s** — not with a clean margin,
   though: post-commit verification found the reproducible band is really
   58.83-60.26s, one further run over the line by a few tenths against 42
   that were not, an unexplained low-single-digit-percent tail CPU load did
   not account for (ADR-013 Decision 4, in full). CI's ceiling comes from the same
   stated rule — the slowest observed run plus 15%, rounded up to a multiple
   of five — unaffected by this correction.)
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
