---
id: DRAFT-123
title: >-
  browser-domain skill's fixture map still calls shop-lamp-spec.html the only
  fixture longer than PAGE_TEXT_KEEP
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R71
  - 'PR #38 R4 (LOW)'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
browser-domain skill's fixture map now states a falsehood: shop-lamp-spec.html is no longer 'the only fixture whose rendered text passes agent.PAGE_TEXT_KEEP (2000 chars)' — city-infobox.html renders ~4.1k chars and depends on that fact by design. Evidence: .claude/skills/browser-domain/SKILL.md:85-86; src/browser/fixtures/city-infobox.html header comment; tag-stripped length 4095 vs 2484.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Skill fixture map gains a city-infobox.html line (or drops 'the only').
<!-- AC:END -->
