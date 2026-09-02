---
id: DRAFT-65
title: 'the same task, same page, same build disagrees with itself across its own reps'
status: Draft
assignee: []
created_date: '2026-09-02 17:44'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-M40-5-3
  - T-M40-5 round-2 probe
  - '2026-08-24'
  - build `c83febb` (`docs/analysis.md` §8a-4 Round 2
  - '"Rep-level nondeterminism'
  - as a finding in its own right").
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
this is not the round-1→round-2 delta (a different build, already the subject of T-M40-5's own Update) and not T-M40-5-1/T-M40-5-2 (those name specific failure MECHANISMS — the replan-path identity-anchor kill, and the label-without-value extraction — each reproduced consistently once it fires). This block names a third, orthogonal thing: on the SAME build, SAME task text, SAME start URL, three back-to-back repetitions land in different outcome classes. multpl.com: 2/3 correct (`026e10cb`, `bcdf4d38`) vs. 1/3 `failure:extract` (`46e9eb35`). quotes.toscrape.com's author page: 1/3 correct (`4d0d3142`) vs. 2/3 `failure:semantic` (`480d71a4`, `f8945477` — the T-M40-5-2 label-without-value shape, which itself only fires on 2 of the 3 reps here, not all 3). Neither task's plan, page, or build changed between reps; only the outcome did. This means a single rep of either task is not a reliable read of that task's true pass rate on a given build — the 50.0% headline threshold number itself (§8a-4 Round 2) would have read 33.3% or 66.7% with one rep's outcome flipped, and ADR-025's protocol (3 reps per task) was sized for exactly this risk but does not yet have a case that pins the risk itself, only the aggregate threshold.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 an adversarial case that reproduces or fixture-simulates rep-level disagreement on an otherwise-identical request (e.g. a mutation that flakes between two extraction outcomes across repeated runs against unchanged fixture state), watched red first per CLAUDE.md rule 2, before any fix or mitigation (e.g. a majority-vote-of-N-reps policy, or root-causing WHY the same request produces different resolver/extraction outcomes) is attempted. Not closed by T-M40-5-1 or T-M40-5-2 individually — check both before assuming this is already covered. Update 2026-08-30: ADR-041 reproduced the same flake on build `bfb2f395`: the quotes task split 1 correct / 2 label failures and Open Library split 1 correct / 2 empty extracts. `planner-request-disables-sampling` now fixture-simulates that disagreement through the real live-planner request boundary and was watched red before `temperature: 0` mitigated the uncontrolled provider default. Keep this block open until ADR-041's one fixed post-deploy campaign shows whether the mitigation holds on the remote provider; temperature zero is not documented here as a guarantee of exact remote determinism. Remediation outcome, 2026-08-30: that remote campaign disproved sufficiency. x-rates still emitted two action sequences, multpl emitted three, and quotes split outcomes despite identical action names. The task remains todo. Do not close it on the offline request-payload case alone and do not rerun ADR-041; the next mitigation must first define a new fixed campaign and cost boundary. Update 2026-08-30 (ADR-042): the next mitigation is a persistent content-keyed cache at the shared `live_planner` boundary. Its red-first case proves exact parsed inputs replay across planner closures at zero extra planner cost, while changed recovery context and malformed responses miss. Keep this task open until the one fixed deployed campaign proves repeatability; no retry or voting policy was added. ADR-042 outcome: six of seven qualifying post-first runs hit at zero planner cost, but multpl rep 3 paid for a fresh malformed completion on its identical initial request. More importantly, multpl still split outcome classes and action sequences. Keep T-M40-5-3 open; local-file cache durability and verified-quality admission are now the two evidenced boundaries, not reasons to rerun this campaign.
<!-- AC:END -->
