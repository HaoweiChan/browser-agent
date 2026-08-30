# M48 canonical graph — red-first ledger

Date: 2026-08-30

`python3 -m evals.run --suite m49` produced
[`20260830-083657-m49.json`](../../evals/report/20260830-083657-m49.json):
**0/6**, $0.0000, 0 tokens, 0 actions, 0.05s. Each failure is deliberate: M48
freezes the cited evidence contract, and M49 alone may implement extraction.
Evidence of record: `evals/report/20260830-083657-m49.json`.

The M48 commit hook found an eval-integrity defect: the old citation suffix
accepted letters only, so this cited `m49` report appeared uncited. The
invariant now accepts lowercase letters, digits, and hyphens and pins this name.

| Case | Observed red | M49 capability that may green it |
|---|---|---|
| `m49-sec10k-terminal-live-region` | `missing_capability: terminal-live-region` | terminal state, not `Extracting…` |
| `m49-ecb-effective-date` | `missing_capability: temporal-effective-date` | date/value pairing excluding history |
| `m49-boe-dated-rate` | `missing_capability: dated-text-evidence` | rate plus effective date |
| `m49-fed-chart-data-evidence` | `missing_capability: chart-context-text-evidence` | cited text/data before vision |
| `m49-treasury-latest-tenor` | `missing_capability: latest-dated-table-cell` | latest dated tenor from table/export |
| `m49-eia-semantic-table` | `missing_capability: semantic-table-normalization` | semantic headers/cell, layout excluded |

The fixtures are static synthetic reproducers, byte- and canonical-text-hashed
to freeze the required evidence shape; they are not captures, live-rate claims,
live-site selectors, or navigation recipes. Their provenance names
the visible support-matrix URLs and existing run IDs: BoE `001b9727`, Fed
`51309b76`, Treasury `6c393014`, EIA `df2f3ed7`, ECB `35c4e211`, and the M41
10-K inspector evidence. No network or model call occurred.
