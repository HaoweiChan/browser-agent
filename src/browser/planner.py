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
 "target": {"role": str|null, "name": str|null, "text": str|null} | null,
 "value": str|null,
 "expected_state": {"url_contains": str} | {"text_visible": str} | {"role_visible": {"role": str, "name": str|null}} | null}
Rules: `navigate` puts the URL in `value`. `extract` reads the target element's
text as the answer. Targets are semantic (ARIA role + accessible name) — never
CSS selectors. Prefer few steps. Every click/fill carries an expected_state.
Output the raw JSON array only — no markdown fences, no commentary."""


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

    async def plan(task: str, url: str | None):
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

    async def plan(task: str, url: str | None):
        user = f"Task: {task}\nStart URL: {url or 'none — choose one via navigate'}"
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
