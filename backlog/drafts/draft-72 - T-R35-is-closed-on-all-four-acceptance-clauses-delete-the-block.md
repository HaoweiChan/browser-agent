---
id: DRAFT-72
title: T-R35 is closed on all four acceptance clauses; delete the block
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M32-17
  - 'T-M32-9; clause (1) corrected at PR #40 R4.'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
not an audit — the audit is done, and this is the evidence. T-R35 ("three specs files still publish the withdrawn 75s/15s ceilings as current") has four acceptance clauses: (1) "every ceiling statement in specs/ names 80/90/20/20" — satisfied **only as of PR #40**, and the first version of this block wrongly claimed it was already satisfied. Round 1 found two specs files still publishing a live pair that nothing enforced: `ADR-002`'s Status line ("**60s locally, 80s on CI** via `EVAL_WALL_BUDGET_S`, both measured and both enforced", plus "the local number ships unchanged at 60s") and `ADR-013`'s Ruling ("**80s since ADR-019**", marked current by "at the time of writing", 10s stale). Both are fixed in PR #40 by dropping the literals and deferring to ADR-019 §2/§3/§5 as amended by ADR-021. Note the clause's own wording is stale in the same way it was written to catch: the enforced local `fast` has been 90 since ADR-021, so a reader obeying "names 80/90/20/20" verbatim would re-introduce the defect. Read it as "names the enforced pair", and it now holds. (2) "ADR-019's Amends header matches its Ruling" — satisfied. `specs/decisions/ADR-019-wall-clock-ceilings-per-suite.md:12` reads "**Amends**: ADR-013 Decision 4 (local `fast` ceiling 60 → 80)", which is its Ruling's own number; the "60 -> 75" T-R35 quotes is gone. (3) "ADR-002's parenthetical stops asserting a live 15s invariant ceiling" — satisfied by T-M32-9, which dropped both literals from that Ruling. (4) "T-R25's Update states what is actually fixed" — satisfied. T-R25 carries `Status-note: fixed at PR #29 R22, kept for the mechanism.` (it read `[status: fixed at PR #29 R22, kept for the mechanism]` until the status field was made parseable; the claim is unchanged) and an Update that separates what was corrected from what was not, naming the mechanism as the open half. T-R35's premise ("T-R25 asserts ... it is not") no longer holds. Its fifth, optional clause — "ideally one graded row that compares INDEX/ADR ceiling numbers against `WALL_BUDGET_S`" — is what T-M32-9 built, narrower; T-M32-16 records exactly how much narrower and is the block that inherits it. T-R35's separately-named leg on `specs/decisions/INDEX.md:11` ("fast 75s local") never needed this branch: PR #29 R5 fixed it by dropping the literal, and `grep -c '75s local' specs/decisions/INDEX.md` is 0 on disk and on `origin/main`.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 T-R35 deleted from tasks/TODO.md with a DONE.md line citing this block, not re-audited. **Do not delete it before confirming (1) — until PR #40 merges, T-R35 is the only tracked pointer at ADR-002's Status line and ADR-013's Ruling.** If any clause above is wrong, the correction belongs here, in the block that made the claim.
<!-- AC:END -->
