"""The agent loop: screen -> plan -> execute step-by-step -> assemble result.

Every step is postcondition-verified against the page (never self-reported).
Failures carry exactly one top-level class from docs/evals/failure-taxonomy.md.
Recovery ladders land at M3; at M1 a classified failure is a loud stop.
Output shape: specs/001-browser-contract.md.
"""

import json
import re
import time
from pathlib import Path

from .resolver import ResolveError, resolve

MAX_ACTIONS = 30
SETTLE_TRIES, SETTLE_MS = 10, 200

# ponytail: keyword screen — LLM-based scope screening only if evals demand it (M3).
SCOPE_BLOCK = re.compile(
    r"log ?in|sign ?in|password|captcha|checkout|payment|purchase|\bbuy\b|\bpay\b"
    r"|delete my|download"
    r"|登入|登录|密碼|密码|驗證碼|验证码|付款|購買|购买|刪除|删除|下載|下载",
    re.IGNORECASE,
)


def screen(task: str) -> str | None:
    m = SCOPE_BLOCK.search(task)
    return f"out of scope (matched '{m.group(0)}'): auth/CAPTCHA/payment/destructive/download tasks are unsupported" if m else None


async def check_state(page, expected: dict | None) -> bool:
    if not expected:
        return True
    for _ in range(SETTLE_TRIES):
        try:
            if "url_contains" in expected:
                if expected["url_contains"] in page.url:
                    return True
            elif "text_visible" in expected:
                if expected["text_visible"] in (await page.inner_text("body")):
                    return True
            elif "role_visible" in expected:
                rv = expected["role_visible"]
                loc = page.get_by_role(rv["role"], name=rv.get("name")) if rv.get("name") else page.get_by_role(rv["role"])
                if await loc.count() >= 1 and await loc.first.is_visible():
                    return True
        except Exception:
            pass
        await page.wait_for_timeout(SETTLE_MS)
    return False


def assemble_result(task, trace, answer, budgets, failure=None, reason=None, final_url=None, page_digest=None):
    if failure:
        status = "unsupported" if failure == "unsupported" else f"failure:{failure}"
    else:
        status = "success"
    # INV-0: never success with empty output (specs/000, specs/001).
    if status == "success" and (not answer or not trace):
        status, reason = "failure:extract", reason or "empty answer or empty trace"
    return {
        "status": status,
        "answer": answer if answer else None,
        "reason": reason,
        "evidence": {
            "trace": trace,
            "screenshots": [s["screenshot"] for s in trace if s.get("screenshot")],
            "final_url": final_url,
            "final_page_digest": page_digest,
        },
        "budgets_spent": budgets,
    }


async def run_task(task: str, url: str | None, planner, run_dir: str | Path, headless: bool = True, url_guard=None):
    t0 = time.monotonic()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    budgets = {"actions": 0, "llm_tokens": 0, "llm_usd": 0.0, "ms": 0}
    trace: list[dict] = []

    def done(answer=None, failure=None, reason=None, final_url=None, digest=None):
        budgets["ms"] = int((time.monotonic() - t0) * 1000)
        result = assemble_result(task, trace, answer, budgets, failure, reason, final_url, digest)
        (run_dir / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in trace) + "\n")
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    if reason := screen(task):
        return done(failure="unsupported", reason=reason)

    from playwright.async_api import async_playwright

    from .observe import observe

    answer = None
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            # Pre-plan navigation + observation: the planner never plans blind
            # (live failures dee8ad5d / 2e70785a — guessed roles, invented
            # postconditions). Evolving-prefix replan on invalidation lands at M3.
            obs = None
            if url:
                if url_guard and not url_guard(url):
                    return done(failure="task", reason=f"blocked URL: {url!r}")
                s0 = time.monotonic()
                rec = {
                    "i": 1, "action": "navigate", "target": None, "value": url,
                    "resolved": None, "expected_state": None, "postcondition_ok": None,
                    "failure_class": None, "note": "pre-plan observation",
                    "retry_or_recovery": None, "screenshot": None, "ms": 0,
                }
                trace.append(rec)
                budgets["actions"] += 1
                try:
                    await page.goto(url, timeout=20_000)
                    obs = await observe(page)
                    (run_dir / "observation.json").write_text(json.dumps(obs, indent=2))
                    rec["postcondition_ok"] = True
                except Exception as e:
                    rec["failure_class"] = "nav"
                    rec["note"] = f"{type(e).__name__}: {e}"
                    return done(failure="nav", reason=f"pre-plan navigation failed: {e}")
                rec["ms"] = int((time.monotonic() - s0) * 1000)

            try:
                steps, usage = await planner(task, url, obs)
                budgets["llm_tokens"] += usage["llm_tokens"]
                budgets["llm_usd"] += usage["llm_usd"]
            except Exception as e:
                return done(failure="env", reason=f"planner failed: {e}")

            for i, step in enumerate(steps, len(trace) + 1):
                if budgets["actions"] >= MAX_ACTIONS:
                    return done(failure="env", reason=f"action budget ({MAX_ACTIONS}) exhausted")
                budgets["actions"] += 1
                s0 = time.monotonic()
                rec = {
                    "i": i, "action": step["action"], "target": step.get("target"),
                    "value": step.get("value"), "resolved": None,
                    "expected_state": step.get("expected_state"), "postcondition_ok": None,
                    "failure_class": None, "note": None, "retry_or_recovery": None,
                    "screenshot": None, "ms": 0,
                }
                trace.append(rec)

                def fail(cls, note):
                    rec["failure_class"], rec["note"] = cls, note
                    rec["ms"] = int((time.monotonic() - s0) * 1000)
                    return done(failure=cls, reason=f"step {i} ({step['action']}): {note}")

                try:
                    if step["action"] == "navigate":
                        if url_guard and not url_guard(step.get("value") or ""):
                            return fail("task", f"blocked URL: {step.get('value')!r}")
                        await page.goto(step["value"], timeout=20_000)
                    else:
                        loc, tier = await resolve(page, step.get("target") or {})
                        rec["resolved"] = {"tier": tier, "description": str(step.get("target"))}
                        if step["action"] == "click":
                            await loc.click(timeout=10_000)
                        elif step["action"] == "fill":
                            await loc.fill(step.get("value") or "", timeout=10_000)
                        elif step["action"] == "extract":
                            answer = (await loc.inner_text()).strip()
                        else:
                            return fail("task", f"unknown action {step['action']!r}")
                except ResolveError as e:
                    return fail("locate", f"{e.kind}: {e}")
                except Exception as e:
                    cls = "nav" if step["action"] == "navigate" else "act"
                    return fail(cls, f"{type(e).__name__}: {e}")

                rec["postcondition_ok"] = await check_state(page, step.get("expected_state"))
                if step["action"] == "extract" and not answer:
                    return fail("extract", "extraction returned empty text")
                shot = f"step_{i}.png"
                try:
                    await page.screenshot(path=str(run_dir / shot))
                    rec["screenshot"] = shot
                except Exception:
                    pass  # evidence best-effort; the postcondition is the gate
                rec["ms"] = int((time.monotonic() - s0) * 1000)
                if rec["postcondition_ok"] is False:
                    return fail("act", f"expected_state not reached: {step.get('expected_state')}")

            digest = (await page.inner_text("body"))[:500]
            final_url = page.url
        finally:
            await browser.close()

    return done(answer=answer, final_url=final_url, digest=digest)
