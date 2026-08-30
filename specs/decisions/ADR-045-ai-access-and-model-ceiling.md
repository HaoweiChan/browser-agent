# ADR-045 — authenticate paid LLM access and remove the loop price exception

**Ruling**: Every `POST /tasks` requires a browser-verified **LLM access key** before a run exists; the default route is `deepseek/deepseek-v4-pro` then `openai/gpt-5-mini`; every accepted model is under the frozen DeepSeek ceiling, with no mode exception, and Opus 5 is refused.

**Because**: On 2026-08-30 the owner found $33 of Claude Opus 5 usage despite the
earlier affordability rule. The code had explicitly exempted loop mode from that
rule and the public endpoint let any visitor spend the deployment credential.
Rotating the provider key stops the current exposure but does not close either
path. “LLM access key” says what the browser credential unlocks without inviting
users to paste an OpenRouter API key. GPT-5 mini is under the ceiling recorded in
the frozen decision snapshot; OpenRouter's live prices may drift, so changing the
snapshot remains an explicit re-decision rather than a silent runtime change.

**Enforced by**: `gateway-model-reaches-planner`, `gateway-canonical-selects-planner`, and
`ui-no-url-guard-and-example-chips`.

## Consequences

- Browser check stays public because it spends no LLM tokens.
- A missing deployment access key disables paid requests instead of opening them.
- OpenRouter receives `models` in priority order only for the default route;
  ablation/model overrides stay single-model measurements.
- The run record names the model OpenRouter actually served; mixed loop calls
  name each effective model instead of attributing fallback spend to DeepSeek.
- Credential-bearing ablation requests refuse redirects rather than forwarding
  the access key to a new origin.
- ADR-027 Decision 4 and ADR-028 §8's Opus/loop price exception are superseded.

## Red-first evidence

Before the implementation, the model case observed Luna for both defaults,
refused GPT-5 mini, accepted Opus 5, and the widened all-accepted ceiling sweep
reported Opus over both caps. The rendered page had no access-key control or
header. At the HTTP boundary `/tasks` accepted missing and wrong credentials and
`/access/verify` did not exist. These are invariant gaps: each old state could
spend money while the prior suite stayed green.

The required cold review then found three more silent inputs: explicit DeepSeek
still shared the default fallback route, fallback responses discarded
OpenRouter's effective model id, and urllib forwarded the access header across a
redirect. Each was added to the existing gateway/preflight cases, watched red,
then fixed before the full gates were repeated.
