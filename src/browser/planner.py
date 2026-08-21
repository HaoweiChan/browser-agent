"""Planner: NL task -> typed steps (docs/architecture/task1-overview.md, D9).

A planner is `async (task, url) -> (steps, usage)` where usage is
{"llm_tokens": int, "llm_usd": float}. The eval fast suite injects
`stub_planner` at this boundary — zero LLM calls (cost-discipline rule 4);
the live OpenRouter planner is exercised by the CLI, the gateway, and the
`full` suite.
"""

import asyncio
import json
import os
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5.6-luna"

# --- M9 cost/model ablation (specs/decisions/ADR-010-m9-model-ablation.md) ----
#
# Two lists, because they answer two different questions and conflating them cost
# the default its own endpoint once already (owner spec change, 2026-08-20):
#   ABLATION_MODELS — what the ablation RUNS. Owner-selected: popular on
#     OpenRouter and within a price ceiling the owner set.
#   ALLOWED_MODELS  — what `POST /tasks` ACCEPTS. The ablation set plus the
#     incumbent default, which must stay reachable by explicit name even though
#     it is priced out of the comparison.
#
# Selection is the owner's, on two stated criteria: entries from OpenRouter's
# usage leaderboard (which measures adoption, not quality — the page says so, and
# ADR-010 Decision 2 quotes it), capped at what `CEILING_MODEL` lists for.
# Every id was read from https://openrouter.ai/api/v1/models (no key needed) and
# frozen with its prices in evals/labels/openrouter-models-20260820.json; the
# allowlist is pinned against that snapshot, and the ceiling is enforced from it,
# by gateway-model-reaches-planner. A typo'd id is a run that fails at spend time.
# The ceiling is the MODEL, not a number (owner ruling, 2026-08-20). No price
# literal lives here, and that is a fix rather than a style choice: the previous
# version hard-coded this model's list price and it drifted 11% inside one working
# session, leaving code, an ADR, a support-matrix row and §9 all quoting a figure
# the provider had stopped charging (PR #15, R16). The effective ceiling is
# derived from the frozen snapshot's entry for this id — one source of truth, and
# nothing to hand-raise. (The snapshot cannot be read from here: `evals/` is
# .dockerignored, so a production import of it would break the image.)
CEILING_MODEL = "deepseek/deepseek-v4-pro"

# The default until 2026-08-21, replaced by the ablation's own pick. Named here
# rather than deleted because ADR-010 Decision 6 excluded it on price, and an
# exclusion whose subject has no name cannot be re-checked when prices move.
SUPERSEDED_INCUMBENT = "anthropic/claude-sonnet-4.5"

ABLATION_MODELS = [
    CEILING_MODEL,                        # the ceiling itself
    "openai/gpt-5.6-luna",
    "tencent/hy3",
    "deepseek/deepseek-v4-flash-0731",    # cheapest, and most-used model on OpenRouter
]

# The default is now one the ablation MEASURED, which is the whole point of M9
# and reverses the arrangement this file shipped with. Until 2026-08-21 the
# default was `anthropic/claude-sonnet-4.5`: over CEILING_MODEL on both prompt and
# completion, therefore ablated by no cell, therefore unable to stay the default
# on cost grounds alone whatever the numbers said (ADR-010 Decision 6). The
# numbers are now in (ADR-010 Decision 16, `docs/analysis.md` §9) and the
# pre-committed rule in Decision 5 picked the replacement: every candidate scored
# the same correctness, so the tie fell to cost, and this is the cheapest cell.
#
# No figures here — the comment above says why, and the multiples an earlier draft
# quoted went stale inside a session (PR #15, R23). The snapshot carries the
# numbers; gateway-model-reaches-planner derives the comparison from it.
#
# The superseded incumbent stays in the frozen snapshot on purpose: it is the
# evidence for Decision 6's exclusion, and dropping it would delete the reason
# the default moved. It is NOT in the allowlist any more — a public endpoint
# should not accept a model this system deliberately stopped paying for.
#
# dict.fromkeys, not a set: the default is also an ablated model now, so the two
# lists overlap, and order is the display order §9 and the ADR both use.
ALLOWED_MODELS = list(dict.fromkeys([DEFAULT_MODEL, *ABLATION_MODELS]))

SYSTEM = """You are a browser-automation planner. Emit ONLY a JSON array of steps.
Each step: {"action": "navigate|click|fill|extract",
 "target": {"role": str|null, "name": str|null, "text": str|null, "near": str|null, "index": int|null} | null,
 "value": str|null,
 "anchor": str|null,
 "expected_state": {"url_contains": str} | {"text_visible": str} | {"role_visible": {"role": str, "name": str|null}} | null}
Rules: `navigate` puts the URL in `value`. `extract` reads the target element's
text as the answer. Targets are semantic (ARIA role + accessible name) — never
CSS selectors. `index` (0-based) picks the k-th match when several elements
share a role, e.g. the first search result. `near` picks the match closest to a
visible string instead of counting: use it when the element you want has no name
of its own but sits beside one that does — a price beside a product, a value
beside its table label, an author beside a byline. Prefer `near` over `index`
when such a string exists; only these five target keys exist, and any other key
fails the run. On an `extract` step, `anchor` is
the distinguishing name of the entity the task is about; the run fails if that
string is absent from the page the answer was read from — use it whenever the
task names a specific entity. Prefer few steps.
Every `click` MUST carry an expected_state — a click that changes nothing you
can check is a click nobody can verify, and the run will be failed for it.
Pick the cheapest checkable consequence: a URL fragment, or a role+name that
becomes visible. All keys you give must hold, so assert one thing you are sure
of rather than two you are hoping for. `fill` verifies itself by readback and
needs no expected_state. If a click's consequence genuinely cannot be known
from the observation, prefer a different plan over a guess — never invent
expected text.
When a page observation is provided: the browser is ALREADY on that page — do
not re-navigate unless the task needs a different page, and target ONLY roles/
names present in the observation. Output the raw JSON array only — no markdown fences, no commentary."""


class PlanError(Exception):
    """The MODEL did not produce a plan — as distinct from the call failing.

    This type is the only thing in the system that means "the response arrived
    and was not a plan", so it is the discriminator every layer above uses
    instead of pattern-matching an error message (PR #15, R9).

    It carries `usage` because the provider bills a completion whether or not it
    parses. A model that answers with prose is charged for the prose, and a cost
    table that drops those calls under-reports exactly the runs it exists to
    find (PR #15, R10)."""

    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage or {"llm_tokens": 0, "llm_usd": 0.0}


def parse_plan(content: str) -> list:
    """Model output -> list of steps. Raises PlanError on non-plan output.

    Tolerates markdown code fences (real production variance: adversarial case
    planner-fenced-json, run 5a52f0aa)."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        steps = json.loads(text)
        assert isinstance(steps, list)
        return steps
    except Exception as e:
        raise PlanError(f"planner returned non-plan output: {e}: {content[:200]}")


def stub_planner(plans: list):
    """Deterministic planner for the fast suite: one plan per call, in order.

    A sequence rather than a single plan because M3 replans: a case that injects
    a bad first plan has to be able to say what the replanner comes back with.
    The last plan repeats, so a case that never replans still just gets its one
    plan — and a replan that returns the same steps is caught by the agent's
    no-progress guard rather than looping.
    """
    calls = [0]

    async def plan(task: str, url: str | None, observation: dict | None = None, note: str | None = None):
        steps = plans[min(calls[0], len(plans) - 1)]
        calls[0] += 1
        return steps, {"llm_tokens": 0, "llm_usd": 0.0}

    return plan


def live_planner(model: str = DEFAULT_MODEL):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise PlanError("OPENROUTER_API_KEY is not set")

    def _call(payload: dict) -> dict:
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)

    async def plan(task: str, url: str | None, observation: dict | None = None, note: str | None = None):
        user = f"Task: {task}\nStart URL: {url or 'none — choose one via navigate'}"
        if observation:
            from .observe import render

            user += "\n\nCurrent page observation:\n" + render(observation)
        if note:
            # Replan: the previous attempt and why it failed, plus the page as
            # it actually is now. Plan the REMAINING work from here — the steps
            # already executed are not re-issued.
            user += (f"\n\nA previous attempt failed: {note}\n"
                     "Plan only the steps still needed from the page above.")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "usage": {"include": True},
        }
        data = await asyncio.to_thread(_call, payload)
        # Usage first: this completion is billed whatever it contains, and
        # building it after `parse_plan` meant a prose answer threw its own cost
        # away (PR #15, R10).
        u = data.get("usage", {})
        usage = {
            "llm_tokens": u.get("total_tokens", 0),
            "llm_usd": float(u.get("cost", 0.0)),
        }
        # Default-deny at the response boundary. Round 3 guarded the whole
        # response handling with `except Exception -> PlanError`, which classified
        # everything it did NOT recognise as the model's fault — the same
        # catch-all shape as the defect before it, with the polarity flipped
        # (PR #15, R18). Only a response positively recognised as "the model
        # answered, and the answer is not a plan" is the model's; an envelope this
        # code cannot read is the provider, and stays an ordinary exception so
        # callers abort instead of scoring it.
        #
        # Any truthy `error` is a provider error, not a string-vs-dict question:
        # an `isinstance(..., dict)` test missed `{"error": "rate limited"}`.
        if data.get("error"):
            raise RuntimeError(f"provider error: {data['error']}")
        try:
            choice = data["choices"][0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError(f"message is {type(message).__name__}, not an object")
        except Exception as e:
            raise RuntimeError(
                f"unreadable planner response envelope: {type(e).__name__}: {e}") from e
        # From here the model demonstrably answered, so everything is its own
        # doing and carries the usage the provider billed for it.
        content = message.get("content")
        if not content:
            # `content: null` is what a reasoning model returns on
            # `finish_reason: length`, and the ceiling model defaults to high
            # reasoning effort. It answered; the answer contains no plan.
            raise PlanError(
                "model returned no plan content "
                f"(finish_reason={choice.get('finish_reason') or 'unknown'})", usage)
        try:
            steps = parse_plan(content)
        except PlanError as e:
            e.usage = usage
            raise
        return steps, usage

    return plan
