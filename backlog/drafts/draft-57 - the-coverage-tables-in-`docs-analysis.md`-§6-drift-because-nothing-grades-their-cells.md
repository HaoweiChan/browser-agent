---
id: DRAFT-57
title: >-
  the coverage tables in `docs/analysis.md` §6 drift because nothing grades
  their cells
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M41-1
  - M41
  - >-
    2026-08-26. Found while republishing §6 for M41's eight new inspector cases
    (seven of them domain-tagged
  - >-
    which is the count §6's domain row carries; the eighth is the untagged
    invariant): the published task-class and difficulty tables were stale by up
    to nine in a single cell — TC1 published at 54 against an actual 63
  - L3 at 17 against 21
  - >-
    "mechanism/unit probes" at 72 against 74 — while the split quote and the
    domain rows two lines below them were current
  - >-
    because those two ARE graded and the tables are not.
    `docs-numbers-are-derived`'s `analysis_coverage` block recomputes `{total}
    distinct cases ({golden} golden + {adversarial} adversarial)` from the case
    files and requires a row per live domain
  - >-
    and stops there; the cells are hand-typed and were never read back. This is
    the same defect that check was built for
  - one table lower.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
recompute both count tables from the case files' own `tc`/`level` tags the way the split quote already is — a `class_counts` / `level_counts` list of `{"label": ..., "tag": ...}` rows the grader formats and requires verbatim, so a re-typed cell is red. The L3 cell is prose plus a count and only its count is mechanically checkable; grade the count and leave the enumeration to the human, stating that split rather than pretending the sentence is derived. Watched red by re-typing one cell.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
