# 015 — After the probe regression: MCP, tool-calling loops, and what actually limits completion

**Date**: 2026-08-22 · **Milestone**: between M10 (A-freeze, PR #25) and the
post-freeze queue · **Outcome**: a design discussion, not code. Three hypotheses
from the owner — (1) wrap the executor as MCP tools and let the planner
tool-call, (2) progressively disclose capabilities to cut planner tokens,
(3) add an executor/debater agent beside the planner — were each checked
against the code and the committed probe data, and each came back pointing at
a different, smaller change. Result: three Queue blocks (M31 plan lint +
`extract_all`, M32 observation drill-down, M33 tool-calling ablation arm) and
no architecture change. `tasks/TODO.md`.

## Context

The trigger was one line in [PR #25](https://github.com/HaoweiChan/browser-agent/pull/25)'s
"Important failures discovered":

> 3. **Correct-answer rate regressed: 2/8 (25%) at M5 → 1/7 (14%).** The
> A-plan's goal was ≥2×. Published raw and unexplained rather than shaded.

The A-plan had set "≥2× the 2/8 baseline" as the correct-answer goal for the
second held-out probe. The probe came back at 1/7, and on top of that the
inviolable property was violated (task #3, "which author has the most
quotes", answered with the page `<title>` and graded PASS). PR #25 fixed the
violation with a verifier-side guard that fails closed on superlative
questions without ground truth — and declared the cost, D22: it now refuses
some questions a single extraction would have answered correctly.

So the question the owner brought was the right one: *is the planner the
bottleneck, and is its architecture — one chat completion that emits a JSON
plan, no MCP client, no tool-calling loop — the reason completion is low?*

## The prompt (verbatim, condensed)

> 讓我理解現在的 A-level solution 是怎麼實作的。看起來 Planner 收到 task /
> start URL / page observation / replan 時的 failure note，然後直接 call
> OpenRouter chat completion，要求模型吐固定 schema 的 JSON steps。它沒有 MCP
> client，也沒有 tool-calling loop。**但這樣它對於能完成的指令是完全清楚的嗎？
> 還是要憑 planner 能力去拼完成度？如果我們把各種 tools 包裝成 MCP 然後讓
> planner 去使用，會不會更好？**

> 那 planner 會不會每次重複讀到同樣的 prompt？如果**漸進式披露**能做的事情，
> 能否減少 planner 的 token 消耗且增加完成度？另外只有 planner 嗎？他是不是有
> 指派的 executor，或甚至我們可以有一個人**跟他辯論**該做什麼事情？我想在面試
> 時能講到進階的 agent 掌控手法，像 loop engineering、graph engineering，有沒有
> 能導入的部分，像是 **LangGraph**？

## What the code and the data said

Read before answering: `src/browser/planner.py`, `agent.py`, `observe.py`,
`verifier.py` (PR #25 branch), `docs/architecture/task1-overview.md`,
`docs/analysis.md` §8a-2.

**Is the planner clear about what it can do?** Yes, by construction. The
system prompt *is* the capability list — 4 actions, 5 target keys, 3
`expected_state` shapes — and the executor is closed-world: an unknown action,
target key, or expected_state key is a `StepError("task", …)`, never a silent
downgrade (`resolver-unknown-target-key`). The planner cannot believe it can
do something the executor cannot. What it cannot do is *express* comparison:
there is no enumerate / filter / rank step, so "cheapest" was planned as
"read article 0" (`734d3d1f`, `live-books-cheapest-travel`) and "most quotes"
as "read whatever is first" (probe #3). PR #25's own guard comment says it in
one clause: *"the plan vocabulary has no comparison primitive to have gotten
it right WITH."* The gap is vocabulary, not protocol.

**Would MCP help?** MCP is transport. Planner and executor live in one
process and the step schema is already typed; an MCP server in between adds a
JSON-RPC hop and an SDK, and OpenRouter's chat completion does not consume
MCP — the tool list would still have to be turned into `tools=[…]` by hand.
The only honest reason for an MCP server here is to let an *external* agent
drive this executor, which is a different product. The real question hiding
under "MCP" is **tool-calling loop (LLM-per-step) vs plan-then-replan** —
which is the A-vs-B table in `docs/architecture/task1-overview.md`, decided
on reasoning at M0 and never measured.

**Does the planner re-read the same prompt?** Yes: ~524 tokens of system
prompt per call, and the observation is re-sent on replan. Measured cost of a
planning call is ~1,440 tokens / ~$0.006 (`cd7121fc`, `734d3d1f`); the whole
second probe was 24,641 tokens for 20 runs. Prompt caching cannot even apply
(Anthropic's floor is 1,024 tokens). Tokens are not the bottleneck; 1/7 is.

**Progressive disclosure of capabilities?** Backwards at this size: it would
save under 100 tokens and reintroduce "the planner did not know X existed."
What *is* under-disclosed is the page — `observe()` caps at `MAX_ELEMS=60`,
`text_head=300`, and probe #4/#5/#7 all had the correct value verbatim in
the page text the agent captured but absent from the elements the planner was
shown; `live-quotes-js-role-tier-blind` is "readable but unplannable" for the
same reason. Progressive disclosure of the *observation* is the version of
this idea that maps onto a committed failure.

**Is there only a planner?** The LLM is the planner and nothing else.
Resolver, executor, classifier, recovery ladders and OutcomeVerifier are all
pure code — deliberately, so that verification is structural, not
behavioral, and the fast suite stubs one boundary at $0. A debating LLM critic
would catch "this plan has no comparison step," but it has no more ground
truth than the planner, and it would turn the offline gate into two stubbed
LLMs. The same catch is one deterministic line: task matches the superlative
shape (the regex PR #25 already shipped) and the plan has no enumerating step
→ reject before the first action and replan with a note. Rule 6 holds (no site
knowledge), the fast suite stays $0, and there is already a red case for it.

**LangGraph?** `run_task` already is a state graph written as control flow —
nodes screen → navigate → observe → plan → resolve → act → postcondition;
edges labelled by `classify()`'s seven failure classes; cycle budgets
`MAX_FIXES` / `MAX_REPLANS` / `RUN_BUDGETS` with every exhaustion classified
(INV-3); cycle detection in the no-progress replan guard (identical plan,
re-issued step, dropped action with no page change); state persisted as the
evidence pipeline (`trace.jsonl`, SSE, verifier input). LangGraph would give
the same graph as a library plus checkpointing and human-in-the-loop
interrupts, at the cost of a dependency and rewiring every stub injection
point the fast suite depends on. The interview line is not "we didn't use
LangGraph"; it is "here is our graph, here is why its edge labels are
failure classes and not model decisions, and here is what that buys in
offline evaluability."

## The resulting decision

Three Queue blocks, each tied to a committed failure rather than to the
hypothesis that prompted it:

- **M31 — plan lint + `extract_all`.** The planner-side half of PR #25's
  verifier guard: a superlative task whose plan has no enumerating step is
  rejected before any action and replanned with a note; `extract_all` is
  the one primitive that lets the replan land. Rank/count stays in code.
  Depends on M10 merging (it amends the guard and re-measures D22).
- **M32 — observation drill-down.** One `observe` action scoped to a
  subtree, through the existing replan path. Disclosure of the page, not
  the tools.
- **M33 — tool-calling ablation arm.** OpenRouter-native `tools=[…]` with
  the same four schemas, one call per step, behind the unchanged planner
  boundary, driven by M9's `evals/ablation.py` against the deployment.
  A-vs-B gets a number; an ADR then keeps B or amends the table.

**Accepted / rejected / modified.** MCP as transport — rejected, with the
reason recorded. Progressive disclosure — modified: applied to the
observation instead of the capability list. A debater agent — modified: its
one useful catch became a deterministic lint. LangGraph — rejected as a
dependency, accepted as the vocabulary for describing what is already there.
Per-step tool-calling — neither accepted nor rejected: it becomes a measured
ablation arm, because the table that chose B had never been measured.

## Assumption → Eval contradiction → Correction

- Assumed: the planner is not fully aware of what the executor can do, so
  some of the 6/7 misses are the planner guessing at capabilities; a tool
  catalogue (MCP) would close that.
  Eval said: the misses in `docs/analysis.md` §8a-2 are `failure:locate`
  (#1, #5, #6), page-text dumps (#4, #7) and one wrong-but-PASS aggregate
  (#3). None is an unknown-action or unknown-key failure — the closed-world
  executor would have graded those `failure:task`, and zero did. The one
  category the planner provably cannot express is comparison
  (`live-books-cheapest-travel`, probe #3), and it is a missing verb, not a
  missing catalogue.
  Corrected: M31 adds the verb (`extract_all`) and a lint that refuses a
  plan without it; no MCP.
- Assumed: the planner wastes tokens re-reading the same system prompt, and
  progressive disclosure would both save tokens and raise completion.
  Eval said: ~524 tokens of prompt per call, ~1,440 tokens per planning call
  measured (`cd7121fc`, `734d3d1f`), 24,641 tokens for the entire 20-run
  probe — under Anthropic's caching floor and under 1.5% of the 100k run
  budget. Meanwhile three probe tasks (#4, #5, #7) had the answer in captured
  page text the planner was never shown, and `live-quotes-js-role-tier-blind`
  is committed as "readable but unplannable."
  Corrected: disclosure goes the other way — M32 lets the planner ask for
  more of the page; the capability list stays fully disclosed.
- Assumed: the A-vs-B architecture table in
  `docs/architecture/task1-overview.md` settles whether a per-step
  tool-calling loop would do better.
  Eval said: nothing — that table was written at M0 from reasoning, and no
  committed report measures architecture A on this eval set. ADR-010's
  ablation, the only planning-quality measurement in the repo, varies the
  model and nothing else.
  Corrected: M33 makes it a measured arm behind the same planner boundary;
  the ADR that follows is written from its numbers.
