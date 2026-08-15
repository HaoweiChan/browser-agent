---
name: finish-task
description: Ship checklist for closing out a milestone or feature — run before declaring any milestone done or preparing a submission. Ensures suites, drift audit, support matrix, prompt curation, and the deployed URL are all verified.
---

# Finish-task checklist

Run every item; report each as done / failed / skipped-with-reason. Never
report the milestone complete with a silently skipped item.

1. **Suites**: `python3 -m evals.run --suite invariant` (must be 100%) and
   `--suite fast` (must meet baseline). If the milestone touched live-site
   behavior, also a manual `--suite full` run; commit its report.
2. **New failures became cases**: every failure seen during the milestone has
   an adversarial case that was watched red first (repo rule 2).
3. **Drift audit**: run the `spec-drift` subagent; resolve or ticket every
   finding above stale-doc severity.
4. **Cold review**: run `cold-reviewer` on changed pipeline stages; its
   findings become adversarial cases before the milestone closes.
5. **Support matrix**: regenerate eval-backed suggestions; re-declare statuses
   with reasons (`docs/support-matrix.md` + frontend JSON stay in sync).
6. **Deployed URL**: submit one real task via the public frontend; watch
   progress; open one failing run's trace. If the deploy is broken, the
   milestone is not done.
7. **Prompts curated**: 2–3 collaboration episodes from this milestone into
   `prompts/00N-*.md` — corrected-plan episodes are worth the most; include
   the correction chain.
8. **TODO.md**: milestone marked, next milestone's validation line still
   accurate; hour-guard tally updated (freeze at 20–24h total on Task 1).
9. **Commit through the gate** — no `--no-verify` without an in-message reason.
