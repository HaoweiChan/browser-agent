---
id: DRAFT-119
title: '`_BAND_DEF` matches prose at column 0, so a docstring can raise a false stray'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R64
  - 'PR #36 R23'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/eval_adapter.py:439-441` is `^(?:def )?(_band\w*|...|_REGION)\b` with `re.M`, so `def ` is optional and the anchor is column 0 only. A column-0 line inside a triple-quoted string that begins with a pinned name is reported as a stray definition, with a message naming a constant that never moved. The shape is not hypothetical: the file already carries column-0 lines inside docstrings. Adding `_BAND_LINE is what ADR-019 publishes; see the band section.` at column 0 inside `_check_history_dirty_before_report`'s docstring yields `{outside_the_region: ['_BAND_LINE'], passed: False}`. Direction is fail-closed only — a spurious match inside the region cannot mask a real definition outside it, because every match is offset-tested independently — so this is noise in a gate suite, not a hole.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the pattern requires an assignment or def form (e.g. `^(?:def )?(_band...|...)\s*(?:\(|[:=,])`), or the residue is named where the pattern is defined: prose at column 0 naming a pinned constant reddens the invariant suite.
<!-- AC:END -->
