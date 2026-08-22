# browser-agent

A browser automation agent that takes a natural-language task, plans it against
what the page actually shows, executes it in a real headless Chromium, and then
**has a separate component decide whether it worked**.

**Live:** https://whaleforce-browser-agent.zeabur.app/ — submit a task, watch the
trace stream, open a failed step and its screenshot.

Built on [groundwork](https://github.com/HaoweiChan/groundwork), an eval-first
scaffold. Reliability here has no public ground truth, so correctness is encoded
as executable invariants and golden/adversarial cases instead of prose.

---

## The one idea

Most of this repo exists to answer a single question: **how do you know the
agent didn't just say something plausible?**

An agent that grades its own work will report success. So the executor never
does. A run's status is assembled by a separate `OutcomeVerifier` that reads
raw evidence — what was extracted, and what the page said *where* it was
extracted — never the executor's conclusion. Three invariants hold that line:

| | |
|---|---|
| **INV-0** | `success` requires a non-empty answer **and** a non-empty trace. An empty extraction is `failure:extract`, never a quiet success. |
| **INV-2** | A non-PASS verdict can never be reported as `success`. The verifier outranks the executor. |
| **INV-3** | Every budget exhaustion ends the run with a failure class and the full trace — never a quiet stop. |

Each is backed by a case that has been watched go red. An invariant with no
failing case is decoration.

## Running it

```bash
python3 -m evals.run --suite fast        # offline gate: 116 cases, zero paid calls
python3 -m evals.run --suite invariant   # must-always-hold; pure-code probes + the fixture runs that pin them
python3 -m evals.run --suite live        # 9 cases, 4 real sites, still $0.00
```

The reviewer UI locally — task submission needs `OPENROUTER_API_KEY`; the
guards, matrix and browser smoke test work without one:

```bash
python3 -m uvicorn src.browser.server:app --port 8099
```

## Where it stands

Latest offline baseline — `evals/report/20260822-153750-fast.json`, with
`evals/report/20260822-153803-invariant.json` and
`evals/report/20260822-111204-live.json`:

```
fast  116/116    invariant  48/48    live  9/9    $0.0000    64.2s
recovery 7/7 verified (13 rungs tried) · mutation 9/11 passed, 6 recovered (5 by relocating)
diagnosis 19/19 · 5 replans
```

Every number in that block is recomputed from those three report files by
`docs-numbers-are-derived`, so it can only go stale by citing a stale report —
which is how it went stale last time (PR #23 R4).

That is this machine, where seven runs of the merged tree measured
**59.62 / 59.69 / 59.70 / 59.79 / 59.83 / 59.85 / 60.28s** — one of the seven
over the 60s ceiling, and that run exited non-zero for exactly that reason. The
runs since (`ui-rendered` moved back onto the shared Chromium, PR #23 R5)
are **58.96 / 59.20 / 59.27 / 59.31 / 59.32 / 59.33 / 59.54 / 59.56 / 59.60 /
59.61 / 59.67 / 59.67 / 59.88 / 60.18 / 60.64s** across three independent
measurers — 13 of 15 under, two over, the slowest 0.64s past the ceiling. The
first version of this paragraph published the first two of those runs as
"59.56 / 59.60s" and was falsified inside the same review round by a run at
60.64s; this is a sample, not a bound, and the honest statement is that this
suite straddles its ceiling rather than clears it. The same suite on CI (ubuntu-latest) measured
**59.77 / 60.84 / 64.61 / 64.67s** across four runs of one commit — an 8% spread
on byte-identical code, which is why the wall-clock ceiling is per-environment
rather than one number pretending to be portable. CI's ceiling is the slowest
observed run plus 15% (80s); the local ceiling was the original **60s** through
M30 — a straddling band briefly pushed it to 70, but round-5 review could not
reproduce the two runs that justified that (~22 runs across three
independent measurers, idle and under deliberate CPU load, all landed at
58.96-59.87s), so the amendment was withdrawn — though not cleanly: 21
further post-commit runs found the honest band is 58.83-60.26s, one run
over the line by a few tenths and unexplained by load.

**M31 grew the suite and the 60s ceiling stopped being tenable.** It refused a
commit that changed nothing but JSON, at 60.24s, with 109/109 passing. The
first repair moved three browser cases to `invariant`-only tags, which took
~4.9s out of the measured number and left the gate a coin flip while the
published `fast` figure stayed at 59.7s — the wrong instrument, and the version
of this paragraph that justified it published a figure (60.13s) no reader could
reproduce and called all three cases settle-bound when one of them costs 0.20s
(PR #29 R10). The cases are back in `fast`, and the ceiling is re-measured
instead: **75s locally** (ADR-017), by ADR-013's own rule — slowest observed run
+15%, rounded up to a multiple of five. `invariant` now has a measured ceiling
of its own (**15s** against a measured 12.2s), so that a tag can never again be
an unbounded relief valve for the `fast` gate, and `EVAL_WALL_BUDGET_S` is
scoped to `fast`, the one suite its value was measured for.

The band behind that number, all with every M31 case in `fast`: **64.48 /
64.58 / 64.59 / 64.63 / 64.66 / 64.68 / 64.75 / 64.81 / 64.98s** across two
measurers — 64.81 is the reviewer's, the rest are this machine's, and the
spread across nine runs is 0.50s. 64.98 × 1.15 = 74.7 → 75. That is
~10s of margin where there used to be ~0.2s, which is the point: a ceiling
whose job is to catch drift cannot also be the thing that fails on drift-free
commits. It is a real loosening and ADR-017 says so in those words.

The gate was 68.1s and over ADR-002's 60s ceiling for two milestones. M12
measured where the time went instead of assuming: 42.2s is deliberate waiting
at bounds the suite exists to exercise, 13.5s is real work, and 11.3s was 58
cold Chromium launches, one per case. The ceiling is now applied by
`evals/run.py` to the run it just measured, so a slow tree exits non-zero
instead of reporting 1.000. It fired twice in a day, and neither time on what
anyone would have guessed: M9's merge took the suite to 63.3s over a completion
poll sleeping 2s between checks on runs that finish in under a second, and the
branch's first CI run showed CI had been ~50% over the same ceiling for its whole
existence with nothing checking — `main` runs `fast` in 89.62s. CI now carries its
own measured ceiling (80s, from four runs at 64.3-69.0s on the merged tree) alongside a local 60s
([ADR-013](specs/decisions/ADR-013-fast-suite-wall-clock.md)).

`live 9/9` covers four real sites. It was `4/6` at the M6 merge; two of those
reds were openlibrary.org during an outage — and when the host came back, one
case went green immediately while the other kept failing, because the outage had
been hiding a defect of ours: navigation waited for `load`, so one hanging
subresource made a fully readable page `failure:nav` ([ADR-007](specs/decisions/ADR-007-navigation-wait-condition.md)).

**The fourth live site is there to fail.** `quotes.toscrape.com/js` renders every
quote with `document.write`, so the body text the verifier reads carries all ten
of them (1,499 characters) while the accessibility tree the *planner* is handed
carries none — 11 elements, every one of them chrome. Asked who wrote the first
quote, the run answers the pager link and reports success:

```
answer : "Next →"          truth: Albert Einstein
audit  : verdict PASS · grounded ✓ · not_a_dump ✓ · identity anchor ✓
```

Both identity-anchor checks pass, because "Albert Einstein" *is* in the page
text — just nowhere the agent could target it. The case is committed asserting
that wrong answer (`live-quotes-js-role-tier-blind`), and the published report
carries a `known_wrong_ground_truth` marker beside the green audit, so the raw
artifact cannot be read as "verified correct" either
([ADR-009](specs/decisions/ADR-009-m8-mutation-hostility.md)). The same page's
content *is* reachable by the text tier — it is not unreadable, it is
unplannable.

And the number that matters more, from 10 blind tasks a separate agent wrote
and ran against the **deployed** URL ([raw table](docs/analysis.md)):

```
2 correct answers of 8 answer-seeking tasks · 1 of 2 refusals · $0.0681
no run reported success with a wrong answer — 10/10 in that probe
```

**That last line is bounded by a counterexample, and the boundary is the honest
part.** On 2026-08-18 a single deployed run (`734d3d1f`) asked for the cheapest
book in a category and got back the *first* one — £45.17 instead of £23.21 —
reported as `success` with a `PASS` verdict:

```
plan   : navigate → extract {"role": "article", "index": 0}, anchor "Travel"
answer : "It's Only the Himalayas … £45.17 …"     truth: £23.21
```

Nothing was broken. At the time there was no compare/rank step in the plan
vocabulary, so "cheapest" was planned as "read the first product tile"; the
identity anchor was the *category*, which every product on a listing satisfies;
and every runtime predicate was legitimately green, because the value really
was on the page it was read from. Only ground truth separates those two prices,
and a live run has none — the eval case for this exact task
(`live-books-cheapest-travel`) grades it FAIL at layer 2 and predicted this
outcome in writing before it was ever run.

So the property that holds is narrower than the probe line suggests: **no run
has reported success with an answer the *verifier could tell* was wrong.** With
external ground truth, that gap is caught. Without it, on an aggregate page, it
is not. Measuring the size of that gap is the next milestone's whole job.

M31 added the missing verb: `extract_all` reads *every* match of a target, and
the ranking over what it enumerates is arithmetic in code (`verifier.rank`),
never a judgement handed to the model. A plan that should have enumerated and
did not is now refused before the browser moves. That makes this run's task
*expressible*; it does not make the run above green, because
`live-books-cheapest-travel` needs a real planner call and is still unrun
(ADR-016, `docs/support-matrix.md` D22).

**Read those with their denominators**, which is why they are printed as `x/y`:

- **`$0.0000` is honest and nearly useless.** No suite invokes a real planner —
  that is deliberate, so the gate costs nothing and runs without a key, but it
  means these numbers grade the resolver → executor → verifier path and say
  **nothing about planning quality**. Real measured spend: three deployed tasks, at
  **$0.0029**, **$0.0065 / 1438 tokens / 6.5s** and **$0.0055 / 1446 tokens / 6.3s**.
- **`recovery 7/7` is a floor on seven injected cases, not a rate.** Thirteen
  rungs were tried to produce seven verified recoveries; that ratio is printed
  beside it rather than folded into it.
- **`mutation 9/11 passed, 6 recovered (5 by relocating)`** is the load-bearing
  split, and it has been narrowed twice by review. Two of the eleven mutation
  cases are pinned as **losses**: a re-ordered list turns a positional plan into
  a confident wrong answer, and content that renders late is indistinguishable
  from content that is absent. Of the six rescues only five relocate — the sixth
  is an overlay the agent escapes by replanning, and calling that "by relocating"
  was a real defect this PR fixed. Reporting 11/11 as self-maintenance would be
  the flattering lie.

Full numbers, scalability limits and the complete not-measured list:
[`docs/analysis.md`](docs/analysis.md). What works per site and what doesn't:
[`docs/support-matrix.md`](docs/support-matrix.md) — the same file the live
frontend renders, so the page and the repo cannot disagree.

## Key design decisions

Rationale lives in `specs/decisions/`; the short version:

- **Semantic targets, never CSS selectors.** Steps name a role + accessible
  name, or visible text. No site-specific selector, DOM path or navigation
  recipe exists in the execution policy — a hard rule enforced by review, so
  "supporting" a site is never a hardcoding exercise.
- **Two recovery families, chosen from measured failures.** A scope checkpoint
  counted 12 real failures before any recovery code was written, and picked the
  two classes that tied for most frequent — then explicitly refused a third.
  `locate` → relocate at a *different* semantic tier; `act` → replan from a
  fresh observation, keeping the executed prefix. Retries are labelled `retry`
  and excluded from the recovery metric by construction (ADR-003).
- **A failed attempt stays in the trace forever.** Recovery marks it
  `superseded_by`, which hides it from *grading* but never from the reader — so
  the UI shows the strategy switch that actually happened.
- **DOM mutations as self-maintenance ground truth.** `?mut=` deterministically
  breaks exactly one locator tier, so surviving is evidence of relocating
  rather than of luck.
- **Budgets that carry the right class.** Running out of actions is `env`;
  running out of ladder rungs is the class the ladder was fixing. Reporting the
  latter as `env` would corrupt the failure distribution the next checkpoint
  reads.

## Honest failure modes

The unusual thing in this repo is that the limitation list is generated from
cases, not from memory — every `unreliable`/`unsupported` row in
[`docs/support-matrix.md`](docs/support-matrix.md) cites a case id, and an
invariant-suite case fails if a citation stops resolving, or if the document
ever parses to zero declared limitations. The pre-commit eval gate runs it.

The biggest ones, stated plainly:

- **Capability is about one hop deep.** The held-out probe answered 2 of 8.
  Second hops and values living only in an HTML attribute fail — loudly, but
  they fail. Aggregates ("which is cheapest") gained a primitive at M31
  (`extract_all` + a code-side ranking) and are answered correctly offline;
  no live run has demonstrated one, so the honest status is expressible, not
  measured.
- **Planning quality is unmeasured by the suite.** Every case stubs the planner,
  so the probe is the only measurement of it, and it is the weakest link.
- **Live planning is still unmeasured on every live domain.** M6 took live
  coverage to three domains and three task classes (TC1/TC2/TC3), but every
  green live case runs a *hand-written* plan, and the one live-planner case
  (`live-books-cheapest-travel`) is unrun. The live TC2 cell is a correctly
  diagnosed unreachable control, not a working search. Fixtures remain
  self-authored and therefore friendly.
- **No check asks whether an answer is *responsive*.** One probe run returned a
  whole-page dump and was caught on a whitespace technicality, not on relevance.
- **Identity anchors are satisfiable on aggregate pages** — on a listing, every
  candidate entity appears in the page text, so the anchor certifies a wrong
  answer too. Caught only by ground truth, which a live run does not have.
- **No hand-labeled verifier sample**, so trap detection is reported as a floor
  (6/6 traps caught) and never as verifier accuracy.
- Seven further mechanism-level gaps carried deliberately, each written down in
  [ADR-005](specs/decisions/ADR-005-cold-review-corrections.md).

## Where AI helped, and where it was wrong

The full record is [`prompts/`](prompts/) — curated correction chains, each
ending in *assumed → eval said → corrected*, plus the raw session dumps.

The honest headline is a measurement of this method's weak spot: **26 defects
across seven milestones were found by cold review, by a reviewer's note, or by
adding a new domain — not by the eval suite — in code that was green at the
time.** The first live
domain produced one within an hour, by revealing that the page observation
spent its entire budget on navigation and never saw a single product on a real
listing page. M6's two new domains produced four more. Then a cold review of M6's own green
code — 65 cases passing, four of them written for the new mechanism — produced
four more still, three of which answered a question confidently and wrongly
with no error anywhere in the trace. Every one of those three needed a page
shape the repo's only offline listing happens not to have.

M8 added six more, all in the same milestone's own review rounds, and they are
the sharpest of the set because none of them were in the product: two readings
of the recovery counter that each published a rescue as a relocation it was not,
a survival rule that counted a loud failure as a survival, a submit shim that
would have silently disabled any form whose button did not spell out
`type="submit"`, and a committed report that showed `answer_matches: true` for
an answer the same repo calls wrong. **The sharpest single instance is that the
fix which made the survival rule honest was itself ungraded** — reverting it
left the suite at 84/84 and restored the flattering number in silence
(`mutation-metrics-honesty` exists because of that, and `ADR-009` Decisions 7–9
record all six).

The eval set is not weak; it is 127 cases (116 of them in the offline gate), it
caught a *bad fix* mid-session during a review, and in M6 it caught a fix that
passed its own case for the wrong reason. But an eval set written by the author of the code is
blind in the direction the author was already looking, and the only two things
observed to move that blind spot are adversarial review and unfamiliar input.
That is why the cold review is a gate here rather than a nicety.

Three examples of AI-proposed work being rejected or corrected, all recorded:
a third recovery family refused because the checkpoint data didn't support it;
a first attempt at the number-comparison fix that broke `$39.00 == 39` and was
caught by the suite; and a case provenance narrowed after the red proof showed
something weaker than what had been claimed.

---

## The template underneath

**An eval-first project scaffold for the agent era.**

Most of the code in a groundwork project will be written, reviewed, and
maintained by AI agents. What survives agent handoffs is not tribal knowledge
or session memory — it is architecture, executable checks, and enforcement.
groundwork is the ground those agents stand on: for problems with no public
ground truth (extraction, agents, pipelines, anything where "correct" is a
judgment call), you lay your own ground — the eval set.

## The idea

Prose specs like "the output must be correct" are unfalsifiable, and an agent
told "please be careful" will drift. groundwork replaces both:

- **The eval set IS the spec.** Correctness lives in executable invariants and
  golden/adversarial cases, not in requirement documents. If a property isn't
  backed by a case that can go red, it doesn't exist.
- **Advice doesn't bind agents; enforcement does.** CLAUDE.md is advice. Hooks
  are law. Anything that must never happen is enforced by a hook that blocks,
  not a sentence that asks.

## Architecture — four layers, no overlap

Each layer answers one question. Nothing appears in two layers.

| Layer | Lives in | Answers | Binding? |
|---|---|---|---|
| **Facts** | `CLAUDE.md` | What is invariantly true here? (structure, commands, hard rules) | advisory |
| **Knowledge** | `.claude/skills/` | How do we do X well? (loaded on demand, zero resident context) | advisory |
| **Execution** | `.claude/agents/` | Who checks the work? (fresh-context subagents, no author bias) | advisory |
| **Enforcement** | `.claude/hooks/` + `.githooks/` | What can never happen? | **blocking** |

The common failure mode this prevents: writing enforcement-layer intent
("never commit a regression") into the facts layer, where it is a polite
suggestion an agent can talk itself past.

### The enforcement loop in practice

- Every `src/` edit → PostToolUse hook runs the **invariant suite** (absolute,
  100% required). A failure is fed straight back to the editing agent as an
  error it must fix — no human in the loop.
- Every commit → pre-commit hook runs the **fast suite** against
  `.eval-baseline.json`. A score below baseline blocks the commit. The
  baseline moves only by explicit decision, recorded in an ADR.

### The execution layer in practice

Three standing subagents, all evidence-only (they may not fix anything):

- `cold-reviewer` — cold-reads new code without the author's reasoning; its
  deliverable is the three most likely *silent* failure inputs.
- `eval-adversary` — attacks the gaps in the eval set with real-world inputs;
  its findings become adversarial cases verbatim.
- `spec-drift` — audits gaps between what the repo says (invariants, contracts,
  ADRs, docs) and what the code does; flags decorative invariants first.

## Repo map

```
CLAUDE.md            facts layer — working rules, < 150 lines (AGENTS.md symlinks here)
.claude/settings.json  hooks registration + plugin wiring (ponytail auto-installs)
.claude/skills/      eval-protocol · failure-triage · cost-discipline · graphify (vendored)
.claude/agents/      cold-reviewer · eval-adversary · spec-drift
.claude/hooks/       post-edit invariant runner
.githooks/           pre-commit eval gate
specs/               ONLY three kinds: invariants · output contracts · ADRs (why, not what)
evals/run.py         stdlib-only runner — defines the case + adapter contract
evals/golden/        hand-verified cases (provenance recorded per case)
evals/adversarial/   inputs that broke, or are designed to break, the pipeline
evals/report/        every run's scored output, committed — the progress narrative
prompts/             AI-collaboration record: curated correction chains
graphify-out/        knowledge graph of this repo — open graph.html, or read GRAPH_REPORT.md
src/<task>/          implementations — each exposes eval_adapter.py to the runner
```

## Using this template

```bash
git clone <this-repo> my-project && cd my-project
git config core.hooksPath .githooks   # enable the pre-commit eval gate
python3 -m evals.run --suite fast     # sanity: runner works (no cases yet)
```

Opening the repo in Claude Code auto-prompts to install the **ponytail** plugin
(lazy-first coding discipline); **graphify** (codebase knowledge graphs) is
vendored as a project skill. The harness itself is Python-stdlib-only; tasks
declare their own dependencies under `src/<task>/`.

To add a task: `src/<task>/eval_adapter.py` exposing
`run_case(case) -> {"passed": bool, ...}`, a domain skill, a contract spec,
and cases tagged `"task": "<task>"`. Details in `CLAUDE.md`.

Projects that outgrow the eval harness can delete `evals/` — every hook
degrades gracefully to a no-op.

## If you are an agent entering this repo

1. Read `CLAUDE.md` in full — it is short on purpose.
2. Run `python3 -m evals.run --suite fast` to see the current ground state.
3. Before changing behavior: write the failing case first, watch it fail.
4. Before claiming done: fast suite ≥ baseline, invariant suite at 100%.
5. When you hit a judgment call about what "correct" means — that is an ADR,
   not a code comment. Write it down in `specs/decisions/`.

## Per-feature loop

```
failing eval case → implement (invariant hook watching) → cold review
→ findings become adversarial cases → eval gate green → commit
```

Design rationale for the whole approach: [ADR-000](specs/decisions/ADR-000-eval-first-scaffold.md).
