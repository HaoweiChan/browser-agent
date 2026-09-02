---
id: DRAFT-40
title: M45 ran four narrowings and published three
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M45-D9
  - 'PR #56 R9'
  - >-
    2026-08-26. Routed to debt as LOW because the undercount WEAKENS the
    published universal claim rather than inflating it — but two case rows
    currently have no stated purpose
  - which is its own defect.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`docs/support-matrix.md` D31, `docs/analysis.md` §8a-5's attempts table, the M45 RESULT block above and the case triage in `screening-zh-term-inside-another-word` all say three lookaheads were written and watched red three times. Four were. The case's red-watch (2), `evals/report/20260825-175345-invariant.json`, lists 幫我購買力士洗髮精 and 帮我购买力度伸发泡锭 among its wrong rows, and neither can be un-refused by any of the three lookaheads the documents name — they were killed by a fourth, `[購购][買买](?!力)`, which the withdrawn-narrowing record never mentions. Ablation re-run on this tree and confirming R9 exactly: against `[購购][買买](?!力)` both rows are ALLOWED (the regex misses them, so the case reddens); against `[購购][買买](?!力平[價价])` both are BLOCKED (green). So the red watch that killed the first 購買 attempt cannot have been produced by the second, and the two rows are evidence of an attempt no document names.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the attempts table in `docs/analysis.md`, D31 and the case triage list `[購购][買买](?!力)` as the fourth falsified narrowing with 幫我購買力士洗髮精 and 帮我购买力度伸发泡锭 as its counterexamples; the counts "three attempts" and "all six counterexamples" become four and eight, matching the eight counterexample rows the case actually pins; and the strengthened claim — four independent narrowings falsified, not three — is stated where the universal is made. No code change. Gate green. Surfaces carrying the count, enumerated so closing this block by its own checklist cannot leave a wrong one behind (PR #56 R12): `docs/analysis.md` §8a-5's attempts table, `docs/support-matrix.md` D31, the M45 RESULT block in this file, the `triage.note` of `screening-zh-term-inside-another-word`, and **M45-D5's Acceptance in this file** — which R12 caught stating "three" in the same commit that filed this block saying "four". D5 has since been written count-free ("one of the narrowings M45 withdrew"), which is why it needs no number when this block is closed; it stays on the list so a future edit that re-introduces a count there is caught by the same checklist.
<!-- AC:END -->
