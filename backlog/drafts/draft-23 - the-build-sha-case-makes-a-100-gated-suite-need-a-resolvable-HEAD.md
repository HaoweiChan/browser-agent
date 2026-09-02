---
id: DRAFT-23
title: the build-sha case makes a 100%-gated suite need a resolvable HEAD
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md M44-P1-D2
  - 'PR #65 R4'
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
verbatim from the finding. "The new case makes a 100%-gated suite depend on `git rev-parse HEAD` resolving in the process's environment: a correct route reddens invariant wherever HEAD does not resolve." Evidence: "`src/browser/ eval_adapter.py` `_check_version_never_guesses`: on `head_sha is None` it appends `wrong['head-does-not-resolve']`, so `passed` is False even when all 13 probes matched. A `container:` CI job, a `git archive` tarball, or a git-less image fails a suite CLAUDE.md gates at 100%. Declared as ceiling (3) in the case triage, so this is disclosure-complete, not hidden." Repro: "Run the case with git removed from PATH, or from an export of the tree -> passed False with `wrong['head-does-not-resolve']` while the route is correct." Second instance (PR #67 R5, outside the quoted finding above, which predates it): `_check_build_sha_is_derived` does the same thing for the same reason — its executed probes compare against `git rev-parse HEAD`, so an unresolvable HEAD reddens a correct Dockerfile. Both functions are in scope for the fix below, and the ceiling is now listed in that case's triage; it was not when the case was written, which is what made this a finding rather than a duplicate. Not fixed in M44-P1 on the reviewer's own routing: the precondition is what makes the `absent` probe a git-fallback guard rather than a tautology, and today it holds everywhere the suite runs (`actions/checkout` gives CI a real checkout). Acceptance, carrying the reviewer's note: if it ever bites, the non-vacuity signal moves to `got` — where `got['head_resolves']` already is — with a separate case asserting it, so an unresolvable HEAD reports "this probe was vacuous here" rather than "the route is broken". The move is only correct WITH that second case: dropping the key from `wrong` and adding nothing makes a vacuous probe silently green, which is worse than a loud false red.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
