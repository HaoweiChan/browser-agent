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
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"

SYSTEM = """You are a browser-automation planner. Emit ONLY a JSON array of steps.
Each step: {"action": "navigate|click|fill|extract",
 "target": {"role": str|null, "name": str|null, "text": str|null, "index": int|null} | null,
 "value": str|null,
 "anchor": str|null,
 "expected_state": {"url_contains": str} | {"text_visible": str} | {"role_visible": {"role": str, "name": str|null}} | null}
Rules: `navigate` puts the URL in `value`. `extract` reads the target element's
text as the answer. Targets are semantic (ARIA role + accessible name) — never
CSS selectors. `index` (0-based) picks the k-th match when several elements
share a role, e.g. the first search result. On an `extract` step, `anchor` is
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
    pass


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


def stub_planner(steps: list):
    """Deterministic planner for the fast suite: returns the given steps."""

    async def plan(task: str, url: str | None, observation: dict | None = None):
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

    async def plan(task: str, url: str | None, observation: dict | None = None):
        user = f"Task: {task}\nStart URL: {url or 'none — choose one via navigate'}"
        if observation:
            from .observe import render

            user += "\n\nCurrent page observation:\n" + render(observation)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "usage": {"include": True},
        }
        data = await asyncio.to_thread(_call, payload)
        content = data["choices"][0]["message"]["content"]
        steps = parse_plan(content)
        u = data.get("usage", {})
        usage = {
            "llm_tokens": u.get("total_tokens", 0),
            "llm_usd": float(u.get("cost", 0.0)),
        }
        return steps, usage

    return plan
