# M48 red-first ledger — accessible-name extraction

Date: 2026-08-30

| case | triage | red observed before production edit | greened by |
|---|---|---|---|
| `extract-falls-back-to-accessible-name` | `input-variant` | target resolved at `role`, then `failure:extract`; reason `extraction returned empty text`, answer `null` | ADR-043: rendered text first, then the same image link's browser-computed accessible name |

The fixture removes the live site and planner. The failed shape is one visible
image link, one unique accessible name and no `innerText`; therefore the result
cannot be attributed to model variance, resolver ambiguity or navigation.
The first broad implementation also turned `trap-empty-extraction` into the
false answer `Result summary`; that existing case is the counterexample that
narrows admission to an image-bearing link rather than every named control.

Gate fixed-point artifacts are retained and cited rather than discarded. The
prior 273-case baseline `evals/report/20260829-192958-fast.json` was 270/273.
`evals/report/20260829-201406-invariant.json` was 111/115 and recorded the
expected count/index reds before the derived documents moved.
`evals/report/20260829-201645-fast.json` was 270/274, recorded the over-broad
fallback and sets the timing band. `evals/report/20260829-202042-fast.json` was
272/274 on the narrowed final code; its only reds were the headline and band
fixed points repaired next. `evals/report/20260829-202234-invariant.json` was
113/115 and caught the band bullet's ambiguous second report citation plus the
now-superseded report-citation text.
