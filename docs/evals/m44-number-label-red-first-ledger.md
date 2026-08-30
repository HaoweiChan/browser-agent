# M44 number-in-label classifier repair — red-first ledger

M44 run `467fdd77` returned the grounded extraction `Current S&P 500 PE
Ratio: 29.72 -0.07 (-0.23%)` against independently refreshed truth `29.72`.
The campaign classifier reported `wrong_success`: when the answer list also
contained the label-only string `Current S&P 500 PE Ratio:`, `_asserted`
selected the label's `500` as the number nearest `ratio`.

Triage: `eval-bug`. The production answer and truth agree; no agent, model or
site behavior is changed.

Red-first evidence:

- Before the check existed, the invariant adapter returned
  `unknown_check: number-in-label`.
- With the exact check added before the repair,
  `label_prefix_does_not_add_its_number` was `false`; the wrong-value and
  contradictory-value controls were already `true`.

The repair drops a label-only list item only when it ends in `:` and is a
strict prefix of a longer item in the same extraction. It therefore removes
the duplicate label without suppressing a wrong or contradictory value. The
three assertions now pass offline. No browser, network, model or judge call is
part of this case or repair.

The operator paused the paid campaign after 27/252 runs and US$3.9049 while
model-control behavior is investigated in another session. Its append-only
partial journal and report remain raw evidence and are not rewritten to hide
the original classifier result; they are not a completion claim for M44.
