---
id: DRAFT-26
title: >-
  a check that never ran and a check that has not finished read the same, and
  neither reads as failure
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-15-D3
  - T-M39-15
  - >-
    PR #69 round 1 — the forge-side half of the same silent-failure family.
    Separate from D2 deliberately: D2 is about state invisible **between
    worktrees**
  - D3 about state invisible **between GitHub and every tree** — different layer
  - different mechanism
  - different fix
  - and folding them makes both vaguer.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
this repo's gate is enforced at 100%, but its CI is not mandatory-to-RUN. A `CONFLICTING` PR runs no checks at all, and an empty check list is not a failing one — so "not run", "not finished" and "nothing to report" are the same pixel. Three things this produced on 2026-08-28, each verified against the API and the merged tree rather than relayed: 1. PR #66 sat `CONFLICTING`/`DIRTY` with **zero** checks (`gh pr view 66 --json statusCheckRollup` -> empty array, `mergeStateStatus` `DIRTY`). Its duplicate ADR-033 and a wall-clock breach were both invisible because nothing ran to find either; the duplicate was caught by a coordinator reading branches from outside the repo. 2. PR #71 was opened conflicting with no CI, rebased, then merged carrying seven `evals/report/*-invariant.json` files, all at `total: 82`. One — `evals/report/20260827-205100-invariant.json` — is on `main` recording 43/82, wall **1.17s**, `cost_usd: null`, its 39 failures `ModuleNotFoundError`, where the other six ran ~16s. An import-failure artifact from a depsless interpreter, not a gate result, merged without the gate ever executing on the tree that carried it. 3. PR #71's merge flipped PRs #66–#70 to `CONFLICTING` at once — five branches lost their gate evidence in one move, each still displaying a green check from its PREVIOUS head. **A stale green is worse than no check**: it reads as verified. **This block now owns the whole class, both directions.** Rows at an abandoned case count outliving the tree that made them, and rows recording a run that never happened, are one file's two failure modes. The first was `T-M39-15-D1`, closed unbuilt on 2026-08-28 when ADR-035 Decision 7 moved the committed local `fast` ceiling to 110 and removed the forced amendment its specific instance turned on (see `tasks/DONE.md`); the general shape it described was never fixed and is inherited here. **Prune nothing, including that row: a decision, not an oversight.** Measured against `origin/main` as of 2026-08-28 (a dated snapshot — the ledger grows on every gate run, and it stood at 2245 rows when PR #69 last re-checked it): 2161 rows, of which 44 carry `cost_usd: null` and 43 of those also `wall_s < 3` (the single exception is `20260822-174202`, 5.22s). Today's specimen is one of 44, so pruning it alone makes the ledger arbitrarily clean rather than defensibly clean and leaves the next reader unable to tell "pruned" from "never happened" — worse than a lie that can at least be seen. The cleanup is blocked on the GUARD EXISTING, not on permission: prune 44 rows today and the next depsless run writes the 45th the same afternoon — which is `T-M39-15-D4`, the generator. `T-M38-5` cleans the population once, after a write-time guard lands; the signature belongs in the residuals of the ADR-019 amendment `T-M39-13`'s acceptance calls for, so that guard is a two-line check and not a policy debate. **The signature is the CONJUNCTION** — `cost_usd is None` AND an implausible `wall_s` — never either half alone: 43 of the 44 satisfy both, while 5 further rows run under 3s with a real recorded cost, so the wall-clock half on its own would condemn legitimate runs. (No section number here on purpose: that amendment is unwritten, §8 is an unallocated gap between ADR-019's §7 and the §9 PR #72's renumber added, and a citation to §8 reddens `adr-header-and-index` — which it did, once.) **Inert by coincidence, not by rule**, and the distinction is the argument for the guard rather than against it. What disarms the population today is only that every one of these rows sits at a case count nothing publishes any more: the 19 sub-0.9 rows that are `dirty: false` — clean, therefore citable by construction — sit at counts 5, 6, 10, 18, 20, 22, 32, 49, 53, 63 and 96, nowhere near the live suite sizes, which were 92 (`invariant`) and 238 (`fast`) when this was last checked and move with every merge. That is the suite having grown, not a guarantee. Revisit any of those counts — a case deletion, a suite split — and the clean rows among them become citable that moment. The ADR-019 amendment removes the deadlock but adds no admission control, so nothing stops the next one being written. **Not CI, despite the obvious guess.** Both gate scripts select the interpreter as `PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python`, so a fresh worktree — no `.venv` — runs a depsless `python3`, every import fails, and `.githooks/pre-commit` deliberately writes a full report on a red run. Artifact and ledger row then sit untracked for the next `git add -A` to sweep in.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an orchestrator may not report a PR as mergeable, nor run a review round against it, without first asserting `mergeStateStatus != DIRTY` AND that the checks it cites belong to the CURRENT head sha — one `gh pr view --json mergeStateStatus,headRefOid,statusCheckRollup` call at the moment the claim is made. Watched red by pointing it at a conflicting PR and at a PR whose green check belongs to a superseded head. Constraints, recorded so the next reader does not rediscover them: 1. A **pr-loop protocol** item, not an eval case — a forge's check state is not a property of the tree, so no loopback-only suite can grade it. 2. The `pr-loop` skill lives in the **groundwork plugin, not this repo**, so the fix is a cross-repo change — the same constraint D2 records. Not implemented here; this block is the record.
<!-- AC:END -->
