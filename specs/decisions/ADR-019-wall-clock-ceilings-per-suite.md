# ADR-019: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: four ceilings, one per (suite, environment), each derived by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five) from a band computed from `evals/report/history.jsonl` and graded against it — local `fast` 60 → 80 → **90s** (ADR-021), local `invariant` **20s**, CI `fast` 80 → **90s**, CI `invariant` **20s** — read through one variable per suite (`EVAL_WALL_BUDGET_S_FAST`, `EVAL_WALL_BUDGET_S_INVARIANT`).
**Because**: M31 added real cost and the first repair moved three browser cases to `invariant`-only tags instead of facing it — which left the gate refusing a commit that changed nothing but JSON at 60.24s with every case passing — and the first version of this ADR then gave `invariant` a ceiling derived from local runs but enforced only on CI, where it had never been measured and immediately went red.
**Enforced by**: `fast-wall-clock-budget` (both ceilings, the set of suites that have one, and the override's scope), `published-band-matches-the-ledger` (the bands against the ledger), `published-band-slack-is-declared` (§6's bound), `evals/run.py` `over_budget()`

**Amended by**: ADR-021 (Decision 2's local `fast` ceiling 80 -> 90, on the number `published-band-matches-the-ledger` derived after the M32 merge grew the suite; the other three ceilings unchanged)

**Amends**: ADR-013 Decision 4 (local `fast` ceiling 60 → 75) and ADR-002 Decision 4 (a second suite now has a ceiling)

---

## Context

ADR-013 Decision 4 has been to 70 and back to 60 already, and the record of why
is long (`fast-wall-clock-budget`'s provenance, points 5-7). What is different
this time is that nothing about the measurement is in dispute: the suite grew.

M31 added five cases that drive a real browser, three of them settle-bound —
each spends the full 2s postcondition budget on a postcondition that
deliberately never arrives. The first repair round put those three in
`invariant` only, on the argument that `fast` was at its ceiling. That was the
wrong instrument, and the reviewer's evidence is the proof:

- the pre-commit gate refused **a commit that changed nothing but JSON under
  `tasks/reviews/`** — `[eval] OVER BUDGET: suite 'fast' wall clock 60.24s > 60s`
  with `[eval] suite 'fast': 109/109 = 1.000`;
- four runs of that same tree: 59.68 / 59.70 / 59.80 / 60.24s — a coin flip;
- the cost did not go away, it moved: `invariant` went 7.26s → 12.20s while the
  published `fast` number stayed at 59.7s;
- and `invariant` had no ceiling at all, so the tag was an unbounded relief
  valve. `fast-wall-clock-budget` itself pinned `{suite: invariant,
  wall_seconds: 999.0, over: false}`.

## Decision

### 1. The three cases go back into `fast`

They are regression guards for three silent-success defects (PR #29 R1, R2, R3)
and the local pre-commit hook runs `fast` alone. A guard the hook does not run
is worth less than the 4.9s it costs.

### 2. The local `fast` ceiling is 90s, computed from the ledger

Every LOCAL band here — this section's and §3's — is computed from
`evals/report/history.jsonl`, the ledger committed in this repo, and
`published-band-matches-the-ledger` grades that on every run — §6 lists exactly
what it requires, and this file states it nowhere else. It has to, because three bands in PR #29 did not
match the ledger beside them: nine of fifteen runs published as "every run the
ledger records", four values that appear in no recorded run, the two slowest
`invariant` runs dropped unlabelled, and a maximum (64.71s) the ceiling was
derived from that was never measured (PR #29 R18, R21). That is the same
selective presentation ADR-013 Decision 4 was withdrawn over, repeated in the
decision that amends it.

§5's CI numbers are not in that ledger and cannot be (no CI run commits their
wall clock); they are hand-read off the workflow log, ungraded, and logged as
debt (T-R51).

**The ledger's numbers, at the case count this branch ships:**

- Band source — `fast` at 152 cases, ts `20260823-200925`, **70.64s**
  (152/152, and `dirty: false` — a green run writes no per-case report under
  ADR-012's policy, so the ledger row is the whole artifact, which is why this
  sentence cites the ts and not a file. Both halves are deliberate. GREEN,
  because PR #34 R21's finding was that the enumeration this section used to
  carry published only the RED runs at the shipped case count. CLEAN, because a
  dirty citation is what made this band red on CI and green locally — see the
  CI paragraph at the end of §6. The ledger's own maximum here is 71.01s and
  derives the same ceiling.)

Every run of this tree is in `evals/report/history.jsonl`, committed beside
this file; the sentence above names the one the band is derived from by its
ledger timestamp, and §6 items 2-4 are what the check requires of it. The
ledger's own maximum at a given count may be higher than the band source,
because it includes red runs and runs taken mid-edit; §6 is why that is allowed
and by how much. The enumeration that used to stand here — and the one in §3 —
is gone: it was a snapshot of a file that grows on every gate run, nothing
graded it, and it had drifted to publishing six of the eight runs recorded at
the shipped case count, which is the R21 defect this ADR was amended over
(PR #35 R21; PR #34 R21 is the same defect found independently on the M32
branch, and gets the same resolution — see §3). What
is published here is now exactly what is graded (§6).

ADR-013 Decision 3's rule — slowest observed +15%, rounded up to a multiple of
five — gives 70.64 × 1.15 = 81.24 → **85**, which is BELOW the committed 90 and
does not move it: ADR-021 set 90 from a longer record at 146 cases (ledger
slowest 74.8s), and §6's no-ratchet-down rule is that a freshly republished
band is a short sample and therefore a lower bound on what the tree costs. One
run at 152 cases is exactly that short sample. Item 5 grades the arrow against
the RULE, not against the committed ceiling, which is why 85 under a §2 heading
that says 90 is green and declared rather than a contradiction. The band
published for the earlier
114-, 116- and 122-case trees is superseded rather than corrected in place: it was
derived by hand from a subset, and the point of the grader is that nobody has
to trust a hand-derived band again. The rule is unchanged; only the reading of
it was wrong.

Margin against the observed band is ~20s where before M31 it was ~0.2s. That is
a real loosening, and it is the point: a ceiling whose job is to catch drift
cannot also be the thing that fails on drift-free commits — this one refused a
commit that changed nothing but JSON.

### 3. `invariant` gets a ceiling: 20s

- Band source — `invariant` at 58 cases, ts `20260823-200456`, **13.78s**
  (58/58, `dirty: false`, ts-only for the same ADR-012 reason as §2. Four clean
  rows were available at this count — 12.93 / 13.78 / 13.18 / 13.12s, taken as
  they came, not selected for their numbers. 12.93s is disqualified: it derives
  **15** where the ledger's maximum derives 20, which is item 3. Of the three
  that qualify, this is the slowest, chosen so the published number sits as
  close to the ledger's own maximum of 13.80s as a real run allows — §6 tolerates
  up to one ceiling step of slack, and the point of R21 was that publishing
  below the maximum is how a band drifts, so take the least slack on offer.)

The same rule gives 13.78 × 1.15 = 15.85 → **20**, which is the committed
ceiling. Two decimals on the product because one is not enough to re-derive it:
"15.4" and "15.0" round up to a multiple of five differently depending on how a
reader reads them (PR #35 R13).

Both bands above are republished at the case count this branch ships after the
`origin/main` (PR #35) merge and this round's own case: `fast` 136 → 152,
`invariant` 53 → 58. Neither is the enumeration this file used to carry. PR #34 R21 found that enumeration publishing three runs
where the ledger held six and calling the smallest of them the maximum — the
same defect PR #35 had already fixed here by deleting the list and citing one
graded row instead, which is the resolution both findings get.

This number was **15** until PR #29 R21, and that was a reading error, not a
rule change: the band behind it published five runs of a ledger holding
sixteen, dropping the two slowest (13.06 and 13.57s) without labelling them.
13.57 × 1.15 = 15.6, so the rule had said 20 all along — and CI, which enforced
the locally-derived 15 having never measured it, went red at 15.06s and 15.22s
proving it. Two suites now have numbers, and
`fast-wall-clock-budget` grades the SET, so a third suite acquiring cost
without a ceiling turns it red.

The reason `invariant` needs one is not that it is slow. It is that without one,
"move the case to `invariant`" is a way to make the `fast` number go down while
the tree gets slower — which is exactly what happened, in this PR, one round ago.

### 4. One override variable per suite

The first version of this decision scoped the single `EVAL_WALL_BUDGET_S` to
`fast` — which stopped it raising `invariant`'s ceiling, and in the same stroke
made it impossible for `invariant` to have a per-environment number at all. CI
then enforced §3's locally-measured 15s having never run it, and went red at
15.06s and 15.22s with 46/46 passing. `.githooks/pre-commit` runs `fast` alone,
so nothing local could catch it (PR #29 R15).

`wall_budget(suite)` now reads `EVAL_WALL_BUDGET_S_{SUITE}`. Each suite has its
own variable, so raising one environment's `fast` ceiling cannot silently raise
its `invariant` ceiling — the relief-valve property §3 is about — and each suite
can be measured where it is enforced, which is what ADR-013 Decision 3 already
ruled `fast` needed. `fast-wall-clock-budget` pins both directions.

### 5. CI's two numbers, measured on CI: 90 and 20

Not projected from local runs, which is the mistake §3 made. Four attempts of
one commit (`d173340`, the tree this branch ships — 116 `fast`, 48 `invariant`):

| attempt | `invariant` | `fast` |
|---|---|---|
| 1 | 16.47s | 69.54s |
| 2 | 15.85s | 74.06s |
| 3 | 14.80s | 69.37s |
| 4 | 15.60s | 74.04s |

Same rule: 16.47 × 1.15 = 18.9 → **20**; 74.06 × 1.15 = 85.2 → **90**.

**CI's `fast` ceiling of 80 was the next coin flip, and this is the measurement
that says so** rather than the promise the first version of this ADR left in its
place. 74.06s against 80 is 8% of margin on a runner whose own spread across
these four attempts is 6.8% — the same ratio that produced the local 60.24s
refusal. The reviewer projected ~72s and the measurement came in at 74.06s
(PR #29 R19).

The runner is ~1.15x slower than this laptop on `fast` (74.06 vs 64.71) and
~1.27x on `invariant` (16.47 vs 12.96), which is why four numbers and not two.

### 6. (2026-08-23) The band's slack is a declared ceiling, not an oversight

PR #29 R24 asked why `published-band-matches-the-ledger` grades
`rule(published) == rule(ledger max)` rather than `published >= ledger max`.
The weak property is kept, and this section is the price of keeping it: the
hole is measured, named, and pinned by a case, so nobody has to discover it.

**What the check enforces.** One list, in one place; every other sentence in
this file and in README refers to it instead of restating it. Three rounds of
PR #35 ended the same way — the repair correct, its own description left behind
(R15, R16) — and a second copy of a rule is the thing that goes stale.
`published-band-matches-the-ledger` requires, per suite:

1. the published case count is the suite's current case count;
2. the band sentence cites a ledger row by timestamp, at that count, whose wall
   clock IS the published number — and if that row is dirty, that no clean row
   at that count existed by then. Judged as of the cited run, not as of now;
3. the published number derives the SAME ceiling as the ledger's maximum at that
   count — `rule(published) == rule(ledger max)`, not `published >= ledger max`;
4. the committed ceiling is at least `rule(ledger max)`, read from the ledger
   and never from the published number;
5. the derivation sentence multiplies the published number, is right to two
   decimals, and states the ceiling **the rule gives** — `_band_rule(x)` — which
   must not exceed the committed ceiling;
6. the Ruling's own local ceilings are the ones `evals/run.py` commits;
7. README's band row carries the same four values as this file, and neither
   document publishes two bands for one suite.

Green is required nowhere in that list and cannot be (T-R53). Item 5 states the
rule's value and deliberately does NOT require it to equal the committed
ceiling — the paragraph on what this does not cover, below, is why.

**What it lets through.** The published number may sit anywhere inside the band
that derives the committed ceiling — item 2 requires it to be a run that
happened, not the slowest one — so it can understate the ledger's maximum at
that count by up to one ceiling step — five seconds of ceiling divided by the rule's
1.15, a declared slack of one ceiling step (**4.35s**) of wall clock.
`published-band-slack-is-declared` derives that bound from the rule's own
constants rather than trusting this sentence, measures the headroom of each
band published above, and reports both — no per-suite number is written here,
because a number that moves with the band is the snapshot this section deletes
everywhere else.

**Why not the strict form.** Not for the reason the first version of this
section gave. It argued that the ledger line is appended after the run's cases
are graded — `evals/run.py` — so the run that sets a new maximum passes and the
NEXT commit reddens, on an author who changed nothing. That lag is real and it
is shared: no run sees its own wall clock under EITHER form, and this section's
own property reddens the next commit too when a run crosses the band. Naming it
as the disqualifier was wrong (PR #35 R3).

What differs is frequency. `published >= ledger max` forces a doc edit on every
new maximum, and on a tree that moves 0.2-0.5s between consecutive runs most of
the early runs at any new case count set one — each landing on whoever commits
next, for drift of tenths of a second. The property kept here forces an edit
when the band is crossed: once per one ceiling step (**4.35s**), which is a
real change in what the
tree costs and worth a human writing a number down. A regeneration script
changes who types the number, not how often the interruption arrives.

**What the slack cannot hide — and what it does not cover.** Item 4 is graded
against `rule(ledger max)` directly, from the ledger, never from the published
number, so a tree that crosses its band reddens the gate. R21's direction
(12.96s published where 13.57s was recorded: 15 where the rule said 20) is red
on that and on item 3, and the case asserts both.

That is not the same as "no ceiling is ever justified by a maximum smaller than
the truth", which is what this section claimed first (PR #35 R4). The ledger is
filtered to rows at the CURRENT case count, so adding one 0.0s case discards
every earlier run: `invariant` had 34 runs at 51 cases reaching 14.12s, and the
first two runs at 52 cases maxed at 12.78s, which derives **15** — the number CI
has been red against twice. Item 4 is `>=`, so a committed ceiling above the
freshly-derived one is accepted and nothing goes red.

**And item 5 stops short of closing that**, deliberately. It requires the
derivation to state what the RULE gives, not what `evals/run.py` commits, so
`12.89 × 1.15 = 14.82 → **15**` under a §3 heading that says 20s is GREEN — that
exact state was published in this round and the check accepted it (§3). Round 3
tried conjoining the two, requiring the rule's value to equal the committed
ceiling, and reverted it: a fresh case count has two or three runs, a short
sample derives lower, and the commit that adds the case then cannot pass its own
gate — R11's deadlock by another route (PR #35 R16). What the deviation buys is
that adding a case stays one commit. What it costs is a reader meeting an arrow
smaller than the ceiling printed beside it. What still holds is that the ceiling
itself cannot be wrong: item 6 grades the Ruling against `WALL_BUDGET_S` and
item 4 grades it against the ledger, so the residue is the arrow and nothing
else.

The residue is declared, not graded: a freshly republished band is a short
sample and therefore a LOWER bound on what the tree costs. The rule is that a
ceiling does not ratchet down on one. Republish the maximum, leave the ceiling
where the longer record put it, and move it down only with a measurement that
says so (T-R50 carries the widened-window option).

**What a reader should conclude.** The number beside each band is one named
run: the sentence cites its ledger timestamp, and
`published-band-matches-the-ledger` requires a row with that timestamp, at that
case count, whose wall clock IS the published number. So it is never a value
nobody measured. It is not necessarily the slowest run in the ledger — red runs
and runs taken mid-edit are in there too, and the maximum of all of them can sit
up to one ceiling step above the band source without anything going red. The
ceiling beside it is correct either way, because it is graded against that
maximum and not against the published number.

Whether the cited run was taken on a clean tree is judged **as of that run**: a
dirty row is refused only if a clean one was already available when the band was
published. Both halves of that are deliberate. Requiring clean outright
deadlocked adding a case — a tree only reaches count N+1 while the new case is
uncommitted, so every row at N+1 is dirty until the commit the check was
blocking (PR #35 R11). And judging as-of rather than as-of-now is what stops
later clean runs from retroactively reddening a published band, which is the
same treadmill this section refuses for the strict form. Both bands above are
live examples: each cites the run that measured its new case count, taken while
the 134th case was still uncommitted, and the clean green runs of this tree that
followed did not disturb them. The GREEN half is not required and not
requirable the same way (T-R53): this check is in both suites, so at a new count
every run is red until the band is republished.

If you want the exact current maximum, the ledger is the artefact — and the
grader prints it, with the case count, whenever the band needs republishing.

## Consequences

- **CI's numbers are measured, not promised.** The first version of this ADR
  left "the CI run of this branch is the measurement" as a promise; it came due
  immediately and the answer was no, twice over — `invariant` red at 15.06s and
  `fast` at 74.06s against 80. Both are now set from CI runs of the shipped
  tree (§5). `fast-wall-clock-budget`'s own `not_covered` still says this case
  cannot tell a measured number from an invented one; the four attempts are in
  §5 and in the workflow comment so a reader can check rather than trust.
- **The declared limitation stays declared.** Total wall clock is all that is
  graded: a case that gets 10s slower while another gets 10s faster is still
  invisible, and per-case timings still live in the committed reports.
- **README's wall-clock paragraph is rewritten**, because the numbers it
  published for the tag-shuffle justification were not reproducible: it said the
  suite ran 60.13s with "all of them" in `fast` when the real figure is ~64.6s,
  and called all three cases settle-bound when one of them costs 0.20s
  (PR #29 R10).
