# Scope checkpoint — after the M2 baseline, before M3

Committed before any M3 code. Purpose: make the M3 mechanism choice follow the
*observed* failure distribution instead of the interesting-sounding one. The
plan (`docs/plans/active/task1-b-level-plan.md`) names skipping this note under
time pressure as its own risk — it is the evidence that investment followed
measurement.

Baseline: `evals/report/20260816-002725-fast.json`, 41 cases, 41/41.
Thresholds: `specs/decisions/ADR-002-performance-thresholds.md`.

## Observed failure distribution

Every row is a failure that actually happened — in a live run, in a cold
review, or during M2 development — not a class we imagined. Twelve distinct
failures across M1 and M2:

| # | Class | What happened | Where it surfaced | Case |
|---|-------|---------------|-------------------|------|
| 1 | `locate` | substring name matching resolved an absent "History" heading to a superstring sibling and extracted it as a success | cold review, M1 | `resolver-substring-name` |
| 2 | `locate` | planner guessed role `region` for an element that was actually `status` | live run dee8ad5d | `observe-hello-elements` |
| 3 | `locate` | observation advertised a name on ARIA name-prohibited roles the resolver can never match | M2 fixture design | `observe-name-prohibited-roles` |
| 4 | `locate` | text-tier locator dead after the visible label changed; accessible name still fine | M2 mutation suite | `l4-shop-button-text-renamed` |
| 5 | `act` | planner invented postcondition text it had no way to know, so a correct action read as failed | live run 2e70785a | `observe-hello-elements` |
| 6 | `act` | postcondition unreachable because the fixture's own script broke under `ids-renamed` | M2 mutation suite | `mutation-catalog-integrity` |
| 7 | `env` | model wrapped the plan in a markdown fence; `json.loads` threw | live run 5a52f0aa | `planner-fenced-json` |
| 8 | (silent) | every `extract` overwrote `answer`, so multi-item tasks succeeded with one item | cold review, M1 | `multi-extract-list` |
| 9 | `act` | an unverified step was recorded `postcondition_ok: true`, because "nothing to check" and "checked and fine" were the same value | cold review, M2 | `postcondition-unverified-click` |
| 10 | `act` | a compound `expected_state` was graded on its first key only; the rest were silently dropped | cold review, M2 | `postcondition-compound-keys` |
| 11 | (silent) | the grader compared numbers at 6 significant digits, so $12,345.67 and $12,345.74 were "equal" | cold review, M2 | `verifier-numeric-precision` |
| 12 | (silent) | an identity anchor on an aggregate page is satisfied by every candidate answer, including the wrong one | cold review, M2 | `trap-search-not-executed` |

**Distribution: `locate` 4/12, `act` 4/12, silent-semantic 3/12, `env` 1/12.**

Three readings matter more than the counts:

- `locate` and `act` tie at the top, and within each class every instance is a
  *different* cause — for `locate`: wrong matching semantics, a guessed role,
  an unaddressable role, a dead tier. These are the two classes where a ladder
  has somewhere to climb.
- Failures 6, 7, 8, 9, 10 and 11 were **not** recovery problems. They were
  fixed by correcting a parser, a fixture, an accumulator, a truth value, a
  control-flow chain and a number format. A recovery ladder for any of them
  would have been machinery wrapped around a bug. This is the main thing the
  checkpoint is protecting against.
- Half of the M2 entries came from the close-out cold review, not from running
  the system. Cases 9–12 were all *green-looking* paths: the suite was 36/36
  while three of them were live. That is the argument for keeping the review
  step, and the reason trap-catch is reported as a floor rather than as an
  accuracy figure.

## Chosen mechanisms for M3 (2 families, genuinely distinct)

**Family 1 — `locate` → relocation.** Stale/failed locator → re-observe a fresh
a11y snapshot → regenerate candidates → resolve at a *different* semantic tier →
act → verify postcondition. Rungs are different strategies, not the same
strategy with new parameters. Chosen because it is the most frequent class
(4/8), because the mutation suite gives it controlled ground truth, and because
it is the assignment's named self-maintenance evidence. Red case waiting for
it: `l4-shop-button-text-renamed` (expects `failure:locate` today).

**Family 2 — `act` → postcondition invalidation → replan.** Action executed,
expected state not reached → feed the observation back to the planner and
extend/revise the plan prefix. Distinct from Family 1 in diagnosis (state, not
element), in action (new plan, not new locator) and in evidence (`retry_or_recovery`
= recovery with a new plan version). This is also the mechanism that makes the
"evolving plan prefix" claim in `docs/architecture/task1-overview.md` real
rather than aspirational — without it the architecture doc describes something
the code does not do. M2 already raised the stakes here: a click with no
checkable postcondition is now `failure:semantic`, so live runs will produce
more `act`-shaped stops, and this ladder is what turns them into outcomes.

A third family is **not** being added. Nothing in the observed distribution
justifies one, and the plan's own rule is never a third family just to fill a
quota.

## Explicitly NOT implementing (and why)

| Not doing | Why |
|---|---|
| `env` recovery ladder (retry the LLM, model fallback) | the one observed `env` failure was an output-format bug, fixed by a tolerant parser. A retry ladder here would be retry-in-disguise. |
| `nav` retry/backoff ladder | zero observed occurrences. Detect + classify + loud stop stays. |
| `extract` ladder (alternative extraction strategies) | the single observed extract issue was an accumulator bug. Empty extraction is already a loud classified failure. |
| `semantic` recovery | recovering from a wrong-but-coherent outcome needs verifier layer 3, which is SHOULD, and would let a weak signal drive execution. Detect and report, do not act. |
| Overlay/modal dismissal rung | no fixture or live run has produced one. Would be building for an imagined failure. |
| Adaptive tier reordering / per-site locator learning | already BACKLOG in the taxonomy; cold-start and persistence questions weaken the generalization story more than the mechanism adds. |
| Silent-failure *recovery* | the design position is detection, not repair. Traps measure the floor; the analysis states it. |

## What M3 must show to count

1. Each L4 case watched red without relocation, green with — the flip visible
   in the committed report history, not asserted in prose.
2. Recovery metric counts only `retry_or_recovery == "recovery"` traces:
   classify → strategy switch → verified success. Re-observe, scroll and wait
   rungs log as `retry` and are excluded by construction.
3. `mutation-recovery` reaches 3/3 by *relocating*, not by never having
   depended on the broken tier — today that honest number is 0/3 (ADR-002).
