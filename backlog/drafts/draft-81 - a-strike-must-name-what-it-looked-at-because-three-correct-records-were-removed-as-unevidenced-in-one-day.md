---
id: DRAFT-81
title: >-
  a strike must name what it looked at, because three correct records were
  removed as unevidenced in one day
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R76
  - 'PR #41 R1'
  - plus two instances found cross-session on `task/M32`
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Three times in one day a correct record was struck or contradicted because whoever checked could not see its evidence — never because the evidence was absent. In each case the disproof was one command away, and in each case the stricter-sounding move (remove the unevidenced claim) was the one that destroyed information. That is what makes it worth a decision rather than three review artifacts: **the failure disguises itself as rigour.** 1. A `ts`-ordering diagnosis, correct for CI run `32637648447` (sha `11545a1`, the `20260823-192533` / `20260823-115044` pair), was generalised to run `32626835735` (sha `434a98d`), where the mechanism cannot exist: `git show 434a98d:src/browser/eval_adapter.py | grep -c cited_a_dirty_run` is 0. T-R44's original Repro was struck as wrong; it was right for its own run. Disproof cost: one `git show`. 2. The over-scoping that caused (1): "items 3/4 hold today" with margin to 17.39s was true of one run and false as stated. Item 3 fired at **16.02s** on the other — published 12.92s derives 15, CI's 16.02s derives 20. Disproof cost: one `gh run view` of a run nobody had opened. 3. README strikes an earlier CI band "because nothing named the run it came from". `ADR-013:162-164` names it — commit `09b9740`, run `32455716866`, three re-runs, all four numbers reproducing verbatim. Disproof cost: reading two lines further down a file already open.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an ADR recording the ruling with these three instances as its evidence, and a graded consequence if one can be found that does not itself cost more than it saves — the honest fallback is a stated convention with the instances as its record. Not gateable as prose alone; the ADR must say which half it is. **Try the form, not the claim, before falling back.** PR #40 learned this shape at the cost of a round: its `docs-numbers-are-derived` sweep failed while it graded a *number* — it reddened on true sentences, flagging `# ~71s on an M-series laptop` as publishing an unenforced ceiling — and worked once it graded a **form**: a runnable `--suite X` command whose own trailing comment publishes a ceiling, which can only mean the live one, so it has no true-sentence false positives and widened to the whole tree without one.
<!-- AC:END -->
