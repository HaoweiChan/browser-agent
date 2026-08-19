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
python3 -m evals.run --suite fast        # offline gate: 73 cases, zero paid calls
python3 -m evals.run --suite invariant   # must-always-hold, no LLM, no network
python3 -m evals.run --suite live        # 6 cases, 3 real sites, still $0.00
```

The reviewer UI locally — task submission needs `OPENROUTER_API_KEY`; the
guards, matrix and browser smoke test work without one:

```bash
python3 -m uvicorn src.browser.server:app --port 8099
```

## Where it stands

Latest offline baseline — `evals/report/20260817-133237-fast.json`:

```
fast  69/69    invariant  18/18    live  4/6    $0.0000    36s
recovery 3/3 verified (8 rungs tried) · mutation 4/4 passed, 2 by relocating
diagnosis 12/12 · 3 replans
```

`live 4/6` is not a regression: both reds are openlibrary.org, which stopped
responding entirely partway through M6 and fails `failure:nav` at page load.
The two greens on the other two live domains ran in the same suite.

And the number that matters more, from 10 blind tasks a separate agent wrote
and ran against the **deployed** URL ([raw table](docs/analysis.md)):

```
2 correct answers of 8 answer-seeking tasks · 1 of 2 refusals · $0.0681
no run reported success with a wrong answer — 10/10
```

**Read those with their denominators**, which is why they are printed as `x/y`:

- **`$0.0000` is honest and nearly useless.** No suite invokes a real planner —
  that is deliberate, so the gate costs nothing and runs without a key, but it
  means these numbers grade the resolver → executor → verifier path and say
  **nothing about planning quality**. Real measured spend: one deployed task at
  **$0.0029** and **$0.0065 / 1438 tokens / 6.5s**.
- **`recovery 3/3` is a floor on three injected cases, not a rate.** Eight rungs
  were tried to produce three verified recoveries; that ratio is printed beside
  it rather than folded into it.
- **`mutation 4/4 passed, 2 by relocating`** is the load-bearing split. Only one
  of the three DOM mutations breaks a locator tier a plan was actually standing
  on; the other two pass without recovering anything. Reporting 4/4 as
  self-maintenance would be the flattering lie.

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
  Second hops, aggregates ("which is cheapest"), and values living only in an
  HTML attribute all fail — loudly, but they fail.
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

The honest headline is a measurement of this method's weak spot: **18 defects
across six milestones were found by cold review or by adding a new domain —
not by the eval suite — in code that was green at the time.** The first live
domain produced one within an hour, by revealing that the page observation
spent its entire budget on navigation and never saw a single product on a real
listing page. M6's two new domains produced four more. Then a cold review of M6's own green
code — 65 cases passing, four of them written for the new mechanism — produced
four more still, three of which answered a question confidently and wrongly
with no error anywhere in the trace. Every one of those three needed a page
shape the repo's only offline listing happens not to have.

The eval set is not weak; it is 81 cases, it caught a *bad fix* mid-session
during the last review, and in M6 it caught a fix that passed its own case for
the wrong reason. But an eval set written by the author of the code is
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
