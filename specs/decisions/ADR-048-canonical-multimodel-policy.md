# ADR-048: bound canonical model nodes behind one policy

Date: 2026-08-30
Status: accepted

**Ruling**: Canonical model calls pass through one policy boundary: deterministic evidence first; Pro→GPT-5 mini for planning; Flash reserved for a bounded evidence/text gap; GPT-5 mini only for an advisory ambiguity critic. Vision is disabled until frozen evidence names an exact price-vetted Flash Vision route.
**Because**: a requested model name, a provider-served model, cache identity, and spend accounting must not be independent paths that can silently reintroduce an over-ceiling model.
**Enforced by**: `m51-node-policy-is-central-and-price-bounded`, `m51-node-cache-binds-node-route-input-and-version`, `m51-node-budget-stops-before-next-call`, `m51-node-telemetry-attributes-actual-served-model`, `m51-vision-requires-verified-access-and-known-price-vetted-model`, `m51-critic-runs-only-on-semantic-ambiguity-and-cannot-publish`, `m51-canonical-deterministic-evidence-spends-zero-flash-calls`, and `m51-public-canonical-threads-verified-access-without-logging-secret`.

---

## Decision

1. `src/browser/model_policy.py` is the sole canonical-node LLM boundary. Its
   table declares each role's trigger, ordered route, call/input/output/token/USD
   limits, cache namespace, verified-access requirement, authority, and enabled
   state. Its compact production price projection is mechanically checked against
   `evals/labels/openrouter-models-20260820.json`; every route is at or below
   `deepseek/deepseek-v4-pro` on prompt and completion price.

2. A plan uses `deepseek/deepseek-v4-pro` with `openai/gpt-5-mini` fallback
   only for the omitted/default route. An explicit public override is either
   Pro or GPT-5 mini and pins exactly that single model; historical ablation IDs
   are refused rather than accepted and silently rerouted. Provider response
   `model`, not requested name, is the attribution; any unknown, unapproved, or
   over-ceiling served model fails loudly after billed usage is recorded.

3. Deterministic cited evidence remains M49's first and only active evidence
   mechanism. Flash has a disabled, bounded seam for a future deterministic
   evidence-gap trigger; no M51 run calls it. The snapshot has no exact Flash
   Vision ID and no Flash image-capability evidence, so vision is disabled
   before transport. GPT-5 mini remains the vetted fallback metadata, not a way
   to enable an unvetted visual route.

4. Cache identity binds policy version, namespace, node, ordered route,
   messages/input, and schema version. A valid cache hit reports zero new
   tokens/USD and the originally served model. Invalid cache records miss and
   call the injected transport; they never certify content. The small JSON cache
   is shared under `runs/` like the existing planner cache; public runs are
   serialized, and evals inject an in-memory cache.

5. A call is bounded before transport by input size and prior per-node
   calls/tokens/USD; output tokens are capped in the request. Every attempted
   transport path records safe telemetry only: requested route, actual served
   model if readable, tokens, USD, latency, cached flag, and outcome. Readable
   billed usage is charged even when model/schema/content validation rejects the
   response. No prompt, page evidence, header, or access key enters telemetry.

6. The gateway verifies `X-LLM-Access-Key` before allocation, then passes only
   `verified_access=True` into the canonical runtime. Local/eval injection may
   pass that boolean; it never passes or stores the key. The local CLI requires
   an explicit `--allow-llm` trusted-process opt-in.

7. The only critic trigger is a deterministic verifier FAIL whose reason starts
   `ambiguous semantic evidence:`. It is advisory trace metadata: it cannot
   alter verifier FAIL, route to publish, or create a graph edge. No current
   deterministic producer emits that marker, so the seam is dormant unless a
   future contract supplies one.

## Consequences

- Legacy planner/judge caches and direct plan/loop/escalate comparators remain
  untouched as historical eval machinery; M51 centralizes only canonical calls.
- `control_flow.node_calls` exposes safe node accounting after completion,
  including cached, failed, and critic attempts, with no private reasoning.
- M52 remains the first authorized place for a fresh paid/deployed campaign;
  M51's coverage is offline and US$0.00.
