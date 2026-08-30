# M51 multi-model policy — red-first ledger

M51 adds one bounded, injectable canonical-node policy boundary.  All entries
below use offline transports and spend US$0.00.

| Report | What was red | Fix required |
| --- | --- | --- |
| [`20260830-114928-m51.json`](../../evals/report/20260830-114928-m51.json) | 0/8: no centralized canonical node policy exists. | Add policy/route/price validation, cache, telemetry, budgets, access capability, and critic non-authority seam. |
| [`20260830-115652-m51.json`](../../evals/report/20260830-115652-m51.json) | 5/8: real fixture/FastAPI checks reached the repo interpreter but Chromium/loopback was denied by the sandbox (`PermissionError`); five pure contracts passed. | Preserve the real checks; re-run them with local Chromium permission. |
| [`20260830-120254-m51.json`](../../evals/report/20260830-120254-m51.json) | Privileged focused review was 6/8: the retry re-invoked an advisory critic, and the access stub no longer matched explicit model routing. | Persist a one-attempt critic guard across retry, retain billed critic refusal usage, and assert the exact boolean/model/fallback capability arguments without retaining the header secret. |
| [`20260830-121030-m51.json`](../../evals/report/20260830-121030-m51.json) | 8/8 focused green after root review; no provider/network calls. | Final M51 focused evidence. |
| [`20260830-125036-m51.json`](../../evals/report/20260830-125036-m51.json) | 8/11 after cold review added three falsifications: served-model attribution, provider usage completeness, and pre-transport budget headroom. | Attribute the actual plan node, reject incomplete usage, and reserve the maximum completion before transport. |
| [`20260830-125356-m51.json`](../../evals/report/20260830-125356-m51.json) | 7/11 after the spec-drift audit extended existing cases for route overrides, malformed-cache eviction, planner-only top-level attribution, and aggregate critic calls. | Fail closed on every route override, evict malformed plans, and make aggregate/top-level telemetry match the canonical contract. |
| [`20260830-125659-m51.json`](../../evals/report/20260830-125659-m51.json) | 11/11 focused green after both independent reviews; no provider/network calls. | Final M51 focused completion evidence. |

Vision is deliberately disabled: the frozen OpenRouter snapshot has neither an
exact price-vetted Flash Vision ID nor evidence that Flash accepts image input.
M51 therefore refuses it before a call rather than guessing an identifier.
