---
id: DRAFT-22
title: the derive-command probes build a shell string by raw replace
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D7
  - >-
    PR #67 R4 (renumbered D3 -> D7 in PR #67 round 3: the rebase onto `da6d05b`
    brought main's own `M44-P1-D3`
  - which another block's Acceptance already cites
  - so the incoming id keeps the number)
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
verbatim from the finding. The executed probes in `_check_build_sha_is_derived` substitute paths into the extracted command with raw `str.replace` and hand the result to `sh -c` unquoted, so a checkout path containing a space (or any shell metacharacter) is re-parsed as two arguments: `git -C /Users/me/my repo rev-parse HEAD` fails, the `|| :` branch fires, the file is empty, and `derives-this-checkouts-head` reddens against a Dockerfile that is correct. It cannot produce a false GREEN — the failure direction is a red on a correct tree — which is why it is P3 and not a repair. Not fixed in M44-P1: no path in this repo's checkouts contains a space, and the fix touches the one place the reviewer would rather see settled with the rest of the probe machinery than in a repair round scoped to two other findings.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 the substitution quotes with `shlex.quote`, or is done on tokens rather than on the command string, and a probe run from a directory whose name contains a space is green on the shipped Dockerfile.
<!-- AC:END -->
