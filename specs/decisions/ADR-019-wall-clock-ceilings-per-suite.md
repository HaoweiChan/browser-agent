# ADR-019: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: four ceilings, one per (suite, environment), each derived by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five) from a band computed from `evals/report/history.jsonl` and graded against it — local `fast` 60 → **80s**, local `invariant` **20s**, CI `fast` 80 → **90s**, CI `invariant` **20s** — read through one variable per suite (`EVAL_WALL_BUDGET_S_FAST`, `EVAL_WALL_BUDGET_S_INVARIANT`).
**Because**: M31 added real cost and the first repair moved three browser cases to `invariant`-only tags instead of facing it — which left the gate refusing a commit that changed nothing but JSON at 60.24s with every case passing — and the first version of this ADR then gave `invariant` a ceiling derived from local runs but enforced only on CI, where it had never been measured and immediately went red.
**Enforced by**: `fast-wall-clock-budget` (both ceilings, the set of suites that have one, and the override's scope), `published-band-matches-the-ledger` (the bands against the ledger), `published-band-slack-is-declared` (§6's bound), `evals/run.py` `over_budget()`

**Amends**: ADR-013 Decision 4 (local `fast` ceiling 60 → 80) and ADR-002 Decision 4 (a second suite now has a ceiling)

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

### 2. The local `fast` ceiling is 80s, computed from the ledger

Every LOCAL band here — this section's and §3's — is computed from
`evals/report/history.jsonl`, the ledger committed in this repo, and
`published-band-matches-the-ledger` grades that on every run — §6's numbered
list is what it requires, and sentences here name its items rather than argue
with them. It has to, because three bands in PR #29 did not
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

- Band source — `fast` at 137 cases, ts `20260823-200546`, **62.34s**, 137/137
  (`evals/report/20260823-200546-fast.json`; the run that measured this tree
  while its newest case was still uncommitted, so `dirty: true`).

The `137/137` is the cited row's own result, graded against it, not prose beside
it (T-R55). It is stated because a band source is taken as it is found — item 2 (cited-run)
requires a run that happened, and green is required nowhere in §6 — so a reader
comparing two bands should not have to read silence as a pass.

Every run of this tree is in `evals/report/history.jsonl`, committed beside
this file; the sentence above names the one the band is derived from by its
ledger timestamp. §6 item 2 (cited-run) and item 3 (same-ceiling) are what the
check requires of that run; item 4 (committed-ceiling) is not about it (T-R49).
The
ledger's own maximum at a given count may be higher than the band source,
because it includes red runs and runs taken mid-edit; §6 is why that is allowed
and by how much. The enumeration that used to stand here — and the one in §3 —
is gone: it was a snapshot of a file that grows on every gate run, nothing
graded it, and it had drifted to publishing six of the eight runs recorded at
the shipped case count, which is the R21 defect this ADR was amended over. What
is published here is now exactly what is graded (§6).

ADR-013 Decision 3's rule — slowest observed +15%, rounded up to a multiple of
five — gives 62.34 × 1.15 = 71.69 → **75**. The band published for the earlier
114-, 116- and 122-case trees is superseded rather than corrected in place: it was
derived by hand from a subset, and the point of the grader is that nobody has
to trust a hand-derived band again. The rule is unchanged; only the reading of
it was wrong.

Margin against the observed band is ~18s where before M31 it was ~0.2s. That is
a real loosening, and it is the point: a ceiling whose job is to catch drift
cannot also be the thing that fails on drift-free commits — this one refused a
commit that changed nothing but JSON.

### 3. `invariant` gets a ceiling: 20s

- Band source — `invariant` at 53 cases, ts `20260823-041729`, **13.32s**, 53/53
  (ADR-012 writes no per-case report for a green run, so the ledger row is the
  whole artifact — which is why the sentence cites the ts and not a file).

The same rule gives 13.32 × 1.15 = 15.32 → **20**. Two decimals on the product
because one is not enough to re-derive it: "15.3" and "15.0" both round up to a
multiple of five differently depending on how a reader reads them, and the
committed ceiling is 20 (PR #35 R13). Note the band moved within this round, and be
precise about why. The first two runs at 53 cases measured 12.87 and 12.89s,
which derive **15**; a band published from them was reachable and is green under
the check as it now stands — §6 item 5 (derivation) does not require the rule's value to
equal the committed ceiling. No commit of this branch ever published it
(`git log -S` on this file finds that figure only in the round-4 repair, quoting
it as an example), so the claim is reproducible rather than historical: call
`_band_wrong` with the band at 12.89s citing ts `20260823-041431` (51/53) and a
ledger holding only the two rows recorded at 53 cases by then, and it returns
`[]` (T-R48). What took the state out of reach was item 3 (same-ceiling), when a 13.32s run
landed and the ledger's maximum
crossed into the next band. Had that run not landed, the 15-deriving band would
have stood. This is the declared deviation in §6, not a mechanism catching
something.

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
one commit (`d173340` — 116 `fast`, 48 `invariant`; the tree at the time of
measurement, smaller than the one this branch ships, which is part of why the
CI half is debt, T-R51):

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

**What the check enforces.** This list is where the rules live, and sentences
elsewhere name the item they are about. Five rounds ended the same way — the
repair correct, its own description left behind (PR #35 R15/R16/R19/R20, PR #36
R1) — and a second copy of a rule is the thing that goes stale.

Be exact about how much of that is mechanism, because the claim that it was all
of it is what PR #36 R1 falsified, and the first attempt at being exact
overstated in turn (R10/R11). **Graded**, each clause with a mutation behind it
in `published-band-matches-the-ledger`: every item of this list is numbered and
slugged, with no gap and no slugless item, appended ones included; every
reference to it — here, in README, and in the marked band region of
`src/browser/eval_adapter.py` — names a number this list HAS and spells that
item's slug, so a bare name, a name for an item that does not exist, a name
aimed at the wrong item, a plural range and the retired `property N` numbering
are each red; and the region is checked before it is read — one occurrence of
each marker in the file, both markers starting their own line, the closing one
not inside a body, and every name in the band set (`_band…`,
`_check_published_band…`, `_BAND…`, `_SIX…`, `_SLACK_MARK`, `_REGION`) between
them by byte offset, a form of membership no comment can spell its way into
(PR #36 R19, where a substring test was satisfied by the comment warning
against it). Eleven ways of making this scan stop scanning have been watched
red: each of the five definitions moved out of the region one at a time, band
code added after the end marker, either marker deleted, a comment quoting a
marker a second time, a marker sharing a line with code, the closing marker
moved into a body, and the opening one moved inward past the module-level
block. What that set does NOT pin is the module-level names outside
it, `_ADR019`, `_README`, `_INDEX`, `_DECIMAL_TOKEN`, `_README_BAND_ROW` and
`_ADR_CEILING`: moving one of those out of the region takes no §6 reference with
it today, and nothing would notice if that changed (T-R63). **Not graded:** a
paragraph that paraphrases a rule and names no item at all, and references in
`tasks/TODO.md`, which is outside the scanned set (T-R62 carries both). What
keeps those rare is that there is one list to point at, and pointing is cheaper
than restating.
`published-band-matches-the-ledger` requires, per suite — except the last, which
is about this section itself:

1. (count) the published case count is the suite's current case count;
2. (cited-run) the band sentence cites a ledger row by timestamp, at that count, whose wall
   clock IS the published number and whose `passed/total` the sentence states as
   that row records it — and if the row is dirty, that no clean row at that count
   existed by then. Judged as of the cited run, not as of now;
3. (same-ceiling) the published number derives the SAME ceiling as the
   ledger's maximum at that count — `rule(published) == rule(ledger max)`, not `published >= ledger max`;
4. (committed-ceiling) the committed ceiling is at least `rule(ledger max)`,
   read from the ledger and never from the published number;
5. (derivation) the derivation sentence multiplies the published number, is right to two
   decimals, and states the ceiling **the rule gives** — `_band_rule(x)` — which
   must not exceed the committed ceiling;
6. (ruling) the Ruling's own local ceilings are the ones `evals/run.py` commits;
7. (readme-row) README's band row carries the same four values as this file, and neither
   document publishes two bands for one suite;
8. (references) every line of this list is numbered and opens with its slug,
   the numbering runs 1..N without a gap, and every reference to the list — in
   this file, in README, and in the marked band region of
   `src/browser/eval_adapter.py`, which is itself checked to still contain that
   code — spells a number the list HAS and that item's slug:
   `item 3 (same-ceiling)`. The number alone is a position, and a position
   stays valid when it is re-pointed at another rule (PR #36 R2) or when the
   list is renumbered under it; the slug is what a reference is bound to. A
   bare name, a name the list has no item for, the `property N` numbering
   PR #35 round 4 retired, and a plural range no single slug can carry are each
   red.

Green is required nowhere in that list and cannot be (T-R53); item 2 (cited-run) requires
the result to be *stated*, not to be a pass. Item 5 (derivation) states the rule's value and
deliberately does NOT require it to equal the committed ceiling — the paragraph
on what this does not cover, below, is why.

Two shapes the check emits are preconditions of the list rather than items of it
(T-R49): `adr_publishes_no_band_line` — this file carries no band sentence for a
suite, so the list has nothing to read; and `no_recorded_run_at` — the ledger
holds no row at the current case count, so item 2 (cited-run) has no candidate.

**What it lets through.** The published number may sit anywhere inside the band
that derives the committed ceiling — item 2 (cited-run) requires it to be a run that
happened, not the slowest one — so it can understate the ledger's maximum at
that count by up to one ceiling step — five seconds of ceiling divided by the rule's
1.15, a declared slack of one ceiling step (**4.35s**) of wall clock.
`published-band-slack-is-declared` derives that bound from the rule's own
constants rather than trusting this sentence, measures the headroom of each
band published above, and reports both — no per-suite number is written here,
because a number that moves with the band is the snapshot this section deletes
everywhere else.

The sweep reads three documents — this file, README and
`specs/decisions/INDEX.md` — and every copy of the bound in any of them carries
the marker `one ceiling step (**N.NNs**)` and is graded against the derived
value; a copy written without it is red wherever it stands, and a document that
would rather cite this section than republish the number carries none. The
sweep reads those documents' numbers as numbers, so a copy carrying a trailing
zero, or a space before its unit, is the same published bound and no more
invisible than the exact rendering — which is all it used to match (T-R45).
Writing this paragraph produced two such copies and it caught both.

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

**What the slack cannot hide — and what it does not cover.**
Item 4 (committed-ceiling) is graded against `rule(ledger max)` directly, from the ledger, never from the published
number, so a tree that crosses its band reddens the gate. R21's direction
(12.96s published where 13.57s was recorded: 15 where the rule said 20) is red
on that and on item 3 (same-ceiling), and the case asserts both.

That is not the same as "no ceiling is ever justified by a maximum smaller than
the truth", which is what this section claimed first (PR #35 R4). The ledger is
filtered to rows at the CURRENT case count, so adding one 0.0s case discards
every earlier run: `invariant`'s runs at 51 cases reached 14.12s, and the
first two runs at 52 cases maxed at 12.78s, which derives **15** — the number CI
has been red against twice. Item 4 (committed-ceiling) is `>=`, so a committed
ceiling above the freshly-derived one is accepted and nothing goes red.

**And item 5 (derivation) stops short of closing that**, deliberately. It requires the
derivation to state what the RULE gives, not what `evals/run.py` commits, so
`12.89 × 1.15 = 14.82 → **15**` under a §3 heading that says 20s is GREEN — a
state this branch could have reached and the check accepts, though no commit of
it published that band (§3). Round 3
tried conjoining the two, requiring the rule's value to equal the committed
ceiling, and reverted it: a fresh case count has two or three runs, a short
sample derives lower, and the commit that adds the case then cannot pass its own
gate — R11's deadlock by another route (PR #35 R16). What the deviation buys is
that adding a case stays one commit. What it costs is a reader meeting an arrow
smaller than the ceiling printed beside it. What still holds is that the ceiling
itself cannot be wrong: item 6 (ruling) grades the Ruling against
`WALL_BUDGET_S` and item 4 (committed-ceiling) grades it against the ledger, so
the residue is the arrow and nothing else.

The residue is declared, not graded: a freshly republished band is a short
sample and therefore a LOWER bound on what the tree costs. The rule is that a
ceiling does not ratchet down on one. Republish the maximum, leave the ceiling
where the longer record put it, and move it down only with a measurement that
says so (T-R50 carries the widened-window option).

**What a reader should conclude.** Item 2 (cited-run) is why the number beside each band is
never a value nobody measured. It is not necessarily the slowest run in the
ledger — red runs and runs taken mid-edit are in there too, and the maximum of
all of them can sit up to one ceiling step above the band source without
anything going red. The ceiling beside it is correct either way:
item 4 (committed-ceiling) grades it against that maximum and never against the
published number.

Item 2 (cited-run)'s as-of-the-cited-run reading of cleanliness is deliberate in both
halves. Requiring clean outright deadlocked adding a case — a tree only reaches
count N+1 while the new case is uncommitted, so every row at N+1 is dirty until
the commit the check was blocking (PR #35 R11). And judging as-of rather than
as-of-now is what stops later clean runs from retroactively reddening a
published band, which is the same treadmill this section refuses for the strict
form. Both bands above are live examples: each cites the run that measured its
new case count, taken while that count's newest case was still uncommitted, and
the clean green runs of this tree that followed did not disturb them. The GREEN
half is not required and not requirable the same way (T-R53): this check is in
both suites, so at a new count every run is red until the band is republished —
which is why item 2 (cited-run) requires the result to be disclosed instead.

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
