# ADR-012: A history line every run, a full report only when it earns its keep

Status: accepted · 2026-08-21

**Ruling**: `evals/run.py` appends one line to `evals/report/history.jsonl` on every run, unconditionally; a full per-case report (`evals/report/<ts>-<suite>.json`) is written only on `--report`, `--suite all`, or a red run. A report is a **report of record** exactly when something outside `evals/report/` cites its filename as evidence — that set is now enforced, not just conventional.
**Because**: 159 full reports (4.8MB) had accumulated on `main`, one per routine gate tick, when only ~68 were ever pointed at as evidence; every PR diff was paying full per-case JSON for runs nobody was going to read again, while the one thing worth keeping forever — the wall-clock/score time series — wasn't being kept as its own artifact at all.
**Enforced by**: `evals/adversarial/report-citations-resolve.json` (citations resolve) + `evals/run.py`'s write policy (docstring) + `.githooks/pre-commit` (no longer passes `--no-report`, so a red commit attempt leaves an inspectable report; a green one leaves only the history line)

---

## Context

`evals/report/` is committed to git (project layout, `CLAUDE.md`). Every
`evals.run` invocation — pre-commit, CI, the PostToolUse hook, an ad hoc
manual run — used to write a full `{suite, score, totals, metrics, results}`
dump. Pre-commit and the PostToolUse hook already passed `--no-report` (so
routine per-edit ticks wrote nothing), but every other invocation, including
plain `python3 -m evals.run --suite fast` run by hand while iterating, wrote
one. Nothing pruned them, so `main` carried 159 reports / 4.8MB, most of them
a green tick with no downstream reader — 124 turned out to be cited nowhere.

The 13 that survive citation (plus 25 ablation/soak/live instrument
artifacts, non-prunable by policy regardless of citation — see Consequences)
are pointed at from `specs/decisions/ADR-*.md`, `docs/analysis.md`,
`docs/support-matrix.md`, `tasks/TODO.md`, and one eval case's `provenance`
field. That's the real signal: a report earns permanence by being cited as
evidence for a claim, not by having been generated.

## Decision 1 — the history line is unconditional and cheap

Every run appends one JSONL line to `evals/report/history.jsonl`, schema:

```
{"ts", "suite", "sha", "dirty", "passed", "total", "score", "wall_s",
 "cost_usd", "report"}
```

plus this fork's own extras when the adapters produced them (`p95_s`,
`recovery`, `mutation` — ratios, matching the console printout). `sha`/`dirty`
come from `git rev-parse --short HEAD` / `git status --porcelain`, with one
exclusion: the dirty check excludes `evals/report/history.jsonl` itself,
because that file is what the run just wrote — without the exclusion the
repo would read "dirty" forever after the first run, never distinguishing a
real uncommitted code change from the tool's own bookkeeping. Verified: two
back-to-back runs on an otherwise-clean tree both record `dirty: false`.

`report` is the full report's basename when one was written, else `null` —
so the time series and the evidence pack cross-reference without a second
lookup.

## Decision 2 — the full report is conditional

Written when `--report` is passed, or `--suite all`, or the run is **red**
(any case failed, or score < baseline for a suite the baseline tracks).
Routine green ticks — pre-commit, CI's `invariant`+`fast` steps, the
PostToolUse hook — leave no full report. `--no-report` still forces it off
unconditionally, for a caller that wants the console printout with zero
writes.

Consequence for this PR's own gate run: it is green, so it produces a
`history.jsonl` line and **no new full report** — confirmed in the PR body,
not asserted here.

`.githooks/pre-commit` dropped `--no-report`: a red commit attempt (which it
already blocks) now leaves a full report behind for inspection, and a green
one costs nothing extra beyond the history line, which lands in the working
tree **unstaged** — same as any other cron-shaped writer in this house
style, it rides into the next commit rather than the one that triggered it.
The PostToolUse hook (`.claude/hooks/post-edit-invariant.sh`) keeps
`--no-report`: a per-Edit invariant tick has no business writing anything to
disk beyond feeding pass/fail back to the agent.

## Decision 3 — backfill before prune, so the prune is lossless

Before deleting anything, every one of the 158 existing full reports (cited
and uncited alike) was backfilled into `history.jsonl` as one line: `ts` from
the filename, `sha`/`dirty` as `null`/`false` (no report ever recorded git
state before this ADR), `passed`/`total`/`score`/`wall_s`/`cost_usd` from
each report's own summary fields (`ablation`'s per-task `correct` and
`soak`'s top-level `attempted`/`correct` needed their own small branch —
different shapes, same runner in spirit), `report` = the basename if the
file survives the prune, else `null`. Sorted by `ts`. The wall-clock/score
trend this ADR exists to preserve is therefore intact for all 158 runs,
whether or not the JSON dump behind any one of them survives.

## Decision 4 — the prune

CITED set: every `evals/report/<ts>-<suite>.json` matched by
`evals/report/(\d{8}-\d{6}-[a-z]+\.json)` in `docs/`, `specs/`, `tasks/`,
`README.md`, `src/`, `evals/golden/`, `evals/adversarial/`, `.github/`,
`prompts/` — 13 files. `graphify-out/manifest.json` indexes every report in
the repo and was deliberately **excluded** from this scope: that's a
generated concordance, not a document choosing to point at a report as
evidence, and including it would have made every report "cited" by
construction.

Non-prunable by kind regardless of citation, by policy:
`*-ablation.json`, `*-soak.json`, `*-live.json`, and the ledger
`pr-loop-ledger.jsonl` — 25 files, all instrument/record artifacts governed
by their own ADRs (ADR-006 live breadth, ADR-010 ablation), not routine gate
ticks.

Prune candidates = `*-fast.json` / `*-invariant.json` / `*-all.json` AND
uncited: **124 of 133** such files. `git rm`'d.

**Before**: 158 full reports, 4.85MB. **After**: 34 full reports (25
non-prunable-by-kind + 9 additionally cited fast/invariant), 0.63MB, plus the
new `history.jsonl` (158 backfilled lines + everything from here forward,
~27KB) and the unchanged ledger.

**Recovery**: the pre-prune commit is `c4eb55a` (tip of `main` before this
branch). `git show c4eb55a:evals/report/<name>` recovers any pruned file
verbatim.

## Decision 5 — the citations must keep resolving

New invariant case `report-citations-resolve`
(`evals/adversarial/report-citations-resolve.json`,
`_run_report_citations_case` in `src/browser/eval_adapter.py`) scans the same
scope as Decision 4 and fails if any cited report is missing from
`evals/report/`. Watched red first: renamed the ADR-002-cited
`20260816-002725-fast.json` on disk → `missing_reports:
['20260816-002725-fast.json']`; renamed back → green. Same declared-not-graded
boundary as `support-matrix-cites-real-cases`: it proves the evidence still
*exists*, not that the claim next to the citation is still true.

## Consequences

- A future prune must re-run this same script/scope rather than trusting the
  file list by eye — the citation set moves every time a doc is edited, and
  `report-citations-resolve` is the safety net if it's forgotten.
- `graphify-out/` will keep indexing every surviving report as it always did;
  it is not a citation source and is not swept by anything here.
- `ablation`/`soak`/`live` reports still accumulate uncapped — this ADR does
  not cap them, only fast/invariant/all. A future ADR owns that if it becomes
  a real size problem.
