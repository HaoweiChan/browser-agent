---
id: DRAFT-68
title: 'an executable line inside a debt block is ungraded, and this one was a no-op'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-8
  - 'PR #44 R9.'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
T-M39-6's acceptance shipped a copy-pasteable collapse condition, `len({json.dumps(o, sort_keys=True) for o in objects}) == 1`, which is silently a no-op against the `(obj, start, end)` tuples `_json_objects` returns after PR #44 R6 — `json.dumps` serialises a tuple as a list rather than raising, so two identical verdicts at different offsets give 2 and the condition never fires. The prose note two lines below it warned that the collapse must compare objects and not spans, so the trap was disclosed in English and contradicted in the code beside it, which is the worst of both. The snippet itself is CORRECTED in the same commit that logs this block, so nothing copy-pasteable is left wrong. What stays open is the general hole it exposes: `tasks/TODO.md` carries executable fragments in acceptance criteria, nothing runs them, and a fragment that is wrong reads exactly like a fragment that is right — the same class `report-citations-resolve` and `docs-numbers-are-derived` close for citations and counts, unclosed for code.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either a check that every fenced/backticked Python fragment under `## Debt` parses and, where it is a self-contained expression over a stated input, evaluates to what the block claims — watched red against the pre-fix snippet above — or a rule recorded in an ADR that acceptance criteria state behaviour in prose and never in runnable code, applied to the existing blocks.
<!-- AC:END -->
