---
id: DRAFT-115
title: '`_run_ui_rendered_case` leaks a BrowserContext when the case errors'
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R28
  - 'PR #23 round-5 verification (out-of-scope note'
  - no finding id)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the R5 repair moved the case onto the shared Chromium, but its `go()` closes the context only on the success path, so an exception inside `page.evaluate` leaks a BrowserContext onto the shared browser for the rest of the suite. Its sibling `_run_observe_case` (`src/browser/eval_adapter.py:466`) already uses the try/finally pattern this one needs.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `go()` wraps its context in try/finally, and a case asserts the shared browser holds no contexts after a deliberately-erroring render.
<!-- AC:END -->
