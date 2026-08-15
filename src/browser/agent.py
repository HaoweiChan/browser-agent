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
from .verifier import verify

MAX_ACTIONS = 30
SETTLE_TRIES, SETTLE_MS = 10, 200
PAGE_TEXT_KEEP = 2000  # evidence digest per extraction — enough for anchors, bounded

# ponytail: keyword screen — LLM-based scope screening only if evals demand it (M3).
# Latin terms need \b (case screening-word-boundary: 'signing' contains 'signin');
# CJK terms must stay boundary-free — \b never matches inside a CJK run.
SCOPE_BLOCK = re.compile(
    r"\b(?:log ?in|sign ?in|password|captcha|checkout|payment|purchase|buy|pay|download)\b"
    r"|\bdelete (?:my|the|this)\b"
    r"|登入|登录|密碼|密码|驗證碼|验证码|付款|購買|购买|刪除|删除|下載|下载",
    re.IGNORECASE,
)


def screen(task: str) -> str | None:
    m = SCOPE_BLOCK.search(task)
    return f"out of scope (matched '{m.group(0)}'): auth/CAPTCHA/payment/destructive/download tasks are unsupported" if m else None


async def check_state(page, expected: dict | None) -> bool | None:
    """True / False / None, where None means "nothing was asserted".

    None is not True. Collapsing them recorded unverified steps as verified and
    made the module docstring's claim false (case postcondition-unverified-click).
    Every key present must hold: an if/elif chain silently graded a compound
    expectation on its first key alone (case postcondition-compound-keys).
    """
    if not expected:
        return None

    async def holds(key, want) -> bool:
        if key == "url_contains":
            return want in page.url
        if key == "text_visible":
            return want in (await page.inner_text("body"))
        if key == "role_visible":
            loc = (page.get_by_role(want["role"], name=want["name"])
                   if want.get("name") else page.get_by_role(want["role"]))
            return await loc.count() >= 1 and await loc.first.is_visible()
        raise ValueError(f"unknown expected_state key {key!r}")

    for _ in range(SETTLE_TRIES):
        try:
            if all([await holds(k, v) for k, v in expected.items()]):
                return True
        except ValueError:
            raise
        except Exception:
            pass
        await page.wait_for_timeout(SETTLE_MS)
    return False


def evidence_window(body: str, value: str, keep: int = PAGE_TEXT_KEEP) -> str:
    """Bounded page-text evidence that still contains the extracted value.

    A flat head-truncation would fail the verifier's grounding check on any
    page longer than `keep` — a false `failure:semantic` on a correct run.
    Selecting the window is evidence handling, not grading: if the value is
    absent the head is stored and grounding fails, which is the true verdict.
    """
    if len(body) <= keep:
        return body
    i = body.find(value)
    if i < 0:
        return body[:keep]
    lo = max(0, i - keep // 2)
    return body[lo:lo + keep]


def assemble_result(task, trace, answer, budgets, failure=None, reason=None, final_url=None,
                    page_digest=None, extractions=None, verdict=None):
    if failure:
        status = "unsupported" if failure == "unsupported" else f"failure:{failure}"
    else:
        status = "success"
    # INV-0: never success with empty output (specs/000, specs/001).
    if status == "success" and (not answer or not trace):
        status, reason = "failure:extract", reason or "empty answer or empty trace"
    # INV-2: the executor's claim never outranks the verifier (specs/000).
    if status == "success" and verdict and verdict.get("verdict") != "PASS":
        status = "failure:semantic"
        reason = reason or f"verifier {verdict['verdict']}: {verdict.get('reason')}"
    return {
        "status": status,
        "answer": answer if answer else None,
        "reason": reason,
        "verdict": verdict,
        "evidence": {
            "trace": trace,
            "screenshots": [s["screenshot"] for s in trace if s.get("screenshot")],
            "extractions": extractions or [],
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
    # Raw evidence for the OutcomeVerifier: what was read, and what the page
    # said at the moment it was read. The verifier never sees our conclusion.
    extractions: list[dict] = []

    def done(answer=None, failure=None, reason=None, final_url=None, digest=None, verdict=None):
        budgets["ms"] = int((time.monotonic() - t0) * 1000)
        result = assemble_result(task, trace, answer, budgets, failure, reason, final_url,
                                 digest, extractions, verdict)
        (run_dir / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in trace) + "\n")
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    if reason := screen(task):
        return done(failure="unsupported", reason=reason)

    from playwright.async_api import async_playwright

    from .observe import observe

    answers: list = []
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
                            # A fill verifies itself by readback, so it needs no
                            # authored postcondition to count as checked.
                            back = await loc.input_value()
                            if back != (step.get("value") or ""):
                                return fail("act", f"field readback {back!r} != filled value")
                            rec["postcondition_ok"] = True
                        elif step["action"] == "extract":
                            val = (await loc.inner_text()).strip()
                            if not val:
                                return fail("extract", "extraction returned empty text")
                            body = await page.inner_text("body")
                            extractions.append({"value": val, "page_text": evidence_window(body, val)})
                            answers.append(val)
                            # Identity anchor (verifier L1): the entity the task
                            # names must be present where the answer was read.
                            anchor = step.get("anchor")
                            if anchor and anchor not in body:
                                return fail("semantic", f"identity anchor {anchor!r} absent from the page the answer was read from")
                        else:
                            return fail("task", f"unknown action {step['action']!r}")
                except ResolveError as e:
                    return fail("locate", f"{e.kind}: {e}")
                except Exception as e:
                    cls = "nav" if step["action"] == "navigate" else "act"
                    return fail(cls, f"{type(e).__name__}: {e}")

                try:
                    checked = await check_state(page, step.get("expected_state"))
                except ValueError as e:
                    return fail("task", f"malformed expected_state: {e}")
                if checked is not None or rec["postcondition_ok"] is None:
                    rec["postcondition_ok"] = checked
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

    # One extract -> scalar answer; several -> list (contract: answer string|list).
    answer = answers[0] if len(answers) == 1 else (answers or None)
    # The run is graded by the verifier, not by having reached this line.
    verdict = verify(trace=trace, extractions=extractions, answer=answer)
    return done(answer=answer, final_url=final_url, digest=digest, verdict=verdict)
