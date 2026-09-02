---
id: DRAFT-118
title: a paraphrase that names no item is invisible to item 8 (references)
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R62
  - 'T-R56 round 1 (PR #36 R1/R2)'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
§6 item 8 (references) binds a reference to content — number plus slug, both agreeing with the list — so a deferral pointed at the wrong rule, or a list renumbered under its references, is red. A paragraph that restates a rule and names no item at all is still invisible: nothing counts copies. Five review rounds have produced exactly that shape, and the current defence is that pointing is cheaper than restating, plus a blacklist of three retired phrases in `docs-numbers-are-derived`. ADR-019 §6, README and the check's docstring now say this in those terms rather than claiming the copies are caught (PR #36 R1). `tasks/TODO.md` is the other unbound surface: it carries §6 references (they spell their slugs, but nothing checks that) and is outside item 8 (references)'s scanned set, deliberately — it is hand-edited every milestone and its prose says "item N" about things that are not this list, which is the false-red shape PR #36 R5 filed against the source scan.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a graded property that is red on a fresh unmarked restatement and green on this tree, and a decision on `tasks/TODO.md` — scanned with a marked region of its own, or left unbound and said so here — the shape worth trying is requiring every sentence in §6's prose and README's band section that contains an item's own distinctive token (the backticked expressions the list uses) to carry a reference, since those tokens are derived from the list rather than blacklisted. Watched red by adding a paraphrase of one item with no reference beside it.
<!-- AC:END -->
