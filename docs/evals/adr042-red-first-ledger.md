# ADR-042 red-first ledger

Date: 2026-08-30

| Case | Before production change | After production change |
|---|---|---|
| `planner-cache-is-content-keyed` | **FAIL** — `_plan_cache_path` and `_plan_cache_key` absent | **PASS** — four provider calls: one exact miss, one changed-note miss, and two malformed misses; both exact repeats, including a new planner closure, replayed the first parsed plan at zero cost |

The transport was replaced with a deterministic local function and the cache
path with a temporary directory. No key, network call, paid token, retry or
site-specific recipe was used. The case is classified `flake` because the
deployed ADR-041 campaign showed divergent completions for otherwise identical
requests; it does not simulate a resolver or extraction failure.

The separately pre-registered live campaign then ran once on deployed
`23839a05` and is preserved in `evals/report/20260829-195310-probe.json`: 4/12
correct, 8 loud failures, 0 wrong-success. Six of seven qualifying post-first
runs hit at zero planner cost; one exact multpl repetition missed, and caching
made two bad first plans repeat consistently. The mechanism and correctness
gates therefore fail; the offline row above remains a mechanism invariant, not
a claim of live task quality.
