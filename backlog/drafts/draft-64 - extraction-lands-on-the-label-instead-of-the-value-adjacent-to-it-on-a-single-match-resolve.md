---
id: DRAFT-64
title: >-
  extraction lands on the label instead of the value, adjacent to it, on a
  single-match resolve
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-5-2
  - T-M40-5 probe
  - '2026-08-24'
  - '`run_id`s `c20b1fda`'
  - '`37fe5cec`'
  - '`2f12cf5e`'
  - build `8183dc2` (`docs/analysis.md` §8a-4
  - new failure shape 3).
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
on quotes.toscrape.com's author page, three separate probe reps all resolved a SINGLE element (`{role: strong, near: "Born:"}` or equivalent) and extracted the text of an adjacent label rather than the value beside it — `"Description:"` twice, a bare `"Born:"` once — while the correct answer (`"March 14, 1879 in Ulm, Germany"`) sat in the same evidence window, untaken. The judge correctly rejected all three. **This is explicitly NOT M38's territory**: M38 (`a target with several matches is narrowed by the page, not failed`) is about a target that resolves to N>1 elements needing narrowing; every one of these three runs resolved to exactly one element and extracted the wrong text from it — a single-match extraction defect, not an ambiguity-resolution one. It is also a DIFFERENT shape from D28's own prior record on this same page: `run_id 6811f8bf` extracted the site title `"Quotes to Scrape"` (a page-furniture shape); these three extract an in-context label instead (a label-without-value shape). The failure surface on this one page has now moved between probe rounds — worth naming as a pattern (unstable failure mode on a stable page), not just three isolated misses.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an adversarial case reproducing "resolve succeeds on one element, extracted text is a label with no adjacent value" on this or an equivalent fixture, watched red first per CLAUDE.md rule 2, before any fix to the extraction/anchor-selection path is attempted.
<!-- AC:END -->
