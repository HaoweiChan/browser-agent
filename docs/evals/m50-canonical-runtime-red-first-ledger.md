# M50 canonical runtime — red-first ledger

Date: 2026-08-30

| Case | Deliberate red | Green evidence | What the case pins |
|---|---|---|---|
| Canonical graph foundation | [20260830-093806-m50.json](../../evals/report/20260830-093806-m50.json), 0/3: graph capability, parity, and retry cases all failed before the runtime existed | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | the engine owns the fixed node order, trace, and sole retry edge |
| Snapshot evidence packet | [20260830-102539-m50.json](../../evals/report/20260830-102539-m50.json), 3/7: all four snapshot cases failed before the extractor existed | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | evidence cites exact canonical offsets and source/text hashes, and empty input fails loudly |
| Non-rendered text exclusion | [20260830-103036-m50.json](../../evals/report/20260830-103036-m50.json), 6/7: the packet selected hidden head/script text | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | hidden metadata remains hash-bound but cannot become visible evidence |
| Runtime parity and retry | [20260830-104612-m50.json](../../evals/report/20260830-104612-m50.json), 5/7: canonical execution did not yet preserve plan results or retry a rejected read | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | canonical reuses the existing resolver/executor/verifier and retries only through `decide → plan` |
| Mutation retry refusal | [20260830-104809-m50.json](../../evals/report/20260830-104809-m50.json), 7/8: a later read failure hid an earlier state-changing action and allowed retry | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | any unsuperseded `STATE_CHANGING` action closes the retry edge |
| Shared-runtime refactor invariants | [20260830-104920-invariant.json](../../evals/report/20260830-104920-invariant.json), 113/115: the first extraction moved source anchors checked by two structural invariants | [history row `20260830-112545`](../../evals/report/history.jsonl), 115/115 in 38.42s | shared executor extraction retains the plan-adoption boundary and derived documentation counts |
| `m50-canonical-verifier-retry-clears-attempt` | [20260830-110215-m50.json](../../evals/report/20260830-110215-m50.json), 8/9: a verifier-only retry kept the first rejected extraction, then reached `review_required` with a FAIL verdict | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | retry clears only that attempt's answer/evidence and supersedes the prior read |
| `m50-public-canonical-only` | [20260830-110336-m50.json](../../evals/report/20260830-110336-m50.json), 9/10: public legacy values were still accepted and default did not invoke canonical | [20260830-110641-m50.json](../../evals/report/20260830-110641-m50.json), 10/10 | public legacy values are rejected; default canonical does not construct a driver |

The post-fix report was forced with `--report`; routine green runs stay
uncaptured under ADR-012.
