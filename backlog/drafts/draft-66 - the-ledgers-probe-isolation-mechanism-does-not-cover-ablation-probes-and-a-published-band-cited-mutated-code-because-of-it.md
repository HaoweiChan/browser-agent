---
id: DRAFT-66
title: >-
  the ledger's probe-isolation mechanism does not cover ablation probes, and a
  published band cited mutated code because of it
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M38-5
  - 'PR #42'
  - >-
    R2/R3's acceptance and the coordinator's round-1 disposition. Re-checked
    against `origin/main` after T-R44 merged (2026-08-24): **both halves are
    still open**
  - and what T-R44 closed is the neighbouring coupling
  - not this.
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
this repo already ruled that a probe is not a run and must not reach the committed ledger. `wall-clock-probe-history-isolated` is that ruling in force: `_main_exit_code` (src/browser/eval_adapter.py) redirects `R.HISTORY` and `R.REPORT_DIR` to a temp path because without it the probe injected fabricated rows — 52 of 241 committed lines were probe artifacts at PR #20 R18, deleted by hand as part of that repair rather than caught by a check. **The mechanism covers exactly one probe class: the one that calls `evals.run.main()` in process.** An ablation probe — the whole suite run with one guard conjunct removed, which is how R2/R3 require a guard to be pinned — is a subprocess gate run, appends rows like any other, and is invisible to that isolation. Nine such rows were produced and hand-deleted across three review rounds (the table in ADR-019 §2 lists every one); twice the probe row was the ledger's maximum and forced the published band onto code that never existed as a commit. **What T-R44 changed, and what it did not.** `env` per row and a UTC `ts` close `T-M32-13`: a band is now graded against its own environment, so CI's rows cannot redden a local band and a dirty citation is no longer a two-commit price. Neither reaches this. Checked on the merged tree: `evals/run.py` has no history opt-out of any kind (`--no-history`, `EVAL_HISTORY`, a probe flag — none exist), so an ablation sweep still appends indistinguishable rows; and `_band_wrong` reads `env`, `suite`, `total`, `wall_s`, `dirty` and `ts` and never reads `sha`, so a row from a tree that is not an ancestor of HEAD still counts toward the maximum the band must match.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 extend the isolation `wall-clock-probe-history-isolated` already pins rather than inventing a second mechanism — an opt-out the probe passes (`--no-history`, or `EVAL_HISTORY` pointed at a temp path) so a deliberately broken tree cannot append to the committed time series, plus a case in that same file's shape: run the suite through the opt-out, assert the committed ledger did not grow. Watched red against today's behaviour, where it does. Second half, unchanged by T-R44 and worth doing with it: `_band_wrong` should refuse a row whose `sha` is not an ancestor of HEAD — a different hole (a row from a branch that never merged) in the same class, and the one that makes a band a claim about a tree that exists.
<!-- AC:END -->
