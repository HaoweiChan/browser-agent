# ADR-020: Declaring a domain from live runs with no eval case, and a demo surface that says what a run is doing

Date: 2026-08-23
Status: accepted
Amends: ADR-014 (reviewer UI information architecture)

**Ruling**: a real-site row in `docs/support-matrix.md` may be declared from repeated end-to-end runs against the deployment with the real planner and NO committed report and NO eval case, provided the row carries every run id, its repeat count and a declared limitation naming what failed — and provided it is marked as the exception it is, in the section header and in the citation rule it bends. Separately, the reviewer UI's trace region becomes two columns: the trace, and beside it the browser's own view of the page for the step being shown plus, after the run, every extraction with the page text it was read from. The running phase spins in CSS, and every ending — including a dropped stream whose run record cannot be fetched — must leave the surface terminal and usable.
**Because**: "support the sites an investment firm actually uses" is a claim about capability, and the only two ways to back one are to guess (write cases against sites nobody has run) or to measure. We measured — 43 runs, 22 domains, 19 of which never answered once — and that produced a row shape this repo had no rule for: a domain we know a great deal about, from evidence no suite can replay. Declaring it `—` would be less accurate than what we know, and refusing to declare something measured seven times is not caution. The UI half rides along because it is the same request and the same property: a panel that animates "in progress" is honest only if every ending stops it.
**Enforced by**: `ui-terminal-state-on-every-ending`, `ui-execution-progress-is-trace-derived`, `ui-tinboker-style`, `ui-examples-cover-matrix`, `ui-rendered-narrow`

---

## Context

The owner asked for five things after looking at the deployed page. Four are
frontend. The fifth — cover the sites an investment firm actually uses — is a
claim about capability, and this repo's rule for such claims is that a human
declares them from eval evidence. There was no eval evidence for any finance
domain, and producing some would mean either writing cases against sites nobody
had run (guessing), or running them (measuring). We ran them: 43 runs, 22
domains, 13 answers, 19 domains that never answered once.

That produced a row shape this file had not seen before: a domain we know a
great deal about, from evidence that no suite can replay.

## Decision 1 — declare it, mark it, and say what the marking costs

The alternative was to leave the three domains at `—` (not yet evaluated) until
somebody wrote cases for them. Rejected: `—` would be a less accurate statement
than `supported`/`unreliable`, and the whole argument for this table is that a
declaration is an engineering-judgment act rather than a threshold. Refusing to
declare something we have measured seven times is not caution, it is hiding.

What is conceded, and written into the table rather than left implicit:

- **No gate re-checks these rows.** A regression on `companiesmarketcap.com`
  reddens nothing. It would be found by re-running the probe by hand.
- **The citation rule is weaker for them.** The table requires unsupported and
  unreliable rows to cite a concrete failing case id. `x-rates.com` and
  `multpl.com` cite failing *run* ids instead, because no case exists. A case id
  is replayed on every commit; a run id is a receipt for something that happened
  once and cannot be replayed at all, since `RUNS` is in-memory (D19). The rule
  was widened to admit the weaker form **for these rows only**, and the
  difference between the two forms is stated where the rule is.
- **Nothing grades the rule.** `support-matrix-cites-real-cases` checks that
  backticked case ids resolve; it cannot associate a citation with a row, and
  says so in its own provenance. This is a rule the file keeps by hand.
- **Nothing grades D27's arithmetic either.** Its first version published four
  wrong counts beside the run ids they summarised, and both reviewers caught it
  by recomputing. `docs-numbers-are-derived` cannot help: it recomputes README's
  block out of a committed report, and a hand-run probe has no report.

Two of the three rows are `unreliable` rather than `supported`, on runs that
answered 3/4 and 3/6. That is the D23 lesson applied before it had to be learned
again: one green run per domain would have declared all three `supported`.

## Decision 2 — the page view is trace-derived, and every ending is terminal

ADR-014 restyled this UI "without changing the trace-first information
architecture." This changes it, and the constraint carried over: the right-hand
panel renders only artefacts the run already produced — the per-step screenshot
the executor takes anyway, and `evidence.extractions` — so it can show that a
run was wrong but cannot invent anything a reviewer could not find in the run
record. The running phase spins in CSS for the same reason the progress case
forbids timers in the script: a phase that advances on a clock is a progress bar
that lies about the trace.

The panel also made a latent class of defect visible enough to fix. A UI that
animates "in progress" must reach a terminal state on *every* ending, including
the ones with no result: a dropped stream whose run record then 404s used to
leave the page claiming a dead run was still executing, with the submit button
disabled for good. `ui-terminal-state-on-every-ending` pins that, the
cross-run screenshot mix-up beside it, and the truncation marker that stops a
rejected page dump from rendering as a tidy 300-character answer.

## Consequences

- Eight real-site cards, of which one is deliberately a failing example. A demo
  that cannot show a loud failure is not evidence of anything.
- The support matrix now mixes two declaration methods. The header says which
  rows use which, and why one is weaker.
- Open, and not closed here: a case per declared live domain (or a second guard
  reading the matrix) would close both the "nothing re-checks these rows" gap
  and the §6 coverage-table hole they arrive through. A reduced-motion render
  case would close the one `ui-tinboker-style` cannot reach with substring
  fragments.
