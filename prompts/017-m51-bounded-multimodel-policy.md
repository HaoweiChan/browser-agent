# 017 — M51: multi-model policy without a model zoo

**Date**: 2026-08-30 · **Milestone**: M51 · **Outcome**: one central policy
boundary now owns canonical model routes, prices, budgets, cache identity,
access capability, and per-call telemetry. `specs/decisions/ADR-048-canonical-multimodel-policy.md`.

## Context and condensed prompt

The owner proposed borrowing the SEC 10-K extractor's agentic flow: a cheap
large-input extractor, a stronger planner, workers, a deterministic verifier,
and an optional independent critic. They explicitly did not want a large agent
class hierarchy, and required every model to remain no more expensive than
DeepSeek V4 Pro.

## Decision

The recommendation was **modified**. The browser agent adopted the role policy
and deterministic-authority split, but not active Flash or Vision calls. M51
had no safe evidence-gap trigger or exact price-vetted vision model identifier,
so deterministic evidence remains the zero-call extractor. DeepSeek V4 Pro
plans with GPT-5 mini fallback; GPT-5 mini critiques only explicit semantic
ambiguity and cannot overturn the verifier.

The policy is centralized rather than copied across server, CLI, and agent
code. Cache keys include node, route, input hash, and policy version. Every
call reports the actual served model, tokens, USD, latency, and outcome.

## Assumption → Eval contradiction → Correction

- Assumed: the target architecture required activating a model for every named
  role immediately.
- Eval said: `m51-canonical-deterministic-evidence-spends-zero-flash-calls`
  showed the canonical evidence packet already meets the contract without a
  paid call; Vision had no exact vetted identifier.
- Corrected: evidence stays deterministic and Vision fails closed until a
  separate milestone supplies a safe trigger and price-vetted route.

- Assumed: checking prior spend below a node ceiling was sufficient preflight.
- Eval said: `m51-near-budget-refuses-before-transport` demonstrated a call
  could start with too little room for its declared maximum completion.
- Corrected: preflight reserves the requested output-token and maximum-price
  headroom before transport; it never relies on a post-payment refusal.
