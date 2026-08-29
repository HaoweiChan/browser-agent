# ADR-041: Mode B's wider vocabulary is measured before and after the prompt changes

Date: 2026-08-30
Status: accepted

**Ruling**: run the four regressed ADR-025 tasks 3× before and after mode B's
prompt gains its missing verbs. Explicit plan mode, default model, every run
published; post-change requires zero wrong-success and no loss of correct answers.
**Because**: the offline suite can prove that the prompt and executor vocabulary
agree, but every offline mode B plan is hand-written. Only a live before/after
probe can distinguish "the planner can now wait" from "the planner now waits
instead of completing plans that worked before."
**Enforced by**: procedural pre-registration. This file is pushed before either
round runs; T-M42-1 remains open until the post-change report is committed.

---

## Frozen task table

These are ADR-025's four regressed rows, unchanged.

| # | Task | Start URL |
|---|---|---|
| 1 | `What is the current exchange rate from EUR to USD?` | `https://www.x-rates.com/calculator/?from=EUR&to=USD&amount=1` |
| 2 | `What is the current S&P 500 P/E ratio?` | `https://www.multpl.com/s-p-500-pe-ratio` |
| 3 | `When was this author born?` | `https://quotes.toscrape.com/author/Albert-Einstein/` |
| 4 | `Who is the author of this book?` | `https://openlibrary.org/books/OL7025919M` |

## Protocol

1. Verify `GET /version` before and after each round. The baseline build must be
   `main@c0bd27619a75ae2953ba7f45a329574470f3697a`; the post-change build must
   equal the merge commit containing the prompt change. A mismatched or unknown
   version stops the round.
2. Submit each row three times, serialized through `/readyz`, to
   `https://whaleforce-browser-agent.zeabur.app/tasks` with its frozen `task`,
   `url`, `mode: "plan"`, and no `model` field: twelve runs per round.
3. Record every run's id, answer, status, reason, actions, model cost, judge
   cost, and wall time. Three consecutive transport/service failures stop the
   round; nothing already observed is discarded.
4. Re-read ground truth from the live pages at each round. A moving numerical
   answer is compared with that round's page, never ADR-025's old literal.
5. Report four disjoint counts per row and in total: correct answer, loud
   failure, wrong success, refusal. Never blend them into one pass rate.

## Pre-registered verdicts

- **Safety (hard)**: post-change wrong-success is 0/12. Any wrong-success fails.
- **No regression**: post-change correct answers are greater than or equal to
  the contemporaneous baseline's correct answers. Below it fails.
- **Historical floor**: report both rounds against ADR-025 round 2's 6/12. If
  the baseline is already below 6/12, call that drift; do not lower the
  no-regression threshold after seeing it.
- Refusals remain separate and never count as correct or as a loud failure.

## Vocabulary boundary

Mode B is offered every executor action except `final_answer` (loop cadence's
terminal call) and `click_at` (requires a viewport screenshot, which mode B's
planning observation never carries under ADR-035). The five actions this change
adds are `select_option`, `scroll`, `press`, `wait_for`, and `go_back`.

## Outcome

Pre-change baseline completed after this ADR was pushed, against deployed
`main@c0bd27619a75ae2953ba7f45a329574470f3697a` with `/version` unchanged
before and after. Result: **7/12 correct, 5/12 loud failure, 0/12 wrong-success,
0/12 refusal**; $0.0104268 planner + $0.00126284 judge. Per task: x-rates
3/3, multpl 0/3, quotes-author 2/3, openlibrary 2/3. Every run id, terminal
record, action sequence and cost is in
`evals/report/20260830-014602-probe.json`. The post-change round remains
pending, and its no-regression threshold is therefore frozen at **7 correct**.
