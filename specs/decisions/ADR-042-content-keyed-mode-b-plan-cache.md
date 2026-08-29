# ADR-042: Cache identical parsed mode-B plans by request content

Date: 2026-08-30
Status: accepted

**Ruling**: cache each parsed mode-B plan by the complete versioned OpenRouter
request. Exact hits replay at zero cost; input, prompt, model or parameter
changes miss, and errors or malformed plans are never cached.
**Because**: ADR-041's deployed `temperature: 0` campaign still produced
different plans for identical adjacent requests. Provider sampling controls are
not a determinism guarantee; replaying the one already-paid, already-validated
plan is.
**Enforced by**: `planner-cache-is-content-keyed` and one fixed post-deployment
campaign below.

## Decision

1. The cache key hashes `[cache_version, payload]`, where `payload` is the exact
   request sent to OpenRouter: model, temperature, system/user messages and usage
   parameters. The API key and raw request text are not stored.
2. Only `parse_plan` success writes an entry. A cache hit reports
   `{"llm_tokens": 0, "llm_usd": 0.0, "cached": true}`. A miss preserves the
   provider's measured usage; a successful miss reports `cached: false`, while
   exceptions keep the established two-field billed-usage contract.
3. Reuse the existing gitignored `runs/` cache pattern used by the judge. A
   corrupt file is a miss, never a run failure. Prompt or response-shape changes
   bump the explicit version. No dependency, retry, vote, seed or site-specific
   selector is added.
4. Keep the existing missing-key boundary: `live_planner()` still validates
   `OPENROUTER_API_KEY` before a browser opens. This change saves repeated calls;
   it does not turn cached plans into an offline execution mode.
5. This applies to exact initial plans and exact replans. Observation and replan
   note are already inside the user message, so different page state or recovery
   context cannot collide with an earlier plan.

## Fixed deployment campaign

After the implementation merge is the exact SHA reported by `/version`, run
ADR-041's four frozen tasks three times each, serialized, explicit `mode:
"plan"`, default model, no retries and no discarded runs. Read `/version` before
and after and preserve every run, action sequence and cost.

The verdict remains: zero wrong-success and at least **7/12 correct**. Also
report per-task action-sequence equality and planner cost by repetition. Exact
repetitions that need no distinct replan must show the cache effect after their
first miss; absence of that evidence fails the mechanism check. One campaign
only. A miss does not authorize resampling or a third speculative mitigation.

## Scope

This closes T-M40-5-3 only if the fixed campaign meets its repeatability and
outcome gates. T-M42-1 closes only if the same campaign restores its 7-correct
no-regression threshold. The cache cannot repair resolver, extraction or page
observation defects exposed by a stable plan; those remain separate tasks.
