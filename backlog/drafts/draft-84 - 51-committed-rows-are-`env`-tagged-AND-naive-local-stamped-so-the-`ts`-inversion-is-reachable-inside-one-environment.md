---
id: DRAFT-84
title: >-
  51 committed rows are `env`-tagged AND naive-local stamped, so the `ts`
  inversion is reachable inside one environment
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R77
  - 'PR #41 R6 (T-R44)'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`env` and the UTC stamp landed in two different commits of this PR, so the committed ledger has a band of rows carrying `env: local` while still stamped in naive Asia/Taipei time. The direction is the opposite of the obvious one, which is what makes it easy to get wrong: a Taipei stamp sorts ABOVE a UTC stamp of the same day, not below. Inside `env: local`, `20260823-210938` (13:09:38Z, PRE-switch, Taipei) sorts above `20260823-140957` (14:09:57Z, POST-switch, UTC) while being EARLIER in real time — the exact T-M32-13 inversion, in the one place item 9 (environment) cannot help, because both rows are in the same environment and the filter has nothing to separate them by. Not reachable today, and the reason is narrow: those rows sit at `fast` 138 / 154 and `invariant` 54 / 59, which are dead counts, and `_band_wrong` only reads rows at the CURRENT case count. That is the same assumption ADR-019 §7 states for the pre-`env` rows, and it holds for the same reason — counts only grow. What is new is that `env`-tagged no longer implies UTC-stamped, so a reader who uses the tag as a proxy for "post-switch" is wrong for these 51 rows. Repro. This block has now published two wrong selectors, which is worth more than the selector itself: the first used `ts < "20260823-140957"` and returned NOTHING, because that IS `min(ts)` over every env-tagged row (PR #41 R10) — worse than filing no block, since the next reader concludes the residual is gone. Its replacement, `ts > "20260823-16"`, was right for exactly one day: it returns 51 rows at the commit that wrote it and 52 at the next one, having picked up a UTC row stamped `20260823-160006`. Both failures are the same mistake the block is about — reading a naive stamp as if it ordered real time. The set is CLOSED (nothing will ever be added to it), so bound it on both sides by the window the Taipei stamps actually occupy, and do not use a bare threshold: rows = [json.loads(l) for l in open("evals/report/history.jsonl") if l.strip()] pre  = [r for r in rows if "env" in r and "20260823-2000" <= r["ts"] <= "20260823-2359"] # -> 51 rows, ts 20260823-210938 .. 20260823-220602, all `env: local`, #    shas 0efb0e9 / 9840e23 / f90b58d, at fast 138/154 and invariant 54/59. # The env-tagged stamps occupy hours 14/15/16 (UTC) and 21/22 (Taipei) on # 2026-08-23, with nothing between: that gap is the switch. Note that `f90b58d` appears on BOTH sides — it was HEAD while the stamp change sat uncommitted — so sha is not a discriminator either. Compare any of those 51 against a post-switch row of the same suite and count and the ordering is inverted.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the ledger records the regime per row (an offset, or a marker field) so the two are distinguishable without inference, or a band cited at a count that holds rows from both regimes is refused. **Watch it red on a CONSTRUCTED ledger, not on the committed one.** Grouping every env-tagged row by (suite, total) and regime yields NO mixed bucket: fast/138 [0 UTC, 10 Taipei], fast/154 [0, 5], invariant/54 [0, 30], invariant/59 [0, 6], and the UTC rows sit only at fast/155-156 and invariant/60-61. An earlier version of this line prescribed a watched-red "at `fast` 138, where both regimes are present", which is false — fast/138 is ten rows, all Taipei — and someone following it would have seen green and concluded their guard was broken (PR #41 R16). Drive `_band_wrong` with a two-row ledger you build, the way `band-is-graded-against-its-own-environment` drives all five of its probes. A third option is to accept it permanently and have ADR-019 §7 say `env`-tagged does not imply UTC-stamped, which is what it says today.
<!-- AC:END -->
