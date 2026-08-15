---
name: eval-protocol
description: How to run, read, and extend the eval harness. Use whenever adding eval cases, interpreting eval results/reports, moving the baseline, or deciding whether a change is safe to commit.
---

# Eval protocol

## Suites

- `invariant` — properties that must ALWAYS hold; pure code, no LLM/network.
  Run automatically by the PostToolUse hook after every src/ edit. Must stay
  fast (< ~10s total). Gated at 100% regardless of baseline.
- `fast` — the pre-commit gate suite. Fixtures + LLM stubbed at the module
  boundary; zero paid calls, fully offline (< ~60s total).
- `full` — live sites + real LLM calls. Run manually or scheduled (before a
  milestone, for the analysis report, for the support matrix) — never in CI,
  never on commit.
- `all` — CLI-only catch-all (`--suite all`): matches every case regardless of
  tags. Not a tag; don't put it in a case's `suites`.

Tag cases via `"suites": [...]` in the case JSON; default is `["fast"]`.

## Reading a run

- Score = passed/total, printed at the end and written to `evals/report/`.
- Reports are committed to git — the report history is the progress narrative.
- A FAIL on an `adversarial` case that has never passed is expected debt;
  a FAIL on a `golden` case is a regression. The gate only compares total
  score to baseline, so eyeball WHICH cases flipped, not just the number.

## Adding a case

1. Write the JSON case first, run it, **watch it fail** (or watch it pass and
   confirm the pass is legitimate — an eval that can't go red is decoration).
2. Golden = hand-verified expected output. Record how you verified it in the
   case file under `"provenance"`.
3. Adversarial = an input that broke (or is designed to break) the pipeline.
   Every production failure and every cold-reviewer finding becomes one.

## Baseline discipline

`.eval-baseline.json` moves only via `--update-baseline`, only deliberately,
and only with an ADR (or ADR update) saying why. Downward moves are allowed
— e.g. after adding a batch of hard adversarial cases — but must be recorded.
