# 002 — M1: walking skeleton, deploy spike, first real failures

**Date**: 2026-08-15 · **Milestone**: M1 · **Outcome**: deployed URL runs
NL tasks end-to-end through the live planner; 5/5 eval cases; INV-0 backed.

## Context

M1 per `tasks/TODO.md`: contract spec → trace schema → agent loop → CLI →
deploy spike on Zeabur → first red→green cases. Constraint that shaped the
session: the OpenROUTER key lives ONLY in Zeabur env vars (owner's decision —
never given to the agent locally), so the live-planner validation route became
the deployed instance itself, pulling the minimal gateway (POST /tasks + URL
guard + semaphore) forward from M4.

## What the evals caught (the valuable part)

Three real corrections, all found by running the system, none by inspection:

## Assumption → Eval contradiction → Correction

- Assumed: `json.loads` on the planner's message content is enough.
  Eval said: first live run on the deployed instance (run 5a52f0aa) died
  `failure:env` — sonnet-4.5 wrapped the plan in a ```json fence. The agent
  failed LOUD with the raw content as evidence (INV-0 posture worked).
  Corrected: `parse_plan()` strips fences; system prompt forbids them; the real
  payload became `evals/adversarial/planner-fenced-json.json` (triage:
  input-variant), watched red against the old parser before the fix.
- Assumed: task + start URL is enough planner input for an M1 skeleton.
  Eval said: runs dee8ad5d and 2e70785a — the blind planner guessed a wrong
  ARIA role (`region` for a status element) and invented a postcondition text
  ("Secret Code") it could not possibly know. Two loud classified failures.
  Corrected: pre-plan navigate → observe → plan (the architecture MUST that was
  underbuilt); planner rules now forbid targeting unobserved roles/names and
  guessing expected text (`expected_state: null` when unknowable). Triage:
  invariant-gap.
- Assumed: the default Chromium a11y snapshot shows every element.
  Eval said: `observe-hello-elements` red — the empty `<output role=status>` is
  pruned from the default tree, so the planner could never target where content
  will appear.
  Corrected: `interesting_only=False` + role filter in `observe()`; the case
  guards it green.

## Validation record

Deployed run 09b21b3a: "Click the Reveal button and tell me the secret code
that appears." → plan with observation → click (role tier, postcondition ok) →
extract → `success`, answer `secret-42`, 527 tokens, $0.0029, 4.3s, 3 actions.
Guards verified: file:// and loopback URLs rejected at POST /tasks; keyless
local run ends `failure:env` loudly, never a hung "running".

## Cold review at close-out (fresh-context reviewer, evidence only)

The cold-reviewer's three silent-failure findings all survived verification and
became adversarial cases (watched red, then fixed in one pass):

- Assumed: one `answer` slot is enough for the skeleton.
  Reviewer said: multi-extract plans silently drop all but the last item and
  report success — the contract's list answers were a dead letter.
  Corrected: extracts accumulate; `multi-extract-list` guards it.
- Assumed: `ipaddress.ip_address` + "named hosts pass" covers the URL guard.
  Reviewer said: decimal/dotted-short/hex IP spellings ("2130706433", "127.1",
  "0x7f000001") hit the ValueError branch and pass; Chromium normalizes them to
  loopback. Corrected: IP-literal regex + IPv4-mapped-IPv6 unwrap;
  `url-guard-literal-ips` is invariant-tagged — the PostToolUse hook actually
  blocked further src edits until it went green (enforcement working as built).
- Assumed: Playwright's default role/name matching is precise enough.
  Reviewer said: default substring matching resolves an ABSENT "History"
  heading to "Hello Fixture History" and extracts the wrong text as a tier-1
  success — poisoning the future self-maintenance metric. Corrected:
  `exact=True` (planner names come from the observation verbatim);
  `resolver-substring-name` guards it; the fix also exposed that the bare
  `{role: heading}` golden target was under-specified.
- Also fixed from the review: screening regex lacked word boundaries ("signing"
  matched "signin", "Loginov" matched "login") — false refusals on benign
  tasks; `screening-word-boundary` guards EN boundaries and CJK boundary-free
  matching.

## Notes for M2

The M1 planner plans once after one observation — multi-page tasks (TC2/TC3)
will invalidate mid-plan and need the evolving-prefix replan; that lands with
the M2 baseline telling us how often. Verifier is still assembly-level only
(INV-0); identity anchors + expected-output compare are M2's core.
