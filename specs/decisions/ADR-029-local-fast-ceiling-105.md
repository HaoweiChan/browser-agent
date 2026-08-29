# ADR-029: the local `fast` ceiling moves 90 → 105, because the cases M42 adds moved the tree and the rule says so

Date: 2026-08-26
Status: accepted

**Ruling**: `WALL_BUDGET_S["fast"]` moves from 90s to **105s** for the LOCAL environment only, taken from ADR-013 Decision 3's rule applied to this tree's own committed ledger rather than chosen; ~~CI's `EVAL_WALL_BUDGET_S_FAST` **stays at 90** because nothing in this change measured CI~~ — struck 2026-08-26 (PR #57 R24): CI has since measured this tree and §2 records both ceilings it derives, which the workflow declares. ADR-019 §5 is where CI's numbers are published and `ci-numbers-are-derived` grades them against the workflow, so no ceiling is repeated in this line; ~~`invariant` is untouched at 20s, which its own ledger rows still derive.~~ — struck 2026-08-28 (ADR-036, T-M42-4): true of THIS change, which measured nothing in that suite, and superseded by the next one that did — `invariant` was re-derived by the same rule at a larger count and republished in ADR-019 §3, which is where the ceiling, the count and the band live. Neither the seconds nor the count is retyped here, and that is the fix rather than an omission: PR #66 R15 found an earlier repair updating the count on this line and leaving the seconds behind, so this line published a ceiling the branch had already moved past. This ADR's own ceiling is unaffected.
**Because**: M42's additions grew `fast`, which is growth in CASE COUNT and not in per-case cost — the exact condition ADR-021 named when it said "if a future gap comes from per-case cost the answer is removing waste (T-M32-3), not another raise"; the tree measured 73.06s at 181 cases and the new cases cost ~7s of real browser work between them, so the band crosses a ceiling step and ADR-013's rule derives 105 from it.
**Enforced by**: `published-band-matches-the-ledger` (items 3, 4 and 5 are what force this file to exist rather than letting the band be re-typed), `fast-wall-clock-budget` (whose boundary rows move to 105.00/105.01 in the same change, watched red first), `evals/run.py`'s `over_budget()`.

**Amended by**: ADR-035 Decision 7 (this file's Decision 2 ruling, local `fast` 105 -> **110** [local], on the same instrument and for the same reason — case-COUNT growth, the ledger's slowest run at M43's new count re-derived through ADR-013's rule; the figure is published in ADR-019 §2/Ruling and README's band table and is deliberately not retyped here). Added by PR #70 R14, and the omission is the defect this file's own `Amends` line describes one paragraph down: a reader following the chain from here reached 105 as though it were current, which is exactly what PR #57 R25 found ADR-021 doing to ADR-029.

**Amends**: ADR-019 Decision 2 (local `fast` 90 -> 105 [local]) and ADR-019 §5 (both CI ceilings re-derived from a measurement of the tree that ships) · **overturns ADR-021's CI ruling** ("the ceiling stays at 90, and that is a ruling"), which is struck in place there — for one round that ADR carried no `Amended by` line and a reader following the chain reached a ruling the workflow no longer obeyed (PR #57 R25)

---

## Context

ADR-019 gives each (suite, environment) its own ceiling, derived by ADR-013's
rule — slowest observed +15%, rounded up to a multiple of five — from a band
computed out of `evals/report/history.jsonl`. ADR-021 last moved the local
`fast` number, 80 → 90, on a band at 146 cases.

At 181 cases the tree measured 73.06s, which derives 85 and sat one step under
the committed 90. M42 adds cases — from the milestone itself and from each
review round after it — and every one of them that drives a browser costs real
wall clock. How many is deliberately not written here: three documents published
three different values for that one quantity, and `git diff main --stat` answers
it without any of them (PR #57 R16). The band moves past the step boundary, and `published-band-
matches-the-ledger` items 3 and 4 refuse a band whose derived ceiling is above
the committed one. That refusal is the mechanism working: a suite that got
slower has to say so, in the document of record, before the gate goes green
again.

## Decision

### 1. Local `fast`: 105s, derived and not chosen

The number is `_band_rule(max)` over the local rows at the current case count,
which is the same function `published-band-matches-the-ledger` uses to grade it.
Nothing here is hand-arithmetic, and nothing here restates it. **ADR-019 §2's
band bullet is the one place this repo publishes the band figure and the arrow
it derives**, because it is the one place `published-band-matches-the-ledger`
grades — its item 2 (cited-run) against the ledger row, its item 5 (derivation)
against the rule. Read the number there. What this ADR commits is the ceiling
that arrow lands on, 105s [historical]. `WALL_BUDGET_S` has been raised
three times since (ADR-035, ADR-037, ADR-039), so this sentence's original
present tense — "which `WALL_BUDGET_S` holds" — was false from the next
raise onward and stayed green for four milestones. The live value is not
retyped here: ADR-019 §2's band bullet publishes it and
`published-band-matches-the-ledger` grades it (T-R35).

Two steps, not one, and the second step is machine variance rather than case
count: the rows at this count differ from one another, while the band this
replaces was measured in a quieter session on the same laptop. No magnitude for
that difference is given, no endpoint is named, and no wall clock is retyped.
The ledger gains a row on every gate run — including the verification runs of
the review loop that read this sentence — so any prose describing its maximum,
its spread or its endpoints is falsified by the act of checking it. Five rounds
of findings in this class (PR #57 R5, R14-R16, R19-R23) all reduce to that one
sentence. `adr029-variance-cites-the-ledger` is what keeps this section from
acquiring such a literal again. That difference is the property ADR-013's rule is built around — SLOWEST observed,
not median — and exactly what T-M39-13 warns makes a band fragile. Publishing
the median would be choosing rather than deriving, and would leave the next
honest gate run red.

~~The same tree measured 84.83s and 88.87s within the hour~~ — struck 2026-08-26
(PR #57 R3). Those were real runs of this tree taken while three eval processes
contended for the machine, and they were discarded with the probe rows they
belonged to under the T-M38-5 practice, so no reader can read them back. A
document of record may not argue from evidence that no longer exists, which is
the class ADR-019 §6 exists to close and T-M39-14 names; the sentence above now
argues from rows the ledger actually holds.
`adr029-variance-cites-the-ledger` reads every seconds literal in this section
back against the committed local `fast` rows, so this cannot recur silently.
The rows were NOT committed after the fact to fit the sentence — that is the
other way to close a finding like this, and it is the dishonest one.

### 2. CI has measured this tree, and both its ceilings WERE derived from that [historical]

ADR-019 §5's CI numbers are hand-read off the log of a named workflow run,
because no CI run appends to this repo's ledger (§7, T-R51, T-R73).

**The measurement exists and it is four attempts, not one.** eval-gate run
[32937020758](https://github.com/HaoweiChan/browser-agent/actions/runs/32937020758)
on commit `14a6a7b` ran that tree on CI four times. Every attempt was
correctness-green — ~~`fast` 220/220, `invariant` 76/76~~ — in the environment
that guards `main`, and every attempt was over the 90s `fast` ceiling then
declared. **Those two figures are struck, and struck is not deleted**: they are
the record of what that run measured, on the 220-case tree commit `14a6a7b`
carried, and they are true of it forever. They are struck because
`adr029-scope-matches-the-suites` reads every `` `suite` N/M `` in this section
back against THIS tree's suites, which is right for the local pair below and
wrong for a CI figure hand-read off a named workflow run of a different commit
(ADR-019 §5, §7) — restated live, a true measurement of a 220-case tree becomes
a fabricated claim about a 227-case one, one case addition at a time. The live
claim is the sentence after this one; the digits stay readable above it. The one
publisher for CI figures is ADR-019 §5 (T-M42-20-D2).
The wall clocks are not reprinted here. CI wall clocks live at three graded
sites, which is §5's own list and not a single publisher: **ADR-019 §5's table is
the SOURCE**, and `ci-numbers-are-derived` reads it back against two copies —
README's values and `.github/workflows/eval.yml`'s comment block — so all three
are graded and drift between any two is red (the rule PR #57 R20-R23 arrived at
is that there is one source, not that there is one site). §5 carries the table,
the arithmetic and the `gh run view` command that reprints it.

~~and nowhere else~~ — struck 2026-08-28. That clause was true when written and
is not now: ADR-019's 2026-08-28 amendment argues its ruling from CI wall clocks
quoted in prose, and prose is a fourth site. The rule is therefore stated with
the distinction it always relied on and never wrote down — **the three sites
above are GRADED against §5's table; the amendment is a fourth, deliberately
UNGRADED narrative one** — because "nowhere else" is a claim no check enforces,
and a rule nothing enforces is exactly what this repo keeps discovering it has
restated instead of built. That amendment carries its own disclosure of what that
costs.

~~**Both CI ceilings now come from that table**, by ADR-013 Decision 3's rule
applied to its maxima, and `.github/workflows/eval.yml` declares exactly what
they derive. `invariant`'s moves too, although CI never breached it: its tree
grew from 48 cases to 74, and deriving one suite from the new table while
leaving the other on the old one would publish two trees inside one table —
the class this PR spent five rounds closing.~~ — struck 2026-08-28. Both halves
are superseded and the second is now false: `invariant` HAS breached on CI, and
`fast` is the suite that never has. ADR-019's 2026-08-28 amendment re-derives
both ceilings from a cross-commit sample of runs, so this run's table is no
longer the source. The one-publisher rule is unchanged — ADR-019 §5 carries the
live table, the arithmetic and the ids, and this section keeps only the record of
what run 32937020758 measured.

**This supersedes the two positions this section held before it.** It first said
CI's ceiling was UNMEASURED and scoped every gate claim as local-only; that was
true when written and stopped being true the moment CI ran. It then said the
branch shipped a **red CI wall clock deliberately**, which was the honest
description of a tree whose ceiling was waiting on samples — and is now wrong in
the other direction: the samples arrived, the ceiling is derived, and the breach
is closed by a number the rule produced rather than tolerated by a note in an
ADR. Neither earlier framing survives, and saying so is the point of the
paragraph: a disclosure that quietly drops its own previous claim is not a
disclosure.

**Where that leaves the evidence**: correctness is green in both environments —
locally `invariant` 116/116 and `fast` 274/274, and on CI green across four
attempts of the tree that run measured, whose own totals are struck above and
published live only in ADR-019 §5 — and the wall-clock gate is now derived, not
breached, in both.
The local pair is read back against the suites by
`adr029-scope-matches-the-suites`, because this paragraph once published a
four-case-stale pair (PR #57 R14) and a disclosure wrong about its own evidence
is not a disclosure. The confirmation this branch cannot give itself is the CI
run of the commit that carries these ceilings; that run is the check on the
number, and it is read after the push rather than asserted here.

### 3. What was NOT done, and why the offer was refused

Trimming cases to stay under the old ceiling was available and is the wrong
trade. The three most expensive additions are the three that carry the most:
`action-wait-for-that-never-holds-is-loud` burns the full settle budget *because
that is the postcondition it grades*, and the two `wait_for` successes pay a
fixture's paint delay because the postmortem's S1/S4 shape is a page that paints
late. A ceiling that can only be met by deleting the cases that measure the
milestone is not a ceiling, it is a cap on evidence.

The other refused option was the quiet one: publishing a band the ledger does
not support, or keeping probe rows out of the committed ledger until a fast
enough run happened to appear. T-M39-13 already documents that treadmill; this
ADR pays the cost openly instead.

## Consequences

- The local gate has headroom again at this tree's size, where it had ~5% before
  this change and would have had none after it.
- A wider ceiling catches drift later. That is the real cost of every raise, and
  ADR-021 named it first: the answer to per-case cost growth is removing waste,
  not another raise. This raise is case-count growth, and the next one should
  have to prove the same thing.
- `fast-wall-clock-budget`'s boundary rows move with the number, so the case
  keeps testing the boundary rather than a number it used to be.
- Local and CI publish per-environment `fast` ceilings, independent by ADR-019
  §4's rule and read through one override variable per suite. ~~(105 vs 90) ...
  the first time local has been the LOOSER of the two, which is a reason to
  re-derive CI's promptly rather than to leave it~~ — struck [historical]
  (PR #57 R33): §2 of this same document re-derived CI's from a measurement of
  the tree that ships, so the sentence argued for something the document beside
  it had already done. Both live figures are published where they are graded —
  local in ADR-019 §2, CI in §5 — and neither is repeated here.
