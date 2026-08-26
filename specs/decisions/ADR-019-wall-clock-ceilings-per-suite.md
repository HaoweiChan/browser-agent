# ADR-019: the wall-clock ceiling moves to where the tree lives, and `invariant` gets one too

Date: 2026-08-22
Status: accepted

**Ruling**: four ceilings, one per (suite, environment), each derived by ADR-013's own rule (slowest observed run +15%, rounded up to a multiple of five) from a band computed from `evals/report/history.jsonl` and graded against it — local `fast` 60 → 80 → 90 → **105s** (ADR-021, then ADR-029), local `invariant` **20s**, CI `fast` 80 → **90s**, CI `invariant` **20s** — read through one variable per suite (`EVAL_WALL_BUDGET_S_FAST`, `EVAL_WALL_BUDGET_S_INVARIANT`).
**Because**: M31 added real cost and the first repair moved three browser cases to `invariant`-only tags instead of facing it — which left the gate refusing a commit that changed nothing but JSON at 60.24s with every case passing — and the first version of this ADR then gave `invariant` a ceiling derived from local runs but enforced only on CI, where it had never been measured and immediately went red.
**Enforced by**: `fast-wall-clock-budget` (both ceilings, the set of suites that have one, and the override's scope), `published-band-matches-the-ledger` (the bands against the ledger), `published-band-slack-is-declared` (§6's bound), `evals/run.py` `over_budget()`

**Amended by**: ADR-029 (Decision 2's local `fast` ceiling 90 -> 105, on the number `published-band-matches-the-ledger` derived after M42 grew the suite (the count is `git diff main --stat` away and is published nowhere, because three documents published three different values for it — PR #56 R16); CI's stays 90 because nothing in that change measured CI) · ADR-021 (Decision 2's local `fast` ceiling 80 -> 90, on the number `published-band-matches-the-ledger` derived after the M32 merge grew the suite; the other three ceilings unchanged)

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

### 2. The local `fast` ceiling is 90s, computed from the ledger

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

§5's CI numbers are not in that ledger and cannot be — no CI run commits its
wall clock, and this ADR does not make one: §7 says why, and labels them for what
they are, hand-read off the log of a named workflow run so a reader can re-read
it. **They are also, as of 2026-08-26, measurements of a SMALLER tree than the
one shipping**: §5's four attempts ran the case count §5's own table records,
on the commit it names, and this tree is larger — so CI's committed 90s ceiling
is a number no run of this tree has tested. The count is not repeated here: this
sentence said 152 for one round, which is ADR-021's run `32639577041` on
`07e3d34`, not §5's `32561162459` on `d173340`, and a document contradicting
itself about which run it means is worse than one that makes the reader look
(PR #56 R15).
ADR-029 §2 carries the ruling — the ceiling is not raised on an extrapolation,
and until a CI run of this tree exists and is cited here by workflow-run id,
every gate-green claim on that branch is scoped to the local environment
(PR #56 R7). They stay ungraded by `published-band-matches-the-ledger`, which reads this
repo's ledger and nothing else.

**The ledger's numbers, at the case count this branch ships:**

- Band source — local `fast` at 213 cases, ts `20260825-195505`, **88.42s**, 211/213
  (`evals/report/20260825-195505-fast.json`; `dirty: true`, for the reason the
  next paragraph gives, and red — the two failures are `docs-numbers-are-derived`
  and `published-band-matches-the-ledger` themselves, mid-refresh at the moment
  this row was recorded. That is the general shape of every band republish and
  not a fact about any one milestone: a tree reaches its new case count only
  while the cases are uncommitted, and this section's own republication is what
  the addition forces. Here the addition is the cases M42 adds. The stamp is UTC, as
  every row written since §7 is. How many rows the ledger holds at this count,
  and what its maximum is, are deliberately not written here — see §3. Each
  re-derivation of this section is exactly the cost `T-M39-11` names, and PR #56
  R5 is what it costs when the numbers are refreshed and the sentence explaining
  them is not: this bullet carried M39's tree as its explanation under M42's
  row, saying 207 cases on one line and 181 four lines later, with
  `published-band-matches-the-ledger` grading the scalars and never the prose.)

**This band was dirty for one commit, and that price is what §7 removed.** A case
addition forces a dirty citation: the tree only reaches its new count while the
new case is uncommitted, which is the entire reason the dirty allowance exists. A
dirty citation used to be green locally and red on CI — `T-M32-13` is the
diagnosis, the ledger's `ts` being a naive local stamp compared lexicographically
against CI's UTC ones, so item 2 (cited-run) refused a dirty row against any
clean row stamped earlier and every CI row is clean and stamped eight hours
behind ours. Two trees paid it in full: M28's merge commit published
`ts 20260823-211340`, 70.46s, 151/153, dirty, and the next commit re-cited a
clean run that could not exist until the first had landed; M40 then added
`ui-terminal-state-on-every-ending` and `view-proxy-refuses-private-and-redirects`
and paid the same two commits again. §7 gives every row an environment and item 9
(environment) keeps CI's out of a `local` band's ledger, so a dirty citation is no
longer disqualified by a row from another machine. Locally that is demonstrated —
this band cites a dirty row, and the row it cites is itself red on exactly the
two cases this merge is repairing, which item 2 (cited-run) does not require to
be green. The CI half is asserted, not
demonstrated from here, for the reason §7 gives at the end (T-R74).

The cited rows' own results — (restated — `fast`: 213 cases, 211/213) and
(restated — `invariant`: 74 cases, 72/74) — are graded against the bullets they
summarise, by item 10 (restatement), not merely stated beside them (T-R55).
The result is stated because a band source is taken as it is found — item 2
(cited-run) requires a run that happened, and green is required nowhere in §6 —
so a reader comparing two bands should not have to read silence as a pass.

**The band cites the SLOWEST run on record when it is published, not the
fastest** (PR #42 R14). Item 3 (same-ceiling) compares the ceiling the published number derives
against the ceiling the ledger's maximum derives, so what matters is not how
close the two numbers are but whether ordinary run-to-run variance can move
either across a rounding step. This branch learned it the expensive way: its
168-case band published the FASTEST clean run, 72.19s → 85, and the next
ordinary green gate run of the same tree came in at 75.0s → 90 and turned both
suites red with no code change. Publishing the slowest run on record is the least-slack reading item 3
(same-ceiling) allows, and a later run that is slower still costs nothing while
it lands in the same band — at 175 cases a 73.07s row arrived after a 73.04s
band was published and the check stayed green, because both derive 85. That is the property,
and it is not the same as being the maximum forever. What it does not buy is
immunity, and this merge is the proof: the band was first published here at
73.47s → 85, the very next gate run came in at 74.19s → 90, and item 3
(same-ceiling) reddened exactly as it did at 168 cases. The band re-cites that
slower run rather than the faster one, so the published number now sits inside
the 73.92-78.26s window where every value derives 90. What item 3
(same-ceiling) compares is exactly two numbers — the published one and the
ledger's MAXIMUM at this count in this environment: `_band_rule(said) !=
_band_rule(slowest)`, with `slowest = max(recorded)`. It never iterates the
rows, and the rows below that maximum are compared against nothing, which is
why a faster run cannot redden this band and only a slower one can. A run above
78.26s would still require a re-citation. That coupling — a band pinned to
whatever the slowest recorded run happens to be, whoever recorded it — is what
`T-M38-5` records, named rather than papered over.

Two earlier versions of that sentence were wrong in opposite directions and
both are worth leaving on the record: one published a measured spread and a row
count, which were stale within the hour (PR #42 R24, the snapshot defect §3
refuses two sections down); its replacement claimed EVERY row at this count
derives the band's ceiling, which is false here — the rows at this count do not
all derive one ceiling — and describes an iteration the grader does not perform
(R27). The sentence above is read off the comparison in
`src/browser/eval_adapter.py`, and the check that falsifies it is one line:
print `_band_rule` over the rows at this count.

**Ablation probes are not runs, and their rows are deleted rather than cited.**
PR #42's repair had to prove that each narrowing conjunct is pinned, which
means running the whole suite with that conjunct removed; `evals/run.py`
appends a history row for every run, so five rows of deliberately broken code
landed in the ledger, one of them (74.29s, 162/165) its maximum at this case
count. Item 3 (same-ceiling) then FORCED the published band onto it: a band
describing code that never existed as a commit. It recurred one round later —
two more probe rows at 168 cases, one of them again the maximum (75.02s,
162/168) — which is the strongest evidence `T-M38-5` could ask for that the
hole is in the mechanism rather than in one careless sweep. Those rows and
their report files were deleted — five at 165 cases, two at 168 and two at
170, nine in all — on the
precedent this repo already set — PR #20 R18,
where `_main_exit_code` injected fabricated rows and 52 of 241 committed lines
were probe artifacts, redirected to a temp path and *"deleted by hand as part
of the same repair"*, because *"it is a probe of the exit-code path, not a
run"*. An ablation probe is not a run either, and ADR-012 keeps this ledger to
preserve what the gate actually measured.

What was NOT deleted: the two rows at 165 cases with real reds,
`20260823-232059` (163/165) and `20260823-232408` (164/165). Those are gate
runs of the shipped resolver taken while the derived doc numbers were
mid-refresh — the code is the code that ships, the reds are exactly the two
doc-derivation cases a case addition reddens, and deleting a real red run to
tidy a ledger is the worse error.

**Every deleted row, by `ts`, so a reader can reconcile without trusting this
paragraph** (PR #42 R16 — the previous version of it published totals that were
a snapshot of a file which grows on every gate run, and neither total matched
the committed ledger by the time anyone read it). Deletions are what needs
listing; the kept rows are simply the rest, and their count is deliberately not
published here for the same reason §3 stopped enumerating runs.

Removed from the COMMITTED ledger by `820d807` — verifiable with
`git show 820d807 -- evals/report/history.jsonl`, which is the only kind of
deletion git can show:

| ts | suite | passed/total | wall_s | ablation |
|---|---|---|---|---|
| `20260823-231056` | fast | 162/165 | 74.29 | `READS` widened |
| `20260823-231208` | fast | 162/165 | 72.02 | interchangeability, text half |
| `20260823-231330` | fast | 162/165 | 72.44 | interchangeability, role half |
| `20260823-231442` | fast | 157/165 | 71.87 | plural test removed |
| `20260823-231611` | fast | 161/165 | 72.63 | plural test un-hoisted |

Removed BEFORE they were ever committed — the first two in round 2, the last
two in round 3, whose sweeps ran at 170 cases — and therefore invisible to git.
This table is their only record, which is exactly why it is here:

| ts | suite | passed/total | wall_s | ablation |
|---|---|---|---|---|
| `20260824-001355` | fast | 162/168 | 75.02 | rung 3 ungated |
| `20260824-001507` | fast | 163/168 | 71.95 | trailing-`s` exclusion reverted |
| `20260824-084337` | fast | 167/170 | 73.97 | `ss` exclusion dropped |
| `20260824-084452` | fast | 167/170 | 74.36 | `ss` exclusion widened to `sui` |

Nine rows, nine ablation sweeps, each one at a pass count no shipped tree
produces. Two of the nine were the ledger's maximum at their case count when
they landed, which is how they reached the published band in the first place.
That the isolation mechanism this repo built for one probe class does not cover
ablation is `T-M38-5`.

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
the shipped case count, which is the R21 defect this ADR was amended over
(PR #35 R21; PR #34 R21 is the same defect found independently on the M32
branch, and gets the same resolution — see §3). What
is published here is now exactly what is graded (§6).

ADR-013 Decision 3's rule — slowest observed +15%, rounded up to a multiple of
five — gives 88.42 × 1.15 = 101.68 → **105**, which is exactly the
committed 105. The ceiling was moved 90 → 105 by ADR-029, derived
from the slowest row this tree has recorded (the band source §2 cites above,
which is the ledger maximum at the shipped case count by construction); M42's growth is in case COUNT and not in per-case cost — the condition ADR-021 named when it said the answer
to per-case growth is removing waste rather than another raise. Item 5
(derivation) grades the arrow against the RULE and never against the committed
ceiling, which is why an arrow one step under the heading's number is green and
declared rather than a contradiction: §6's no-ratchet-down rule is that a
freshly republished band is a short sample and therefore a lower bound on what
the tree costs. The band
published for the earlier
114-, 116- and 122-case trees is superseded rather than corrected in place: it was
derived by hand from a subset, and the point of the grader is that nobody has
to trust a hand-derived band again. The rule is unchanged; only the reading of
it was wrong.

Margin against the observed band is ~19s where before M31 it was ~0.2s. That is
a real loosening, and it is the point: a ceiling whose job is to catch drift
cannot also be the thing that fails on drift-free commits — this one refused a
commit that changed nothing but JSON.

### 3. `invariant` gets a ceiling: 20s

- Band source — local `invariant` at 74 cases, ts `20260825-195336`, **14.18s**, 72/74
  (`dirty: true`, and red, for the same structural reason §2's is and stated the
  same general way: a tree reaches its new case count only while the cases are
  uncommitted, so 71 exists only while M42's invariant-tagged additions are, and
  the two red cases — `docs-numbers-are-derived` and
  `published-band-matches-the-ledger` — are the two this republish clears; the
  run is red, so ADR-012 wrote a per-case report for it and this bullet cites
  the file the way §2's does — `evals/report/20260825-195336-invariant.json`.
  As in §2,
  nothing about how many rows sit at this count, or which of them is slowest, is
  written here. M40's SSRF case `view-proxy-refuses-private-and-redirects` is
  deliberately NOT in this suite: it was tagged `invariant`, moved this band, and
  was moved back to `fast`-only because CI's invariant suite runs 17.58s at that
  count and derives a different ceiling — `T-M40-3` carries that decision.
  `T-M32-13`, which the note originally cited beside it, is closed here; whether
  its closure changes M40's tagging is T-M40-3's question, not this section's.)

**No graded form of "the published row is the maximum" is currently known.**
`T-R85` records the class, why the strict form is refused, and the candidate that
was proposed and then killed on its own arithmetic — it was green on the defect it
claimed to catch (PR #45 R5). The paragraph above says what the maximum IS and
where to read it; what nothing says is that the published row equals it. Until a
form exists that is red on a band published below the maximum and green on one
published at it, this class is caught by reading, and §6's "What it lets through"
is the bound that holds meanwhile (PR #45 R2, R8).

T-M40-1's case is tagged `fast` and `invariant` both, so it moved this count by
one from the other direction than the case the bullet above says is deliberately
absent — the bullet's 66 (65 + 1) is that move, landed. The CI question `T-M40-3` owns is therefore live again, with the one
difference that has to be stated rather than assumed: this case measures 0.01s —
it stubs playwright's entry point and launches no browser — where M40's SSRF case
was the expensive one. On `T-M40-3`'s own committed numbers (CI invariant 14.88s
at 58 cases, ADR-021) 14.88 × 1.15 = 17.11 → 20, so a case costing 0.01s leaves
the derived ceiling at 20 rather than 25. That is a projection from two committed
numbers, not a measurement: only a CI run confirms it, and if it is wrong the
symptom and the remedy are both `T-M40-3`'s. This ADR publishes the local band;
CI's ceiling is measured on CI (§5).


Neither band quotes the ledger's maximum, or counts the rows behind it, and that
is the fix for a defect this file has now produced three times. The third was
this round: §2 called its citation "the only row this count has" and §3 claimed a
specific number of rows were available and that the slower had been chosen "so the
published number sits as close to the ledger's own maximum as a real run allows".
Both counts were wrong against the ledger committed beside them, and §3's stated
selection rule was not the one the band followed — none of it graded (PR #41 R2).
The counts are not repeated here, and that is deliberate rather than coy: the
first attempt at this paragraph quoted them, and they were stale against the very
next commit's ledger, which is the same defect one paragraph after fixing it
(PR #41 R13). Any row count in prose is a snapshot of a file that grows on every
gate run. `published-band-matches-the-ledger` prints `ledger_slowest` with the
case count whenever a band needs republishing; that is the artefact. A band
sentence carries what item 2 (cited-run) grades and nothing a reader has to take
on trust: the run, its wall clock, its result, and its `dirty` flag. §3 published **13.80s** and the final
`origin/main` merge brought in a 13.92s row (ts `20260823-202223`, dirty, 57/58)
that made the sentence false — while §2, two sections up, was hand-copying its
own maximum by the same method, so the two halves of one decision disagreed on
method (PR #34 R29). A hand-copied scalar sitting beside a computed one is
exactly the drift class R21 and `T-M32-8` both name. The maximum is whatever
`published-band-matches-the-ledger` reports as `ledger_slowest`, computed over
every row at the current case count — red and mid-edit runs included, which is
why it can exceed the band source (§6, and the paragraph above) — and the
grader prints it, with the case count, whenever a band needs republishing.
Nothing here went red on either scalar: both derived 20, which is precisely why
this had to be caught by reading rather than by the gate.

The same rule gives 14.18 × 1.15 = 16.31 → **20**, which is the committed
ceiling. Two decimals on the product because one is not enough to re-derive it:
"15.8" and "15.0" round up to a multiple of five differently depending on how a
reader reads them (PR #35 R13).

Both bands above are republished at whatever case count this branch ships, which
has moved on every `origin/main` merge and moves again on the next one — so the
counts are in the graded bullets and are not narrated here (PR #45 R4).
Neither bullet is the enumeration this file used to carry. PR #34 R21 found
that enumeration publishing three runs where the ledger held six and calling the
smallest of them the maximum — the same defect PR #35 had already fixed here by
deleting the list and citing one graded row instead, which is the resolution
both findings get.

The paragraph below records the 53-case band this file carried before those
merges. It is kept because its reasoning about §6 item 5 (derivation) is general
and its evidence is reproducible; the numbers in it are that superseded band's,
not the one published above.

The rule gave 13.32 × 1.15 = 15.32 → **20** there. Note the band moved within
that round, and be precise about why. The first two runs at 53 cases measured
12.87 and 12.89s, which derive **15**; a band published from them was reachable
and is green under the check as it now stands — §6 item 5 (derivation) does not
require the rule's value to equal the committed ceiling. No commit ever
published it (`git log -S` on this file finds that figure only in the round-4
repair, quoting it as an example), so the claim is reproducible rather than
historical: call `_band_wrong` with the band at 12.89s citing ts
`20260823-041431` (51/53) and a ledger holding only the two rows recorded at 53
cases by then, and it returns `[]` (T-R48). What took the state out of reach was
item 3 (same-ceiling), when a 13.32s run landed and the ledger's maximum crossed
into the next band. Had that run not landed, the 15-deriving band would have
stood. This is the declared deviation in §6, not a mechanism catching something.

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

Not projected from local runs, which is the mistake §3 made. **Hand-read off the
workflow log, not from the ledger** (§7): four attempts of eval-gate run
[32561162459](https://github.com/HaoweiChan/browser-agent/actions/runs/32561162459)
on commit `d173340` — 116 `fast`, 48 `invariant`; the tree at the time of
measurement, smaller than the one this branch ships. `gh run view 32561162459
--attempt N --log` reprints each line below.

| attempt | `invariant` | `fast` |
|---|---|---|
| 1 | 16.47s | 69.54s |
| 2 | 15.85s | 74.06s |
| 3 | 14.80s | 69.37s |
| 4 | 15.60s | 74.04s |

Each cell is one `[eval] cost … wall Ns` line of that attempt's log, with
`invariant` 48/48 and `fast` 116/116 in all four. **All eight cells of this table
are graded**, by `ci-numbers-are-derived`, and each of the eight was watched red
one at a time: they are compared cell-by-cell, in attempt order, against the copy
in `.github/workflows/eval.yml`'s comment block, so editing either copy reddens
the gate and deleting the workflow's block does too. Round 1 of that case did NOT
do this: `invariant`'s column was only ever read through `min`/`max`, so attempts
2 and 4 could be edited freely with everything green — two numbers in a spec that
nothing read, which is the exact residue this case exists to close (PR #41 R14).

From this table the same case also reads back README's four `fast` values, both
min-max ranges, both ceilings those ranges derive, and the run id above, which
must appear in both documents; and it requires the ceilings derived here to be
the ones the workflow declares. `published-band-matches-the-ledger` still does
not see any of these numbers — it reads the committed ledger and no CI row is in
it — which is why a second case exists at all.

Two things are NOT pinned, stated because the alternative is a sentence claiming
more than it does. First: that anyone ever ran these four attempts. Both copies
could be wrong together and the gate would stay green; the run id is what a
reader checks (`gh run view … --log`), and T-R73 carries the ledger route that
would make it a mechanism. Second: CI figures published anywhere other than this
section, README and the workflow comment — ADR-013's copy of the superseded
95-case band is not read here, and is owned by `task/T-M32-9`.

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
`_check_published_band…`, `_BAND…`, `_SIX…`, `_SLACK_MARK`, `_REGION`,
`_LEGACY_ENV`) between
them by byte offset, a form of membership no comment can spell its way into
(PR #36 R19, where a substring test was satisfied by the comment warning
against it). Every way found so far of making this scan stop scanning has been
watched red — and this sentence carries no count of them, having twice carried a
wrong one: first a total that went stale when the band set grew, then a
"seven definitions and the `_LEGACY_ENV` constant" that counted eight members of
a set of seven, `_LEGACY_ENV` being one of the seven (PR #41 R5). The set is
`_BAND_DEF`'s alternatives, listed above; the mutations are: every name in it
moved out of the region one at a time, band
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
9. (environment) the band sentence names the environment it was measured in, and
   every item above reads only the ledger rows recorded there. A row carrying no
   `env` field is read as `local`, because every row committed before T-R44 is one
   and all of them are local runs. A band naming an environment the ledger holds
   no rows for lands in the `no_recorded_run_at` precondition below rather than
   passing for want of anything to compare against.
10. (restatement) a sentence elsewhere in this file that quotes a band's case
   count and result writes them in the marked form — the word `restated`, the
   suite, `N cases`, `P/T` — and both numbers are the ones that band's bullet
   publishes. The form is described rather than shown, because a literal example
   here would be a third copy of the very numbers this item exists to keep from
   drifting, and the check would read it as one (the same trap `_REGION` names
   in the code: a marker written out is the first one the scan finds). Two rounds running, a repaired band left a
   paragraph summarising it behind (PR #46 R3, then R5 against R3's own fix), so
   the copy is now read back against the original. An unmarked restatement is
   still invisible, the same ceiling item 8 (references) declares (T-R62).

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
form. Both bands above are live examples of the as-of rule doing its job in the other
direction: each was first published against a dirty row — the only kind that
exists at a count whose newest case is still uncommitted — and each is re-cited
here, in the same PR, to the clean green receipt that could not exist until
that first commit had landed. The GREEN
half is not required and not requirable the same way (T-R53): this check is in
both suites, so at a new count every run is red until the band is republished —
which is why item 2 (cited-run) requires the result to be disclosed instead.

If you want the exact current maximum, the ledger is the artefact — and the
grader prints it, with the case count, whenever the band needs republishing.

### 7. (2026-08-23) A band belongs to an environment, and the ledger records which

**One missing dimension, two runs, two clauses — and both of them fired.** The
Ruling above has said "one per (suite, environment)" since this ADR was written.
The grader had not: `published-band-matches-the-ledger` read every
`history.jsonl` row the process could see. On CI that is a strictly larger set
than the committed ledger, because `.github/workflows/eval.yml` runs
`--suite invariant` first and that run appends its own row to the job's copy of
the file before `--suite fast` grades §3's band against it. What that extra row
then broke depended on which clauses existed in the tree, and the two red CI runs
behind this section are not the same failure. Getting that wrong once already
cost a round: this section's first version generalised the second run's mechanism
onto the first, where the clause it names had not been written yet.

**Run 32626835735 — sha `434a98d`, T-R44's own origin — fired item 3
(same-ceiling), on the wall clock.** That tree publishes `invariant` 12.92s at 52
cases; CI measured 16.02s at 52/52 on the same count. `rule(12.92)` is 15,
`rule(16.02)` is 20, so the published band and the ledger's maximum derive
different ceilings and the check reports `{published_slowest: 12.92,
derives_ceiling: 15, ledger_slowest: 16.02, ledger_derives: 20}` — red on CI at
`fast 132/133`, green locally on the same tree. Item 2 (cited-run) cannot be the
explanation there and the tree proves it rather than the argument:
`git show 434a98d:src/browser/eval_adapter.py` has no `_band_wrong` and no
`cited_a_dirty_run` at all, and its `_BAND_LINE` is the pre-`ts` form
`r"Slowest recorded \`(fast|invariant)\` run at (\d+) cases: \*\*([\d.]+)s\*\*"` —
no timestamp group, so nothing in it could read a `ts` or a `dirty` flag.

**Run 32637648447 — sha `11545a1`, on `task/M32` — fired item 2 (cited-run)'s
dirty allowance, on the timestamp.** That is T-M32-13, diagnosed there and
replayed here. `evals/run.py` stamped `ts` with
`time.strftime("%Y%m%d-%H%M%S")` — naive local time, no zone — and the dirty
clause compares those strings as if they were a total order on real time
(`r["ts"] <= ts`, "was a clean row already available when the band was
published?"). The ledger mixes zones. A band row written on that laptop at
`20260823-192533` is 19:25:33 Asia/Taipei, 11:25:33 UTC; CI's `invariant` row
`20260823-115044` was written **25 minutes later in real time** and sorts **eight
hours earlier as a string**. CI's row is clean — a fresh checkout makes
`git_dirty()` false — so it answers yes to a question about a moment it had not
happened in, and reddens a band the allowance exists to permit. That allowance is
PR #35 R11's: a tree only reaches count N+1 while the new case is uncommitted, so
the band's own row is dirty by construction.

The control isolates the second mechanism and is decisive: same CI row, same
16.03s, same `dirty: false`, only the `ts` moved to sort after the band row —
green. Replayed through `_band_wrong` at a band and a CI row that derive the SAME
ceiling, so item 3 (same-ceiling) is silent and only the dirty clause can speak:
`[{'suite': 'invariant', 'cited_a_dirty_run': '20260823-192533',
'clean_runs_available_by_then': ['20260823-115044']}]` before, `[]` after moving
the stamp, `[]` with the rows env-tagged. Speed does nothing **there**. On
`434a98d` speed did all of it — which is why both are written down.

**What the second one cost, beyond the red run:** adding a case became two
commits instead of one. CLAUDE.md hard rule 2 makes adding a case this repo's
most common operation and every one republishes a band, so the cited row is dirty
by construction; the commit lands green, CI runs the committed tree, CI's clean
row claims to predate a band it followed, and the author re-runs on a clean tree,
re-cites, and commits again. PR #34 paid that tax. Replayed at the state a
case-adding commit actually lands in — the dirty citation, CI's clean row, and a
clean local re-run — the untagged ledger gives the payload above and the tagged
one gives `[]`.

`main` was green on the second mechanism for a reason no better than the bug: its
band cites `20260823-041729`, 04:17 local — 2026-08-22 20:17 UTC — and a CI stamp
sorts before that string only if the run happened between 00:00 and 04:17 UTC,
which none did. A band republished during Taipei daytime lands in the window. The
first mechanism had already cost something too: M35 moved a new invariant case
into `fast` to keep §3's band on the count `main` measured (T-R44).

**Item 4 (committed-ceiling) is the one that has not fired, and only it.** The
paragraph this replaces called the whole wall-clock symptom latent, which is
wrong twice over — item 3 (same-ceiling) fired on `434a98d`, and item 3
(same-ceiling) and item 4 (committed-ceiling) do not test the same thing. Item 3
(same-ceiling) compares `rule(published)` with `rule(ledger max)`, which is 15
against 20 on that run. Item 4 (committed-ceiling) compares the COMMITTED ceiling
with `rule(ledger max)`, and 20 against 20 holds, so item 4 (committed-ceiling)
stayed green. It would go red above 17.39s — the top of that band, 20 / 1.15 —
where `rule(ledger max)` becomes 25, and it would be **ungreenable locally**,
because a local ledger holds no CI row to reproduce it with. Against this run's
own 16.02s that is 1.37s of margin, 8.55%, versus a runner spread §5 itself
records at 6.8%. (The 1.36s / 8.5% figure this paragraph used to carry is the
same arithmetic against 16.03s — run 32637648447's number, not this one's.) The filter below
closes item 3 (same-ceiling) and item 4 (committed-ceiling) together, because
`slowest` is computed from the environment's own rows.

**Every history row written from here on carries an `env` tag** (`evals/run.py`
`env_tag()`) — the rows already committed do not, which is the next paragraph — and §6
item 9 (environment) filters the ledger to the band's own environment before any
other item reads it. The tag is `EVAL_ENV` when set, otherwise `ci` when the
runner sets `CI`, otherwise `local`. The `CI` fallback is what actually tags a
runner — Actions sets `CI` unconditionally — so the workflow's `EVAL_ENV: ci` is
a louder second belt rather than the mechanism. It is deliberately NOT derived
from the
effective `EVAL_WALL_BUDGET_S_*`, the obvious candidate: CI's `invariant` ceiling
is 20 and so is this laptop's, so that reading would have given both environments
one tag on the very suite the defect appeared in.

A row with no `env` field reads as `local` (`_LEGACY_ENV`). That is not a default
chosen for convenience: every row written before this section is untagged and
every one of them was measured here, because nothing but a local run has ever
appended to the committed file — which is §5's problem, below. Be exact about
what rests on it, since the obvious claim is wrong: the bands in §2 and §3 cite
rows recorded AFTER the tag existed, so setting `_LEGACY_ENV` to anything else
leaves `published-band-matches-the-ledger` green today — the untagged rows it
would orphan are all at case counts nobody publishes a band for. What holds the
reading up is the case, not the live ledger:
`band-is-graded-against-its-own-environment` drives an untagged row through
`_band_wrong` and requires it to be judged as a local one. The reading becomes
load-bearing again the moment a band is republished from a row this ADR predates,
which is the only way an old row can matter.

**§5 stays hand-read, and now says so with a run id.** The other route was to
make CI's wall clock land in the ledger — a job step that commits a row, or an
artifact the check reads. It is not taken here: a step that commits from a
pull-request job is a permissions-and-push-loop problem to solve for one number
per run, and it cannot be verified from a laptop, which is the exact shape that
produced this debt (numbers published that no committed artifact reproduces). So
§5's four numbers are labelled for what they are and pinned to eval-gate run
32561162459, attempts 1-4, where `gh run view … --log` reprints them.

**What is graded grew, and this paragraph is the third place that said otherwise**
(PR #41 R15; it was written when the labelling route shipped with nothing behind
it, and left standing through two rounds that closed the same claim elsewhere).
At HEAD, `fast-wall-clock-budget` checks that the workflow declares the ceilings
§5 names, AND `ci-numbers-are-derived` pins all eight cells of §5's table against
the workflow's own copy of them, README's four `fast` values, both ranges, both
derived ceilings, and the run id in both documents. The mutation that demonstrates
each of those lives in `ci-numbers-are-derived`'s own `watched_red`, not in §5 —
§5 carries only the eight-cell one. An earlier version of this sentence sent the
reader to §5 for all seven and was the fifth instance in PR #41 of a description
claiming more than its check does (T-R78, closed here).

What is still not graded, and cannot be from here, is the one thing this route
never claimed: that those four attempts were ever run. The run id makes that
checkable by a reader, not by the gate (T-R51 closed on that reading; T-R73
carries the ledger route if it is ever wanted).

**Two properties ship, and neither substitutes for the other.** "A band is graded
against its own environment" is about *which rows* an item reads; "`ts` is a
valid total order on real time" is about *how those rows are ordered*. They are
different claims, and the first attempt at this section delivered only the first
and let a reader infer the second — which is how the next person inherits an
ordering bug as a mystery. Both are here now:

- **`env` scoping** (item 9 (environment), above). A foreign-environment row is
  the wrong row to derive a ceiling from whatever its stamp says, so CI's
  `invariant` row reaches neither the dirty clause nor `ledger max`. This is what
  closes the second symptom, which no stamp change would have touched.
- **`ts` is stamped in UTC** — `evals/run.py` `stamp()`, `time.gmtime`. This is
  the ordering key itself, and it is the fix for the clause that actually fired.
  Graded by `ledger-ts-orders-real-time`, which sets both zones explicitly with
  `TZ` and `time.tzset()` and re-derives T-M32-13's pair from its two real
  instants: a check that asked the host what time it is would be red on this
  laptop and GREEN on a UTC runner, which is the environment-dependent shape
  `fast-wall-clock-budget` has been falsified by twice.

T-M32-13 closes on the pair, and `tasks/DONE.md` records it — it is `task/M32`'s
finding and its diagnosis is the one this section is written from.

**The migration, stated for the ledger as it actually exists.** Switching the
stamp does not convert the ~1,300 rows already committed. They keep their naive
local stamps and are NOT rewritten: no row records the zone it was written in, so
a conversion would have to invent one, which is precisely the fabricated
precision this repo grades against everywhere else. So the ledger holds
local-stamped rows before this commit and UTC-stamped rows after it, and the
boundary moved from "which machine wrote this" to "which side of this commit" —
it did not disappear.

What makes that safe is narrow and worth stating exactly, because it is an
assumption and not a mechanism: `_band_wrong` only ever reads rows at the CURRENT
case count, and both live counts contain only post-switch rows — this commit's
own cases moved `fast` to 156 and `invariant` to 61, and every row at those
counts was written after the switch. Case counts only grow, so a live count only
ever gains post-switch rows. The thing that would break it is re-citing a band at
an older count, where the two stamp regimes coexist.

That is deliberately NOT graded, and the reason is a check that was written,
passed, and deleted for passing. It compared every row at a live count against a
`20260823-140000` boundary — and cleared the pre-switch rows, because a
post-switch UTC stamp of that day is `20260823-14xxxx` while the pre-switch local
rows at the same count are `20260823-21xxxx`, so the stale rows sort ABOVE the
boundary rather than below it. No `ts` threshold can separate the two regimes,
for the same reason the bug existed at all. A check that is green on exactly the
state it exists to refuse is worse than no check, so this is an assumption with
its limit named rather than a mechanism with a false description.

**And what a `ts` in this file means now.** Every timestamp §2 and §3 cite is a
UTC stamp of a post-switch row. The timestamps quoted in the diagnosis above —
`20260823-192533`, `20260823-041729` — are pre-switch rows and are naive local
Asia/Taipei, which is the whole point of quoting them; they are historical
evidence, not citations a reader should convert.

**And what is asserted rather than demonstrated.** No CI band is published, so §6
item 9 (environment) has exactly one environment to grade in this repo today —
`local` — and the CI half of the mechanism is asserted rather than demonstrated
here. `env_tag()` was exercised on all three branches from a laptop (`CI=1` → `ci`,
unset → `local`, `EVAL_ENV=staging` → `staging`), but that GitHub Actions sets
`CI`, that the workflow's `EVAL_ENV: ci` reaches the row, and that CI's
`invariant` row is therefore excluded from a `local` band are none of them graded
by anything (T-R74). The first CI run of this branch is the measurement, and this
ADR does not promise the answer — the last time this file did, it came due
immediately and the answer was no, twice over (Consequences, below).

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
