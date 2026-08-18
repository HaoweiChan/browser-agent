# 010 — M7: verifier accuracy, and the audit that changed the headline

**Date**: 2026-08-19 · **Milestone**: M7 (A-phase) · **Outcome**: 24
hand-labeled runs replayed offline through the runtime `verify()` call;
`not_a_dump` (L1) added and its threshold measured against the whole `fast`
suite; matrix pinned at tp=10/fp=10/fn=1/tn=3 (precision 0.500, recall
0.909); a scaffolding defect masquerading as a production constant found and
removed; 72/72 fast, 18/18 invariant, $0.00. **Updated in M7's final phase**
(cold review + spec-drift audit): a real crash bug in `evidence_window` fixed,
a 25th record added to demonstrate that `not_a_dump` is evadable by chunking
a dump across several extractions — matrix moves to tp=10/fp=11/fn=1/tn=3
(precision 0.476, recall 0.909); 73/73 fast, 19/19 invariant, $0.00. See
`specs/decisions/ADR-007-m7-verifier-accuracy.md` Decision 5.

## Context

This milestone was planned and audited by an orchestrating model and built by
delegated Sonnet agents across three phases, not written end to end by one
session. Phase 1 captured and hand-labeled the 24-record sample and measured
the pre-fix confusion matrix. Phase 2 implemented `not_a_dump` and its
`DUMP_RATIO` threshold — and, to make one red case pass, added a second
constant, `MIN_EVIDENCE`, without diagnosing why the case had gone red. Phase
3 (this record) is an audit-then-write pass: correct phase 2 first, then
write up the milestone honestly, including the correction.

## The prompt (verbatim, condensed)

> You are doing PHASE 3 of milestone M7... Phase 2 added TWO constants:
> `DUMP_RATIO = 0.35` (correct, keep it) and `MIN_EVIDENCE = 20` (remove it —
> see why)... Adding a production constant so the grader tolerates
> unrealistic test scaffolding is backwards: the scaffolding is the defect...
> The headline is NOT precision... Precision as a ratio is a function of a
> deliberately adversarial, constructed sample mix and MUST be published
> saying so — it is a floor reading, not a general accuracy claim... No
> number in any document may be one you did not verify from the tree.

The orchestrator did not just assign the write-up; it pre-diagnosed the
`MIN_EVIDENCE` defect and specified the corrected headline before phase 3
touched a file. Both of those calls are the audit's, not this session's own
discovery — worth recording precisely, because it is the clearest evidence in
this milestone that the review step is not decorative.

## The resulting decision

- **`MIN_EVIDENCE` deleted.** It existed only because
  `_run_verifier_case`'s `superseded` probe passed
  `extractions=[{"value": "a", "page_text": "a"}]` — a placeholder with a dump
  ratio of 1.0 purely because it is one character copied into a
  one-character window. The fix is at the scaffolding: realistic-length inert
  padding, value still a substring of page_text (`grounded` unaffected),
  ratio ≈0.009. The adjacent `anchors` probe was padded the same way after
  measuring its unpadded ratio at 0.27–0.32 — inside today's non-dump ceiling
  but uncomfortably close to `DUMP_RATIO=0.35`.
- **Red-first check kept, not skipped.** After padding, `identity_anchors`
  was temporarily forced to always pass and `verifier-anchor-not-self-satisfied`
  was re-run in isolation: it went red (`passed: False`, both `"Meridian Wall
  Clock"` scenarios reported passing when they should not). Reverted, file
  diffed identical. This is the check the phase-2 fix skipped — going straight
  to "the case is green" without first confirming it *could* go red for the
  right reason is exactly how a masking constant like `MIN_EVIDENCE` gets
  written in the first place.
- **The write-up leads with the structural finding, not the ratio.**
  Excluding the two postcondition-gate probes, the pre-fix runtime verifier
  passed 22 of 22 records regardless of correctness (10 right, 12 wrong) —
  independently re-verified for this record by forcing `DUMP_RATIO`
  unreachable and re-running the 22 records. `not_a_dump` moves that to
  20/22. Precision (0.500) is reported, but as a floor reading of a
  deliberately adversarial sample, with the 22→20 finding stated first.

Full method, measured threshold band, and the deliberately-unfixed list:
`specs/decisions/ADR-007-m7-verifier-accuracy.md`.

## AI recommendation: accepted / rejected / modified

Accepted, with one correction found independently in phase 3 and worth
recording because it is exactly the kind of number the instructions warned
against publishing unverified: the task's own framing described the sample as
"13 fixture + 11 live (6 books.toscrape.com, 5 news.ycombinator.com)".
Re-counting `evals/labels/verifier-sample.jsonl` directly gives **15 fixture
(13 general + 2 built for the postcondition gate) and 9 live (6
books.toscrape.com, 3 news.ycombinator.com)** — both totals sum to 24, but the
fixture/live split and the live domain split were wrong in the framing that
was handed down. Every document in this milestone uses the re-counted,
tree-verified numbers instead.

## Assumption → Eval contradiction → Correction

- Assumed (phase 2): a case that goes red after adding a new grader check
  needs a new grader guard.
  Eval said: the guard (`MIN_EVIDENCE`) had no case demonstrating the
  behavior it protected — it was invented to pass scaffolding, not to guard a
  real input. `verifier-superseded-not-a-loophole`'s placeholder extraction
  had a dump ratio of exactly 1.0 as an artifact of being one character
  copied into itself.
  Corrected: the scaffolding, not the grader. Both scaffolding sites in
  `_run_verifier_case` now use realistic-length inert padding;
  `MIN_EVIDENCE` is deleted; the fast/invariant matrix is unchanged
  (tp=10/fp=10/fn=1/tn=3, re-verified by reading the computed matrix, not
  just the pass bit).

- Assumed (the framing handed to phase 3): "13 fixture + 11 live (6 + 5)"
  describes the sample.
  Eval said: `evals/labels/verifier-sample.jsonl`, re-counted directly, is 15
  fixture (13 + 2 postcondition-gate) and 9 live (6 books.toscrape.com, 3
  news.ycombinator.com) — 24 total either way, but the split was wrong.
  Corrected: every number published in `docs/analysis.md`,
  `docs/support-matrix.md`, `tasks/TODO.md`, and ADR-007 uses the re-counted
  split, not the one supplied.

- Assumed: reporting precision (0.500) and recall (0.909) is the accuracy
  measurement M7 owed.
  Eval said: 12 of the 22 non-postcondition-gate records are constructed
  traps; a different correct:wrong ratio in the sample produces a different
  precision from the identical verifier, so the ratio alone measures the
  sample as much as the code. The structural, sample-independent finding —
  every runtime L1 check is mechanical, so the pre-fix verifier passed all 22
  non-postcondition records regardless of correctness — does not move with
  the sample mix. Corrected: `docs/analysis.md` §5 and this record lead with
  the 22/22 → 20/22 finding; the precision figure is reported second, with
  the adversarial-mix caveat attached every place it appears.

- Assumed (this record, at the time it was written): the 24-record sample and
  its tp=10/fp=10/fn=1/tn=3 matrix were the final word.
  Eval said (M7's final phase, cold review): `verify()` never receives the
  task text, so `not_a_dump` — judged per extraction — cannot tell "list every
  product" from "which is cheapest" when a dump is chunked into several
  per-row extractions instead of one whole-container extraction. Demonstrated,
  not just argued: a 25th record, `chunked-dump-cheapest`, same task and
  fixture as `probe5-shop-listing-dump`, chunked plan, still `PASS`.
  Corrected: matrix moves to tp=10/fp=11/fn=1/tn=3 (precision 0.476, recall
  0.909 unchanged); the structural finding becomes 23/23 → 21/23 (13 traps of
  23 non-postcondition-gate records, not 12 of 22). Every document this
  milestone touches carries the updated counts; see
  `specs/decisions/ADR-007-m7-verifier-accuracy.md` Decision 5.
