---
id: DRAFT-60
title: the live SITE count is published three times and derived twice
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M41-7
  - 'PR #58 R7'
  - >-
    2026-08-26. Routed to debt rather than repair because the line is TRUE today
    — it fails no honesty test — and R1's acceptance made this extra hook
    explicitly optional ("ideally"). Evidence
  - >-
    carried verbatim from the review: the live SITE count is published three
    times but derived twice: `README.md:41` carries a third copy that the
    extended `docs-numbers-are-derived` quote does not cover
  - >-
    so the recurrence-stopper R1 installed still leaves one publication of the
    same number free to go stale. `README.md:41` reads `python3 -m evals.run
    --suite live        # 11 cases
  - 5 real sites
  - still $0.00`
  - >-
    but the graded quote in `evals/adversarial/docs-numbers-are-derived.json` is
    only `"--suite live        # {live} cases"` — a prefix that matches whatever
    follows the comma. Verified: with `counts['live_sites']` forced to 6
  - >-
    `README.md:204` and `docs/analysis.md:72` go red (`readme_does_not_say` /
    `doc_does_not_say`) while line 41's `5 real sites` is never inspected.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the live SITE count is published three times and derived twice

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the README:41 quote in `readme_quotes` becomes `--suite live        # {live} cases, {live_sites} real sites` (or line 41 drops the site count), watched red against the current text with `live_sites` perturbed, and the fast suite stays green. Worth one line beyond the review's own framing: a prefix quote that silently tolerates whatever follows it is a general shape, not a one-line defect — `readme_quotes` matches by substring, so EVERY quote in that list stops grading at its last character. Whether that wants a general fix (anchor each quote to end-of-line) or three more characters in one string is the decision this block carries.
<!-- AC:END -->
