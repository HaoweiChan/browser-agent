# ADR-003: Recovery mechanisms and the thresholds M3 can honestly set

Date: 2026-08-16
Status: accepted

## Context

ADR-002 left three thresholds deliberately unset, one of them because "there is
no recovery mechanism to measure. A number now would be a guess dressed as a
target." M3 built the mechanisms the scope checkpoint selected
(`docs/evals/scope-checkpoint.md`: two families, chosen from twelve observed
failures, third refused). This ADR records what was built, what it measures,
and which cells are still empty.

## Decision 1 — two ladders, dispatched by a deterministic classifier

`classify(action, exception) -> one of 7 classes` (`src/browser/agent.py`) is
rules only, no LLM. It decides which ladder fires, so it is the component
diagnosis accuracy actually grades; its truth table is
`evals/adversarial/diagnosis-classifier-classes.json`. The same Playwright
timeout is `nav` on a navigate and `act` on a click — the action carries as
much of the decision as the exception does.

**Family 1, `locate` -> relocation.** Fresh a11y snapshot, then the same
semantic intent expressed at a *different* tier. Rungs come from the snapshot,
never from stored site knowledge (CLAUDE.md rule 6). The rule that makes it
recovery rather than retry is enforced in code: a tier the failed target
already used is excluded even when the fresh observation would happily supply a
candidate for it (`relocation-distinct-tier`, row 4). Both directions are
exercised, because both occur: text -> role+name
(`l4-shop-button-text-renamed`) and role+name -> text
(`l4-recover-name-to-text`).

**Family 2, `act` -> replan.** The action landed, the expected state did not
arrive. Re-observe, hand the planner the failure and the page as it now is, and
replace the failed step *and everything after it* while keeping the executed
prefix. This is the "evolving plan prefix" from
`docs/architecture/task1-overview.md` becoming code rather than a description.
The injected case (`recovery-replan-postcondition`) is shaped like the live
failure that motivated it (run 2e70785a: a postcondition the planner had no way
to know). Note what the recovery does *not* do: the click had really sorted the
list, so the replan re-plans the remaining extraction instead of redoing the
action — replanning from observation, not from the original plan.

A replan that returns the steps it was asked to replace is refused as
no-progress before it costs a budget unit. Without that, an identical-plan
replanner loops until an unrelated budget trips and reports the wrong cause.

## Decision 2 — budgets, and which class exhaustion carries

| Budget | Cap | On exhaustion |
|--------|-----|---------------|
| actions per run | 30 | `failure:env` — a resource stop |
| LLM tokens per run | 100k | `failure:env` — a resource stop |
| relocation rungs per step | 2 | the class the ladder was fixing (`locate`) |
| replans per task | 2 | the class the ladder was fixing (`act`) |

The split is the point. Running out of actions is an environment fact; running
out of ladder rungs means the run died of the failure it could not fix, and
reporting that as `env` would corrupt the failure distribution the next scope
checkpoint reads. INV-3 (specs/000) fixes the loudness half: every one of these
ends with a class and the complete trace.

## Decision 3 — thresholds, and the ones still not set

Measured on the M3 `fast` baseline, 49 cases:

| Signal | Observed | Threshold set |
|--------|----------|---------------|
| `fast` suite | 49/49 = 1.000 | ≥ 1.000 (unchanged from ADR-002) |
| `invariant` suite | 10/10 | 100%, unconditional |
| Recovery (cases asserting recovery, verified) | 3/3, 6 rungs tried | ≥ 3/3 — a floor on the *injected* classes, not a rate |
| Mutation-recovery | 4/4 mutation cases pass, **2 by relocating** | 3/3 mutation types pass; ≥1 type recovered by relocating |
| Diagnosis accuracy | 5/5 injected classes | 100% on injected cases |
| Wall clock, `fast` | 23.3s | ≤ 60s (unchanged) |
| Cost, `fast` | $0.0000 | exactly $0.00 (unchanged) |

Three readings that matter more than the numbers:

1. **"2 by relocating", not 4.** ADR-002 recorded the honest count of mutations
   survived *by relocating* as 0/3 and predicted the flattering version of this
   metric. `ids-renamed` and `wrapper-nesting` still pass without recovering
   anything, because no plan was standing on the tiers they break. Exactly one
   of the three B-floor mutation *types* (`button-text-renamed`) breaks a tier
   a plan depends on, and both of its cases now recover. The eval adapter counts
   relocation separately from passing so this cannot be quietly rounded up.
2. **Recovery 3/3 is a floor on a denominator of three.** The denominator is
   cases that assert recovery, not all failures, so a ladder correctly failing
   to save a doomed run (`resolver-substring-name` — the asked-for element is
   genuinely absent) is scored as neither a win nor a miss. Six rungs were tried
   across the suite to produce three verified recoveries; that ratio is printed
   beside the metric rather than folded into it.
3. **Diagnosis 5/5 measures injected classes only.** Five of the seven classes
   are reachable by injection today; `env` and `nav` are covered by the pure
   truth table but have no end-to-end injected case, because no fixture produces
   a network failure or a bot-challenge page. Stated, not padded.

Still not set, and why:
- **E2E success on live domains** — no live case exists yet; unchanged from
  ADR-002 and now the largest open cell. Set from the first `full` run.
- **Recovery rate as a rate** — three injected cases is not a population. It
  stays a floor with its denominator visible until the live suite gives it one.

## Consequences

Buys: two mechanisms with distinct diagnoses, distinct actions and distinct
evidence; a metric that separates "passed" from "recovered"; budgets that end a
run with the class it died of. Costs: the `fast` suite went from ~13s to ~23s,
because three of the new cases spend two seconds each waiting for a
postcondition that will never arrive — that wait is the mechanism being tested,
so it is paid rather than mocked. Still well inside the 60s gate.

One accepted limitation, marked in code rather than hidden: a replan that
re-extracts a value an earlier step already extracted would append it twice and
turn a scalar answer into a list. No case produces it — the replan case's
failed step never reached its extraction — and building for it would be exactly
the imagined-failure engineering the scope checkpoint exists to refuse.
