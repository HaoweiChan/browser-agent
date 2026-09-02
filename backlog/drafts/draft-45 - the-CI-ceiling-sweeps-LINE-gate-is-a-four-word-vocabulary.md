---
id: DRAFT-45
title: the CI-ceiling sweep's LINE gate is a four-word vocabulary
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M42-19-D1
  - T-M42-19's close
  - >-
    2026-08-28 — one of that block's own three injections turned out to be
    evidence for this mechanism instead of the figure rule.
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the sweep only inspects a line if `_CI_CEILING_LINE` (`ceiling|budget|wall[- ]clock|\bstays\b`) matches it. "On CI the fast gate tolerates 90 seconds." is a stale CI ceiling by any reading, and it passes green with a correct figure rule and a correct CI token, because "tolerates" is not one of the four words. Verified directly: `_CI_SECONDS` finds `90`, `_CI_TOKEN` finds `CI`, `_CI_CEILING_LINE` does not match. This is the same shape-vs-allowlist tension PR #57 spent six rounds on, one layer in: the SITE list was inverted to an allowlist and earned its keep, and the LINE gate is still a shape. Adding "tolerates" is whack-a-mole and is explicitly not the fix being asked for.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either the line gate is inverted the way the site list was — every line in an allowlisted document is inspected, with the CI token and the figure rule doing the discriminating — measured for false positives on the current tree before it lands; or the four-word vocabulary is declared as the sweep's stated ceiling in the case's triage, so the next reader does not assume a stale ceiling in an allowlisted file is caught however it is phrased. NOT closable by adding words to the list.
<!-- AC:END -->
