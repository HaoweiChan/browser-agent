# M49 deterministic evidence — red-first ledger

Date: 2026-08-30

After the two M49 acceptance cases were added, the offline command
`python3 -m evals.run --suite m49` produced
[`20260830-090403-m49.json`](../../evals/report/20260830-090403-m49.json):
**0/8**, $0.0000, 0 tokens, and 0 actions. The six frozen finance contracts
and the two new generic capabilities all failed only because
`src.browser.evidence` was absent.

The then-eight cases subsequently passed at $0.00. The green implementation is
deterministic and operates only on supplied bytes: no external fetch, browser,
or model call occurred.

The two companion cases pin that CSV/XML exports require an injected,
same-origin HTTP(S) reader, and that the production module contains no
showcase hostname or selector recipe. Fixture values remain synthetic ground
truth, not claims about current live financial data.

Follow-up review added four silent-failure shapes. It produced
[`20260830-091915-m49.json`](../../evals/report/20260830-091915-m49.json):
**7/11**. The expected failures froze a relevant second semantic table,
relative/default-port same-origin exports, non-rendered rate text, and an
unknown capability. The repaired suite passed **11/11** in history row
`20260830-092406`, again with no network, browser, or model call.
