---
name: cost-discipline
description: Rules for anything that spends money or wall-clock — LLM calls, paid APIs, large downloads, long-running jobs. Use when designing a pipeline stage, choosing a model, or writing eval cases that hit external services.
---

# Cost discipline

The assignment grades cost/latency judgment explicitly. Default posture:
**deterministic code first, LLM last, and never LLM in a loop you haven't bounded.**

## Rules

1. **Escalation ladder**: regex/parser → heuristic → small model → big model.
   Each stage only sees what the previous stage couldn't handle. Record the
   per-stage hit-rate — that number goes in the analysis report.
2. **Every external call is cached.** Key = content hash of the input +
   prompt/params version. Re-running the eval suite twice must cost ~0 the
   second time.
3. **Budget per run, enforced in code**: a pipeline run carries a max-calls /
   max-tokens counter and fails loudly when exceeded — no silent runaway spend.
4. **`fast` suite makes zero paid calls.** Paid/live cases are tagged `full`
   only, and their cached responses are committed so `full` is reproducible
   offline.
5. **Log cost per run**: calls, tokens, $ estimate, wall-clock — into the same
   `evals/report/` entry. The scalability analysis is written from these logs,
   not from guesses.
6. Latency: batch what can be batched; parallelize I/O-bound stages; never
   parallelize paid calls without a semaphore.
