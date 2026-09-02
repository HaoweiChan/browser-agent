---
id: DRAFT-124
title: >-
  the UI no longer shows a verifier-rejected extraction anywhere — the
  '(rejected by the verifier)' branch is dead and extractions are not rendered
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R72
  - 'PR #38 R5 (LOW)'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
UI: the '(rejected by the verifier)' note and `.answer.failed` scroll box are now dead code — with answer null on every INV-2 demotion, the reviewer surface shows '(no answer)' plus an 80-char preview and no longer displays the rejected extraction anywhere (extractions are not rendered), a visible loss of the evidence the UI was built to show. Evidence: src/browser/server.py:694-703 (`none` is true for every non-success now; `kind !== success && !none` unreachable from run_task); no renderer for r.evidence.extractions.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Either remove the dead branch or render `evidence.extractions` collapsed under the verdict.
<!-- AC:END -->
