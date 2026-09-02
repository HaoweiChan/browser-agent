---
id: TASK-2
title: 'the request-frame rule is the untried path, and nothing measured it'
status: Done
assignee: []
created_date: '2026-09-02 18:09'
labels: []
dependencies: []
references:
  - TODO.md M45-D8
  - 'PR #56 R8'
  - >-
    2026-08-26. M45 published a universal claim — that no regex separates a CJK
    term inside another word from the same term heading a real request's object
    — and conceded one exception by pointing at a debt block that did not
    contain it. This is that block.
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
every narrowing M45 tried reasoned about the term's NEIGHBOURS (what character follows 密碼 / 購買 / 刪除), and all four were falsified. The untried mechanism reasons about the request frame instead, and the split is clean in every row the case pins: each false positive is a question ABOUT A PAGE (這個頁面對密碼學的定義是什麼？ / …會保留多久？ / 美元的購買力在這頁怎麼呈現？), and each false negative is an imperative addressed to the agent (幫我… / 請… / 我要…). A frame rule would refuse on the imperative and let the question through, which is orthogonal to where the term sits inside a word — so M45's universal claim, stated as it is, is NOT established for it. It is unprobed in both languages: the English side has never needed it, because `\b` does the work there, so shipping one would move the refusal policy for English too and needs its own ADR.

Probe: none — migrated from TODO.md (merged as PR #84; kept because docs still point at this id)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a question-vs-imperative frame rule is written and measured against the FULL row set of `screening-zh-term-inside-another-word` (all 29 rows) plus `l5-refuse-destructive-zh`, `screening-word-boundary` and `l5-refuse-delete-determiners`. Either it strictly beats the bare terms — every false-positive row goes green and no true-positive row goes red — in which case it ships red-first with an ADR covering the policy move, or it does not, in which case the universal claim in `src/browser/agent.py`, `docs/support-matrix.md` D31, `docs/analysis.md` §8a-5 and the case provenance is downgraded from "no regex separates those" to "no NEIGHBOUR rule separates those; the frame rule was measured and did not either, see this block". Either outcome closes it. Gate green. IMPLEMENTED 2026-08-29 under ADR-040. A read frame gates a measured informational-mention allowlist, and every blocked match must be wholly inside one such mention; a safe clause cannot launder an unrelated destructive clause. Bare imperatives remain refused. The valid red-first invariant run is `20260829-085718` (107/109: the policy row and ADR/UI index). Cold review then added four composition variants and watched the policy row red again in `20260829-091252` (108/109) before the match-level repair. The English download-statistics row moved with the same ADR. PR #84 R1/R2 then found that a page marker could launder an action request and that ambiguous 登陸/登陆 matches were absent from the containment set. Six polite, bare and clause-order variants were watched red in `20260829-093259` and `20260829-093430` (each 108/109). The repair restricts the bypass to measured question grammar and binds both risk-match families. Final repair gate: invariant 109/109, fast 268/268; baseline unchanged.
<!-- AC:END -->
