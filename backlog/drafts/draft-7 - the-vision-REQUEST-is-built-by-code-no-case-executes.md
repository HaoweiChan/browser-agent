---
id: DRAFT-7
title: the vision REQUEST is built by code no case executes
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M43-D2
  - 'PR #70 R4 (LOW'
  - routed debt).
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-035 Decision 5 rules that `live_driver` sends the screenshot as a data-URL `image_url` content part beside the unchanged text prompt, and raises `failure:env` when the file it was handed cannot be read. Both live only in `src/browser/planner.py` (the `image_url` / `data:image/png;base64,` content part), and no offline case reaches them: `grep -rn 'image_url\|base64' src/browser/eval_adapter.py` is empty and no case in `evals/` sets `"driver": "live"`. What the offline suite grades is the OBSERVATION — that a screenshot was captured, attached to the right observation, and in the right frame — never the request assembled from it. A stub driver reads `observation["screenshot_path"]` itself, so the whole content-part construction is exercised by the live smoke and by nothing else.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 a `fast`-tagged case that builds the message body from a fixture screenshot path and asserts the content part's shape (and a second for the unreadable-path `failure:env` raise), watched red against a driver that drops the image — or ADR-035 Decision 5 states in words that the request half is live-only and names the smoke run that covers it, the same split Decision 6 already makes for vision QUALITY.
<!-- AC:END -->
