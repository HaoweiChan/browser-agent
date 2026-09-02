---
id: DRAFT-70
title: the ambiguity guard fires on two objects that AGREE
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M39-6
  - 'PR #44 R7.'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
the ambiguity guard fires on two objects that AGREE

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 either identical objects collapse to one verdict (`len({json.dumps(o, sort_keys=True) for o, _s, _e in objects}) == 1` — note the unpack: `objects` holds `(obj, start, end)` tuples since PR #44 R6, and `json.dumps` serialises a tuple as a list rather than raising, so the version of this line without it compares SPANS and is a silent no-op; PR #44 R9) with a scenario pinning the restated-verdict body as the verdict it states, or ADR-023 says plainly that agreeing duplicates also fail closed and a scenario pins that choice. Note for whoever takes it: the collapse must compare the OBJECTS, not their source spans, and the surviving object still has to clear the embedded-certify rule (PR #44 R6) — a restated certify is still two quotations as far as `_is_the_whole_completion` can tell.
<!-- AC:END -->
