"""Eval adapter for task "browser" (contract: evals/run.py docstring).

Case kinds:
- {"kind": "invariant", "check": "inv0"} — pure-code property check, no browser.
- {"task", "fixture", "stub_plan"} — runs the real agent on a local fixture with
  the planner stubbed at the module boundary (fast suite: zero LLM, zero
  network beyond loopback). $FIXTURE_URL in a step's value is substituted with
  the served fixture URL.
"""

import asyncio
import http.server
import json
import tempfile
import threading
from functools import partial
from pathlib import Path

from .agent import assemble_result, run_task
from .planner import stub_planner

FIXTURES = Path(__file__).parent / "fixtures"


def _check_inv0() -> dict:
    """INV-0: a completed run with empty output must not report success."""
    fake_trace = [{"i": 1, "action": "extract", "postcondition_ok": True, "screenshot": None}]
    r = assemble_result(
        task="x", trace=fake_trace, answer="",
        budgets={"actions": 1, "llm_tokens": 0, "llm_usd": 0.0, "ms": 1},
    )
    return {"passed": r["status"] != "success", "status": r["status"]}


def _serve_fixtures():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _run_observe_case(case: dict) -> dict:
    from playwright.async_api import async_playwright

    from .observe import observe

    server, base = _serve_fixtures()
    try:
        async def go():
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(args=["--no-sandbox"])
                page = await browser.new_page()
                await page.goto(f"{base}/{case['input']['fixture']}")
                obs = await observe(page)
                await browser.close()
                return obs

        obs = asyncio.run(go())
    finally:
        server.shutdown()

    missing = []
    for want in case["expect"]["contains"]:
        hit = any(
            e["role"] == want["role"] and ("name" not in want or e["name"] == want["name"])
            for e in obs["elements"]
        )
        if not hit:
            missing.append(want)
    return {"passed": not missing, "missing": missing, "n_elements": len(obs["elements"])}


def _run_fixture_case(case: dict) -> dict:
    inp = case["input"]
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        fixture_url = f"{base}/{inp['fixture']}"
        steps = json.loads(json.dumps(inp["stub_plan"]).replace("$FIXTURE_URL", fixture_url))
        with tempfile.TemporaryDirectory() as run_dir:
            result = asyncio.run(
                run_task(inp["task"], fixture_url, stub_planner(steps), run_dir)
            )
    finally:
        server.shutdown()

    exp = case.get("expect", {})
    checks = {
        k: result.get(k) == v for k, v in exp.items() if k in ("status", "answer")
    }
    return {
        "passed": all(checks.values()),
        "got": {"status": result["status"], "answer": result["answer"]},
        "checks": checks,
        "budgets": result["budgets_spent"],
    }


def run_case(case: dict) -> dict:
    kind = case["input"].get("kind")
    if kind == "invariant":
        if case["input"]["check"] == "inv0":
            return _check_inv0()
        return {"passed": False, "error": f"unknown invariant check {case['input']['check']}"}
    if kind == "observe":
        return _run_observe_case(case)
    if kind == "parse-plan":
        from .planner import PlanError, parse_plan

        exp = case["expect"]
        try:
            steps = parse_plan(case["input"]["content"])
        except PlanError as e:
            return {"passed": False, "error": str(e)[:200]}
        return {
            "passed": len(steps) == exp["steps"] and steps[0]["action"] == exp["first_action"],
            "got": {"steps": len(steps), "first_action": steps[0].get("action")},
        }
    return _run_fixture_case(case)
