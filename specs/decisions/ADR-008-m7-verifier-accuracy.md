# ADR-008: What the M7 hand-labeled sample measures, and what it does not

Date: 2026-08-19
Status: accepted; Decision 3's removal of `MIN_EVIDENCE` was amended by
Decision 7 in the same PR (#10, merge with main), once main's
`slow-asset.html` supplied the case that removal said did not exist. Decision
3's own reasoning is left as written: it was correct on the evidence
available at the time, and the point of Decision 7 is that removal-on-no-
evidence and restoration-on-new-evidence are both the right call, made twice,
not a reversal to be quietly smoothed over.

## Context

The B-freeze and M6 both declared the same gap: "there is no hand-labeled
precision/recall sample" (`docs/analysis.md` §5, pre-M7). M7's job was to
close it — `docs/plans/active/task1-a-level-plan.md` A-exit criterion 2 —
without letting a ratio stand in for an accuracy claim the sample cannot
support.

## Decision 1 — the method, and why it is pinned like a baseline

24 runs were captured through `evals/labels/capture.py`: the same agent path
the eval adapter uses, against fixtures and two live sites, restricted to
runs whose trace actually reached the runtime `verify()` call (i.e.
`agent.py:491`, which passes **no** `expect` and **no** `state`). Raw evidence
(trace, extractions, answer) was frozen into `evals/labels/verifier-sample.jsonl`;
each record was then hand-labeled `correct`/`wrong` by reading the answer
against the task, independently of what the verifier said. The labeled file
was replayed offline through `verify(trace=..., extractions=..., answer=...)`
— the exact runtime call, not the eval adapter's ground-truth-augmented one —
and the resulting confusion matrix pinned into
`evals/adversarial/verifier-precision-recall.json`'s `expect`.

Verified from the tree: **15 fixture records (13 general + 2 constructed to
exercise the postcondition gate, `unverified-click-*`) and 9 live records (6
books.toscrape.com, 3 news.ycombinator.com)**. This corrects a fixture/live
split that circulated during planning (13 fixture / 11 live, 6+5 by live
domain) — the file itself, re-counted for this ADR, gives 15/9.

Moving that pinned matrix is a decision, exactly like `.eval-baseline.json`
(CLAUDE.md hard rule 1): it may only follow a recorded `verifier.py` change,
never a quiet edit to make the case pass. This ADR records the one move that
happened.

## Decision 2 — the `not_a_dump` threshold and its measured band

`DUMP_RATIO = 0.35` was set from `len(clean(value))/len(clean(page_text))`
measured across every extraction in the whole `fast` suite (**107
extractions**, not just the 24 labeled runs). This corrects a miscount that
stood here until M7.1 review: originally recorded as "66 extractions", a
number nobody could reproduce from a script (none was committed). Re-measured
for M7.1 by counting every extraction dict passed into every `verify()` call
made by a full `evals.run --suite fast` run against the tree as committed at
`bd5eef1` (73 cases; both the runtime-shaped call inside `run_task` and the
eval adapter's ground-truth-shaped audit call count separately, since
`not_a_dump` is evaluated fresh at each site) — **107**, confirmed
independently against the reviewer's own count of 107, not the "66" this
section previously claimed:

- Highest non-dump ratio: **0.1786** (`tc5-forms-submit-zh`, a 10-character
  reference-number readback against a 56-character evidence window).
- The two known dumps: **0.4541** (`probe5-books-travel-dump`) and **0.5231**
  (`probe5-shop-listing-dump`).

0.35 sits in the empty gap between 0.1786 and 0.4541, independently
re-measured for this ADR (`evals/golden` + `evals/adversarial`, every `fast`
extraction).

## Decision 3 — `MIN_EVIDENCE` removed: the scaffolding was the defect

Phase 2 added a second constant, `MIN_EVIDENCE = 20`, gating `not_a_dump` off
below that many characters of page text. It existed only because
`verifier-superseded-not-a-loophole` turned red: `eval_adapter._run_verifier_case`
called `verify(trace=sc["trace"], extractions=[{"value": "a", "page_text": "a"}], answer="a")`
— an inert placeholder whose sole job is giving the supersede probe something
to put in the `extractions` slot. Its dump ratio is 1.0 as a pure artifact of
being one character copied into a one-character window; the case tests
supersede resolution, not evidence content.

**Adding a production constant so the grader tolerates unrealistic test
scaffolding was backwards.** The fix is at the scaffolding: the placeholder
now reads `{"value": "ok", "page_text": "<a padded, realistic-length inert
sentence>"}` (ratio ≈0.009), so `grounded` still passes (the value is still a
substring of the page text) and `not_a_dump` is nowhere near its threshold.
`MIN_EVIDENCE` is deleted, along with its use in `verify()`.

The same scaffolding smell existed one branch down: the `anchors` probes in
the same function build `extractions` from `sc["page_texts"]` directly (`evals/adversarial/verifier-anchor-not-self-satisfied.json`),
measured at ratio 0.27–0.32 unpadded — inside today's non-dump ceiling
(0.1786) by a wide margin, but only ~0.03–0.08 below `DUMP_RATIO`. Padded the
same way, dropping the ratios to ≈0.02–0.07, without adding or removing any
anchor string (so which anchors are present or absent — the thing the case
tests — is unchanged).

**Red-first check performed on `verifier-anchor-not-self-satisfied` after
padding**: `identity_anchors` was temporarily forced to always pass (`check("identity_anchors", True, ...)`),
the case was re-run in isolation, and it went **red** — `passed: False`, both
`"Meridian Wall Clock"` scenarios reported as `should_pass: False` but
observed passing. The neutering was then reverted and the file diffed
identical to its pre-edit state. This confirms the padding did not
accidentally make the case pass for a reason other than `identity_anchors`.

**What removing `MIN_EVIDENCE` licenses, and what it does not.** The behavior
it guarded — a page whose entire evidence text is under ~20 characters, where
the dump ratio is mostly noise — is not fixed; it is now a declared limitation
(`docs/support-matrix.md`), because a false FAIL there is the safe direction
and **no case in this repo demonstrates the failure mode**. Speculative
guards for un-demonstrated inputs are exactly the kind of code this repo does
not carry. The `not_a_dump` computation still guards the one real edge case
(a page with literally zero evidence text) against `ZeroDivisionError`, which
is a crash guard, not a threshold.

**Matrix check.** Post-removal: `evals/adversarial/verifier-precision-recall.json`'s
pinned matrix (`tp=10, fp=10, fn=1, tn=3`) is unchanged — verified by
re-running `_run_verifier_case`'s adapter path and reading the computed matrix
directly, not just the pass/fail bit. Every real evidence window in the
labeled sample is ≥56 characters (`REF-6B5159`'s window in `tc5-forms-submit`),
well clear of the 20-character floor that was removed, so nothing in the
sample could have depended on it.

## Decision 4 — the headline is not precision, and why

Post-fix confusion matrix on the 24-record sample: **tp=10, fp=10, fn=1,
tn=3** → precision 0.500, recall 0.909. Pre-fix (before `not_a_dump` existed):
tp=10, fp=12, fn=1, tn=1 → precision 0.455, recall 0.909 (unchanged — the
check never touches a correct answer).

Precision as a single ratio is a function of this sample's mix, which is
**deliberately adversarial**: 12 of the 22 non-postcondition-gate records were
constructed specifically as traps (wrong field, wrong row, unsorted list,
unexecuted search/submit/near-miss entity, a listing dump). A sample with a
different correct:wrong ratio produces a different precision from the exact
same verifier. Publishing 0.500 without saying so invites reading it as "the
verifier is right half the time," which is not a claim this sample can
support.

The structural, sample-independent finding is: **excluding the two records
built to exercise the postcondition gate (`unverified-click-*`), the
pre-`not_a_dump` runtime verifier returned `PASS` on all 22 remaining
records — 10 correct answers and 12 wrong ones — with zero discrimination
between them.** Independently re-verified for this ADR by calling `verify()`
directly on the 22 records with `DUMP_RATIO` forced unreachable: 22/22 PASS.
Every runtime L1 check (`trace_nonempty`, `supersedes_resolve`,
`no_failed_postcondition`, `answer_nonempty`, `actions_verified`, `grounded`)
is mechanical — none of them asks whether the answer answers the question —
so by construction the pre-fix verifier could not distinguish a wrong,
well-formed answer from a right one. Re-running the same 22 records against
the current code (`not_a_dump` included) gives **20/22 PASS**: the two
`probe5-*-dump` records now correctly FAIL. That is the entire, specific gain
`not_a_dump` bought — it closes exactly the probe-#5 page-dump shape, nothing
more. It is a small, honest gain, not a general responsiveness check.

The eval suite has looked clean across six milestones because the adapter
calls `verify()` a **second** time with ground truth (`expect.answer`,
`expect.state` — L2), a layer no real user's run ever reaches. `identity_anchors`
is vacuous at the runtime call site for the same reason: `agent.py:491` passes
no `expect`, so the check only ever fires when the eval adapter supplies
`expect.anchors`. This was previously an inaccurate claim in `verifier.py`'s
own docstring (M6 phase 2 corrected it) — a defect the M6 measurement pass
found by measuring, not by reading.

The 10 surviving false positives and what they are, from `verifier-precision-recall`'s
computed `false_positive_ids`: `trap-near-miss-entity` (a "Pro" variant
answered for the base product), `trap-wrong-field`, `trap-wrong-cell-total`
(wrong table row), `trap-unsorted-cheapest` / `live-unsorted-cheapest`,
`trap-search-not-executed`, `trap-form-not-submitted`, and three more live
wrong-field shapes (`live-wrong-field-upc`, `live-wrong-field-submitter`,
`live-wrong-field-availability`) — **4 of the 10 on live sites.** None of
these are dumps; each is a short, focused, wrong answer. `not_a_dump` was
never meant to reach them — closing that gap needs ground truth (L2, absent
at runtime) or an evidence-only LLM check (L3, absent by design, per
`verifier.py`'s module docstring).

## Decision 5 — a 25th record: chunking evades `not_a_dump`, measured

Found by the final-phase cold review: `verify()` never receives the task
text, so N per-row extractions are structurally identical whether the task
asked for all N rows or for one of them. `not_a_dump` closes the
single-extraction dump shape only — it says nothing about the same dump split
across several extractions, each individually under `DUMP_RATIO`.

Per CLAUDE.md hard rule 2, this is measured, not just declared: a 25th record,
`chunked-dump-cheapest`, was captured with `evals/labels/capture.py`'s
machinery (same task and fixture as `probe5-shop-listing-dump` — "which
product is the cheapest, and what is its price?" on `shop.html` — but the
plan chunks the sorted catalogue into four separate
`{role: listitem, index: 0..3}` extractions instead of one whole-container
extraction), hand-labeled `wrong` (the answer is still all four products), and
appended to `evals/labels/verifier-sample.jsonl` without touching any of the
24 existing lines or their labels. Each extraction's own ratio is ~12% of its
evidence window, far under 0.35, so `not_a_dump` passes all four and the
runtime verifier returns `PASS`.

This corrects the counts in Decision 4, which were pinned before this record
existed: **25 records total (16 fixture, 9 live), 23 non-postcondition-gate,
13 of which are constructed traps** (12 from phase 1/2 + `chunked-dump-cheapest`).
Re-verified directly: pre-`not_a_dump` (`DUMP_RATIO` forced unreachable), all
23 non-postcondition-gate records PASS regardless of correctness (10 correct,
13 wrong); post-fix (current code), **21/23 PASS** — the two original
`probe5-*-dump` records correctly FAIL, `chunked-dump-cheapest` does not.

Matrix moves to `tp=10, fp=11, fn=1, tn=3` → **precision 0.4762, recall
0.9091** (unchanged — the new record is a new FP, not a TN/FP/FN change to
any existing record). Pinned in
`evals/adversarial/verifier-precision-recall.json`; declared as a limitation,
not chased, in `docs/support-matrix.md` ("chunking evades the check") — the
fix would need either the task text at the `verify()` call site (a scope
change to the verifier's own contract: it takes raw evidence, never the task)
or ground-truth L2, neither of which this milestone adds.

## Decision 6 — M7.1: the denominator was the stored window, not the page

Reviewer-reported, reproduced before any fix landed (case
`verifier-dump-ratio-anchor-flip`, pure-code, no browser): `not_a_dump`
divided `len(clean(value))` by `len(clean(page_text))`, but `page_text` is
`agent.evidence_window()`'s output — a *storage artifact* capped at
`PAGE_TEXT_KEEP` (2000 chars) and **doubled** (agent.py:171-173) when a
distant `anchor` forces a second window to be appended. Two consequences,
both watched red before the fix:

- On any page longer than `PAGE_TEXT_KEEP` the check degenerates into an
  absolute cap: a value over ~700 clean characters reads as "a dump"
  regardless of true page size.
- The SAME value on the SAME page flips verdict depending only on whether the
  plan carried a distant anchor. Reproduced directly: a 776-char value on a
  4,388-char page — plain window 2000 chars, ratio 0.388, `not_a_dump` FAILs;
  the identical value/page with a distant anchor — window 3615 chars, ratio
  0.2147, `not_a_dump` PASSes. The true page fraction is 776/4388 ≈ 0.177,
  well clear of `DUMP_RATIO` either way — the pre-fix FAIL was itself wrong,
  not just inconsistent.

**The fix**: `agent.py` now records `body_len` (`len(body)`, already in hand
at extraction time) alongside `value`/`page_text` on every extraction.
`verify()`'s `not_a_dump` prefers `body_len` as its denominator, falling back
to `len(clean(page_text))` — the old formula, unchanged — when `body_len` is
absent. That fallback is deliberate, not a gap: the 25 frozen records in
`evals/labels/verifier-sample.jsonl` predate this field and must keep
replaying exactly as before.

**Re-measured band** (`evals.run --suite fast`, 47 browser E2E-shaped cases,
35 real extractions, current tree):

- The two calibration points that live entirely in the `fast` suite are both
  unsaturated (their window is the whole real page — no truncation), so
  `body_len` and the old `len(clean(page_text))` are nearly identical, and
  both move only in the third decimal place: `tc5-forms-submit-zh` (window 56
  clean chars) 0.1786 → 0.1695; `verifier-catches-listing-dump`'s dump (window
  195 clean chars) 0.5231 → 0.5204. Neither crosses `DUMP_RATIO` in either
  direction — **unchanged** in the sense that matters (verdict), moved only in
  the sense of raw-vs-cleaned-length bookkeeping.
- The third named calibration point, `probe5-books-travel-dump` (window 1339
  clean chars, live-only, ratio 0.4541), lives only in the frozen sample and
  therefore has no `body_len` — its ratio is **exactly** unchanged (byte-for-
  byte the same formula, not just numerically close).
- Two real, previously-saturated fixture extractions now demonstrate the fix
  directly: `near-excludes-its-own-anchor` and
  `evidence-window-keeps-the-anchor`, both against `shop-lamp-spec.html`
  (`body_len=2455`), gave old ratios of 0.0080 (plain window, 2000 chars) and
  0.0052 (anchored window, 3062 chars) — different from each other purely
  because of window storage, the exact defect this fixes. Both now compute
  the identical `body_len`-denominated ratio, 0.0065. No verdict in the
  current suite flips either way; the flip case above is what pins the fix.

**Confusion matrix**: `evals/adversarial/verifier-precision-recall.json`'s
pinned matrix (`tp=10, fp=11, fn=1, tn=3`, precision 0.4762, recall 0.9091)
is **unchanged**, re-verified by re-running `_run_verifier_labels_case`
against the current code. Every one of the 25 frozen records lacks
`body_len` by construction, so all 28 of their extractions take the
unmodified fallback.

**Honest disclosure**: of the 28 extractions across the 25 frozen records,
**6 are saturated (window length ≥ `PAGE_TEXT_KEEP`, max 3,560 characters)**
— `near-excludes-its-own-anchor`, `live-books-detail-upc` (3,560),
`live-books-travel-price`, `live-wrong-field-upc`, `live-unsorted-cheapest`,
`live-wrong-field-availability`. Those six extractions' `not_a_dump` ratios
were, and remain, judged against a truncated-or-doubled storage window rather
than the page the value was actually read from — they are not page-fractions.
None of the six cross `DUMP_RATIO` in either direction, so this does not move
the pinned matrix, but it is a real gap in what that matrix's ratios mean,
not a hypothetical one, and it cannot be closed without re-capturing (and
re-hand-labeling) the sample. Declared in full in `docs/support-matrix.md`
(D4).

**Count correction (Decision 2)**: "66 extractions" in Decision 2 could not
be reproduced from any committed script and was replaced with **107** after
independently re-measuring — every extraction dict passed into every
`verify()` call across a full `--suite fast` run (73 cases as committed at
`bd5eef1`), matching an independent recount by the reviewer.

## Decision 7 — M7.2: the sparse-page false FAIL, removed then restored

Decision 3 removed `MIN_EVIDENCE` (a 20-character floor below which
`not_a_dump` was skipped) because the only thing it guarded — a page whose
entire evidence text is short enough that the ratio is noise — had **no case
demonstrating it was ever wrong**: "no fixture in the repo is sparse enough to
demonstrate it" (Decision 3, restated as D3 in `docs/support-matrix.md`). That
reasoning was correct on the evidence available at the time. A guard with no
case behind it is speculative, and speculative guards are exactly what this
repo does not carry.

The evidence arrived a few days later, inside the PR that merged this
milestone with main's navigation work. Main added `src/browser/fixtures/slow-asset.html`
for its own navigation-timeout cases (`nav-load-event-never-fires`,
`nav-action-load-event-never-fires`, ADR-007) — a page with **37 clean
characters of body text**. Its correct answer, the page's `<h1>`, is 23 clean
characters: **62% of the page**. `not_a_dump` FAILed it, taking both of
main's cases down with it (they extract the same heading), and a third case
written for exactly this shape (`verifier-sparse-page-not-a-dump`, this
milestone). Watched red on the merged tree before any fix: `checks.not_a_dump:
false`, `reason: "value reproduces most of its own evidence window: ['The
monk and the dancer']"`, on all three cases identically.

**The declaration was falsified inside the same PR that made it**, which is
the sharpest version of the thing Decision 3 warned about happening
eventually. The fix restores a page-size floor — `MIN_PAGE_CHARS = 100` in
`verifier.py`, functionally `MIN_EVIDENCE`'s successor, not a re-add of the
same constant (it gates the real page size / `body_len`, not the stored
window, since Decision 6 changed what the denominator means) — below which
`not_a_dump` does not apply at all. 100 sits between the sparse fixture (37
page chars, 39 by `body_len`) and the smallest confirmed real dump,
`probe5-shop-listing-dump` (195 chars) — roughly their geometric mean, ~85.

**What "no other extraction sits between them" actually means, checked
directly rather than assumed.** Every `verify()` call the `fast` suite makes
was instrumented (115 extraction observations, no source file touched) to
read off each one's `not_a_dump` denominator and ratio. The claim is **not**
that no other page falls in the 37–195 character range — plenty do: forms.html's
reference-number readback (denominator 59–68 chars), several shop-fixture
price and SKU extractions (61–194 chars) — the claim that holds is narrower
and is what the floor actually depends on: of every extraction below 100
characters, **only the sparse-fixture case has a ratio anywhere near
`DUMP_RATIO`** (0.59; the next highest is 0.17, the same ceiling Decision 2
measured for real non-dump extractions generally), and no confirmed dump in
the suite is smaller than 195 characters. The floor is not resting in an
empty gap of page sizes; it is resting in an empty gap of *ratios that would
flip* if it moved. Every one of the 25 frozen `verifier-sample.jsonl` records
was checked the same way: only `tc5-forms-submit`'s window (65 chars) is
below the new floor, its ratio (0.15) was never close to `DUMP_RATIO`, and
the pinned confusion matrix (`tp=10, fp=11, fn=1, tn=3`) does not move.

Re-run after the fix: `nav-load-event-never-fires`, `nav-action-load-event-never-fires`,
and `verifier-sparse-page-not-a-dump` all green. Full `fast` suite 77/77,
`invariant` 20/20.

## What stays deliberately not fixed

- **Semantic responsiveness.** No mechanism added here, or existing, asks
  whether an answer addresses the task. `not_a_dump` catches one shape (the
  value reproduces most of its evidence window); a short, plausible, wrong
  answer sails through untouched. Only ground-truth L2 catches it, and a live
  run has none.
- **Chunking evades `not_a_dump` (Decision 5).** `verify()` never receives the
  task text, so the same page dump split across several per-row extractions
  passes every one of them. Measured, not just declared:
  `chunked-dump-cheapest` in the labeled sample.
- **The two anchor holes named in `verifier.py`'s docstring** (a near-miss
  entity whose name contains the target's; every candidate entity present on
  an aggregate page) — unaffected by this milestone, still open, still caught
  only by ground truth.
- **The sample's own bias.** n=25 is constructed (not sampled uniformly from
  production traffic — there is none), stratified toward traps by design, and
  drawn only from runs that reached `verify()` — a run that died earlier in
  the executor (empty extraction, ambiguous locate, absent anchor) never gets
  a verdict and is correctly excluded from this population, but that also
  means the sample says nothing about how often real runs reach `verify()` at
  all.
- **The threshold is chrome-sensitive and thinly calibrated.** The ratio is
  computed against the size of the real page the value was read from
  (`body_len`, since Decision 6), so the same dump on a page with more
  surrounding boilerplate dilutes toward and under 0.35 exactly as before the
  fix — the fix changed what the denominator measures, not that dilution
  exists. Calibrated on exactly two positive examples (0.4541, 0.5231) — only
  ~0.10 of headroom above 0.35. No fixture with heavier chrome exists to
  demonstrate the dilution (`docs/support-matrix.md`).
- **A sparse page can false-FAIL `not_a_dump` below `MIN_PAGE_CHARS` — closed,
  Decision 7.** Was declared here as unfixed because no fixture was sparse
  enough to demonstrate it; main's `slow-asset.html` supplied one inside this
  same PR, and the floor is restored with a case (`verifier-sparse-page-not-a-dump`)
  behind it. What is **not** closed: `MIN_PAGE_CHARS` is still exactly two
  calibration points (37 and 195), same thinness as `DUMP_RATIO` itself
  (Decision 2) — a fixture sparser than 37 but a genuine dump, or a real dump
  smaller than 195, would each need their own case before this floor could be
  trusted to move.
- **A record with no `body_len` still saturates (Decision 6, D4).** Before
  Decision 6 this was universal; after it, only records captured before
  `body_len` existed can still exhibit it — permanently, since they cannot be
  re-captured without breaking the frozen replay. 6 of the labeled sample's
  28 extractions are saturated (window ≥ `PAGE_TEXT_KEEP`); none happen to
  cross `DUMP_RATIO`, but their ratios are not page-fractions.

## Consequences

- `src/browser/agent.py`: every extraction record now carries `body_len`
  (`len(body)` at extraction time), alongside `value` and `page_text`
  (Decision 6).
- `src/browser/verifier.py`: `not_a_dump`'s denominator prefers `body_len`,
  falling back to `len(clean(page_text))` for records that predate it
  (Decision 6). `MIN_EVIDENCE` removed at Decision 3, then restored as
  `MIN_PAGE_CHARS = 100` at Decision 7 once main's `slow-asset.html` gave the
  removed guard a real case; below it, `not_a_dump` does not apply. The `pt_len
  and ...` check still separately guards the zero-length case (crash
  avoidance, distinct from the floor).
- `specs/001-browser-contract.md`: `evidence.extractions` now documents
  `body_len`.
- `src/browser/eval_adapter.py`: both scaffolding sites in
  `_run_verifier_case` (the `superseded` placeholder and the `anchors`
  padding) now use realistic-length inert evidence, with the reasoning
  written inline so a future edit does not silently reintroduce a threshold
  that only exists to tolerate scaffolding.
- `docs/analysis.md` §5 and `docs/support-matrix.md` carry the measured
  numbers, led by the 23/23 → 21/23 structural finding, not by the 0.476
  precision figure.
- `evals/labels/verifier-sample.jsonl`: 25 records (Decision 5 adds
  `chunked-dump-cheapest`); `evals/adversarial/verifier-precision-recall.json`
  pins `tp=10, fp=11, fn=1, tn=3`.
- `docs/plans/active/task1-a-level-plan.md` A-exit criterion 2 is met: ≥20
  hand-labeled runs (25), precision/recall reported, responsiveness gap
  partially closed (dump shape, with its chunking boundary now measured) and
  the remainder explicitly declared.
- `evals/adversarial/verifier-sparse-page-not-a-dump.json` (Decision 7): pins
  a correct extraction from `slow-asset.html` as PASS, red before
  `MIN_PAGE_CHARS` existed.
- `docs/support-matrix.md` D3 moves from `unreliable`, declared to `supported`,
  closed (Decision 7) — kept as a row, not deleted, per this document's own
  house style for closed limitations.
