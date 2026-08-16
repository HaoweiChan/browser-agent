"""Eval adapter for task "browser" — the EvalAuditor (contract: evals/run.py).

Judging goes through the production OutcomeVerifier (`src/browser/verifier.py`),
not through a second set of eval-only assertions: one verifier, two callers.
The adapter's own job is to supply what the runtime cannot have — hand-labeled
expectations, identity anchors, and external ground truth from the fixture
`/state` endpoint.

Case kinds (`input.kind`):
- `invariant`    — pure-code property check, no browser (`check`: inv0 | inv1 | inv2)
- `observe`      — a11y observation shape
- `url-guard`    — SSRF guard truth table
- `screening`    — pre-flight scope screen truth table
- `parse-plan`   — planner output tolerance
- `mutation`     — mutation catalog integrity (pure code, no browser)
- (default)      — fixture E2E: real agent, real browser, planner stubbed at the
  module boundary. `$FIXTURE_URL` in a step value is substituted with the served
  fixture URL; `mut` selects a mutation; `reset_form` clears TC5 ground truth.

The fixture sites are served by the real FastAPI app on loopback (started once
per process) so eval and production exercise the same serving path.
"""

import asyncio
import json
import socket
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from .agent import assemble_result, run_task
from .planner import stub_planner
from .verifier import verify

FIXTURES = Path(__file__).parent / "fixtures"
_BASE: str | None = None


def _base_url() -> str:
    """Start the gateway app on a free loopback port, once per process."""
    global _BASE
    if _BASE:
        return _BASE
    import uvicorn

    from .server import app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{base}/healthz", timeout=0.5).read()
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("fixture server did not become ready")  # loud, never mocked
    _BASE = base
    return base


def _get_json(path: str):
    with urllib.request.urlopen(f"{_base_url()}{path}", timeout=5) as r:
        return json.load(r)


def _post(path: str):
    urllib.request.urlopen(
        urllib.request.Request(f"{_base_url()}{path}", data=b"", method="POST"), timeout=5
    ).read()


# --- pure-code invariant checks --------------------------------------------

def _check_inv0() -> dict:
    """INV-0: a completed run with empty output must not report success."""
    fake_trace = [{"i": 1, "action": "extract", "postcondition_ok": True, "screenshot": None}]
    r = assemble_result(
        task="x", trace=fake_trace, answer="",
        budgets={"actions": 1, "llm_tokens": 0, "llm_usd": 0.0, "ms": 1},
    )
    return {"passed": r["status"] != "success", "status": r["status"]}


CLASSES = ["nav", "locate", "act", "extract", "semantic", "env", "task"]


def _check_inv1() -> dict:
    """INV-1: every non-success status carries exactly one known class."""
    trace = [{"i": 1, "action": "click", "postcondition_ok": True, "screenshot": None}]
    budgets = {"actions": 1, "llm_tokens": 0, "llm_usd": 0.0, "ms": 1}
    wrong = []
    for cls in CLASSES:
        st = assemble_result(task="x", trace=trace, answer="a", budgets=budgets,
                             failure=cls)["status"]
        if st != f"failure:{cls}" or st.count(":") != 1:
            wrong.append((cls, st))
    st = assemble_result(task="x", trace=trace, answer="a", budgets=budgets,
                         failure="unsupported")["status"]
    if st != "unsupported":
        wrong.append(("unsupported", st))
    return {"passed": not wrong, "wrong": wrong}


def _check_inv2() -> dict:
    """INV-2: a FAIL/INCONCLUSIVE verdict can never be reported as success."""
    trace = [{"i": 1, "action": "extract", "postcondition_ok": True, "screenshot": None}]
    budgets = {"actions": 1, "llm_tokens": 0, "llm_usd": 0.0, "ms": 1}
    bad = []
    for v in ("FAIL", "INCONCLUSIVE"):
        r = assemble_result(task="x", trace=trace, answer="an answer", budgets=budgets,
                            verdict={"verdict": v, "reason": "planted"})
        if r["status"] == "success":
            bad.append(v)
    ok = assemble_result(task="x", trace=trace, answer="an answer", budgets=budgets,
                         verdict={"verdict": "PASS", "reason": None})
    return {"passed": not bad and ok["status"] == "success", "leaked": bad}


def _check_inv3() -> dict:
    """INV-3: budget exhaustion is a loud classified failure, never a quiet stop.

    Pure code — the budgets are counters and `budget_stop` is the predicate over
    them, so the property is checkable without a browser. The end-to-end half
    (a run that really exhausts its replans) is budget-replans-exhausted."""
    from .agent import RUN_BUDGETS, budget_stop

    wrong = []
    if budget_stop({k: 0 for k in RUN_BUDGETS}) is not None:
        wrong.append("stopped a run that had spent nothing")
    for k, cap in RUN_BUDGETS.items():
        if budget_stop({k: cap - 1}) is not None:
            wrong.append(f"{k} stopped below its cap")
        if budget_stop({k: cap}) is None:
            wrong.append(f"{k} did not stop AT its cap")
        if budget_stop({k: cap * 2}) is None:
            wrong.append(f"{k} did not stop past its cap")
    # ...and the stop must arrive as a classified failure carrying its trace,
    # which is the half that makes it loud rather than merely correct.
    trace = [{"i": 1, "action": "click", "postcondition_ok": True, "screenshot": None}]
    r = assemble_result(task="x", trace=trace, answer="a",
                        budgets={"actions": 30, "llm_tokens": 0, "llm_usd": 0.0,
                                 "replans": 0, "ms": 1},
                        failure="env", reason=budget_stop({"actions": 30}))
    if r["status"] != "failure:env" or not r["reason"] or not r["evidence"]["trace"]:
        wrong.append(f"exhaustion was not a loud classified failure: {r['status']}")
    return {"passed": not wrong, "wrong": wrong}


INVARIANTS = {"inv0": _check_inv0, "inv1": _check_inv1, "inv2": _check_inv2,
              "inv3": _check_inv3}


def _run_classify_case(case: dict) -> dict:
    """Diagnosis ground truth: (action, error) -> exactly one taxonomy class.

    The classifier is the only component that decides which recovery ladder
    fires, so it gets a truth table rather than an assertion in prose."""
    from .agent import StepError, classify
    from .resolver import ResolveError

    def make(spec: str) -> Exception:
        if spec.startswith("StepError:"):
            return StepError(spec.split(":", 1)[1], "planted")
        if spec == "ResolveError":
            return ResolveError("element-not-found", "planted")
        if spec == "TimeoutError":
            return TimeoutError("planted")
        if spec == "Exception":
            return Exception("planted")
        raise KeyError(f"unknown exception spec {spec!r}")  # loud, never a silent skip

    wrong = [{"action": a, "exc": spec, "want": want, "got": got}
             for a, spec, want in case["input"]["checks"]
             if (got := classify(a, make(spec))) != want]
    return {"passed": not wrong, "wrong": wrong}


def _run_relocate_case(case: dict) -> dict:
    """Relocation rungs: same intent, different tier, never the tier that just
    failed. Pure function over a target and a snapshot — no browser needed."""
    from .resolver import relocation_candidates

    inp = case["input"]
    wrong = []
    for chk in inp["checks"]:
        got = relocation_candidates(chk["target"], inp["observation"])
        want = chk["expect"]
        # Compare on the tier-defining keys only; `index` is intent, not tier.
        thin = [{k: v for k, v in c.items() if k in ("role", "name", "text")} for c in got]
        if thin != want:
            wrong.append({"target": chk["target"], "want": want, "got": got})
    return {"passed": not wrong, "wrong": wrong}


def _run_mutation_case(case: dict) -> dict:
    """Mutation catalog integrity: each transform must break its own tier and
    leave the others alone. Without this the L4 evidence is unfalsifiable."""
    from .mutate import apply_mutation

    src = (FIXTURES / case["input"]["fixture"]).read_text()
    wrong = []
    for name, want in case["input"]["checks"].items():
        out = apply_mutation(src, name)
        for needle, should_be_present in want.items():
            if (needle in out) != should_be_present:
                wrong.append({"mut": name, "needle": needle, "expected_present": should_be_present})
    return {"passed": not wrong, "wrong": wrong}


def _run_schema_case(case: dict) -> dict:
    """Field-by-field conformance to specs/001-browser-contract.md.

    The contract is prose; prose does not fail a build. This case is the
    executable half — it caught `anchor` being specced into TraceStep and never
    emitted (M2 close-out)."""
    inp = case["input"]
    base = _base_url()
    steps = json.loads(json.dumps(inp["stub_plan"]).replace(
        "$FIXTURE_URL", f"{base}/fixtures/{inp['fixture']}"))
    with tempfile.TemporaryDirectory() as run_dir:
        result = asyncio.run(run_task(
            inp["task"], f"{base}/fixtures/{inp['fixture']}", stub_planner([steps]), run_dir))

    got = {
        "result": list(result),
        "evidence": list(result["evidence"]),
        "verdict": list(result["verdict"]),
        "budgets_spent": list(result["budgets_spent"]),
        # Every step, not just the last: the pre-plan navigate record is built
        # separately from the step-loop record and drifts on its own.
        "trace_step": sorted({k for s in result["evidence"]["trace"] for k in s}),
    }
    wrong = {
        k: {"missing": sorted(set(want) - set(got[k])), "extra": sorted(set(got[k]) - set(want))}
        for k, want in case["expect"]["keys"].items()
        if set(want) != set(got[k])
    }
    short = [s["i"] for s in result["evidence"]["trace"]
             if set(s) != set(case["expect"]["keys"]["trace_step"])]
    if short:
        wrong["trace_step_incomplete"] = short
    return {"passed": not wrong, "wrong": wrong, "got": got}


def _run_verifier_case(case: dict) -> dict:
    """Direct probes of the grader itself. The grader is the only component
    with no other component checking it, so it gets unit-shaped cases."""
    from .verifier import answers_match

    inp = case["input"]
    wrong = []
    # A probe the adapter does not understand must be loud. Silently skipping an
    # unknown key scored this case PASS while it checked nothing at all — a case
    # that proves nothing is worse than no case, because it reads as coverage.
    unknown = set(inp) - {"kind", "compare", "anchors", "superseded"}
    if unknown:
        return {"passed": False, "error": f"unknown verifier probe(s): {sorted(unknown)}"}
    for got, want, should_match in inp.get("compare", []):
        if answers_match(got, want) != should_match:
            wrong.append({"got": got, "want": want, "should_match": should_match})
    for sc in inp.get("superseded", []):
        v = verify(trace=sc["trace"], extractions=[{"value": "a", "page_text": "a"}], answer="a")
        if (v["verdict"] == "PASS") != sc["pass"]:
            wrong.append({"superseded": sc["note"], "should_pass": sc["pass"],
                          "verdict": v["verdict"], "checks": v["checks"]})
    for sc in inp.get("anchors", []):
        v = verify(
            trace=[{"i": 1, "action": "extract", "postcondition_ok": True}],
            extractions=[{"value": sc["answer"], "page_text": t} for t in sc["page_texts"]],
            answer=sc["answer"],
            expect={"anchors": sc["anchors"]},
        )
        if v["checks"]["identity_anchors"] != sc["pass"]:
            wrong.append({"anchors": sc["anchors"], "should_pass": sc["pass"]})
    return {"passed": not wrong, "wrong": wrong}


def _run_observe_case(case: dict) -> dict:
    from playwright.async_api import async_playwright

    from .observe import observe

    url = f"{_base_url()}/fixtures/{case['input']['fixture']}"

    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page()
            await page.goto(url)
            obs = await observe(page)
            await browser.close()
            return obs

    obs = asyncio.run(go())
    exp = case["expect"]
    missing = [
        want for want in exp.get("contains", [])
        if not any(
            e["role"] == want["role"] and ("name" not in want or e["name"] == want["name"])
            for e in obs["elements"]
        )
    ]
    # An observation may only advertise names the resolver can actually use.
    unnameable = [e for e in obs["elements"] if e["role"] in exp.get("unnameable_roles", []) and e["name"]]
    return {
        "passed": not missing and not unnameable,
        "missing": missing,
        "advertised_unresolvable": unnameable,
        "n_elements": len(obs["elements"]),
    }


def _run_fixture_case(case: dict) -> dict:
    inp, exp = case["input"], case.get("expect", {})
    # Refusal (L5) cases carry no fixture: the run must stop before browsing.
    fixture_url = None
    if inp.get("fixture"):
        # Unconditional: the form fixture's state is process-global, so an
        # opt-in reset lets a case grade against the previous case's submission
        # and pass on stale ground truth (cold-reviewer, M2 close-out).
        _post("/fixtures/forms/reset")
        fixture_url = f"{_base_url()}/fixtures/{inp['fixture']}"
        if inp.get("mut"):
            fixture_url += f"?mut={inp['mut']}"
    # One plan per planner call: `stub_plans` is what a case uses to say what the
    # replanner comes back with; `stub_plan` is the single-plan shorthand.
    plans = inp.get("stub_plans") or [inp.get("stub_plan", [])]
    plans = json.loads(json.dumps(plans).replace("$FIXTURE_URL", fixture_url or ""))
    with tempfile.TemporaryDirectory() as run_dir:
        result = asyncio.run(
            run_task(inp["task"], inp.get("url", fixture_url), stub_planner(plans), run_dir)
        )

    # Re-verify with ground truth the runtime cannot have: hand labels, identity
    # anchors, and the fixture's own record of what it received.
    state = _get_json("/fixtures/forms/state") if "state" in exp else None
    audit = verify(
        trace=result["evidence"]["trace"],
        extractions=result["evidence"]["extractions"],
        answer=result["answer"],
        expect=exp,
        state=state,
    )
    checks = {}
    if "status" in exp:
        checks["status"] = result["status"] == exp["status"]
    # A case that expects a non-success status is judged on the status alone
    # unless it names a verdict — grading a refusal's outcome is meaningless.
    want_verdict = exp.get("verdict") or (
        "PASS" if exp.get("status", "success") == "success" else None
    )
    if want_verdict:
        checks["verdict"] = audit["verdict"] == want_verdict

    trace = result["evidence"]["trace"]
    recovered = [s for s in trace if s.get("retry_or_recovery") == "recovery"]
    # `recovery: true` asserts the mechanism, not just the outcome: a strategy
    # switch that was actually taken AND a run that then succeeded. A case that
    # passes without one of those is passing for a different reason than it says.
    if "recovery" in exp:
        checks["recovery"] = bool(recovered) == exp["recovery"]
    if "replans" in exp:
        checks["replans"] = result["budgets_spent"]["replans"] == exp["replans"]

    # Metrics the runner rolls up (docs/evals/evaluation-methodology.md). Counted
    # from the trace and the injected ground truth, never from a claim.
    metrics = {}
    if inp.get("mut"):
        metrics["mutation_cases"] = 1
        metrics["mutation_passed"] = int(result["status"] == exp.get("status", "success"))
        # Passing is not recovering. Two of the three B-floor mutations break a
        # tier no plan was standing on, so they pass without anything being
        # relocated; counting those as recoveries is the flattering lie ADR-002
        # called out. Only a run that actually switched tiers counts here.
        metrics["mutation_recovered"] = int(bool(recovered) and result["status"] == "success")
    # Denominator = cases that ASSERT recovery, so a ladder that correctly fails
    # to save a doomed run (resolver-substring-name) is not scored as a miss and
    # not scored as a win. Rungs tried is reported beside it as raw context.
    if recovered:
        metrics["recovery_rungs"] = len(recovered)
    if exp.get("recovery"):
        metrics["recovery_expected"] = 1
        metrics["recovery_verified"] = int(bool(recovered) and result["status"] == "success")
    if str(exp.get("status", "")).startswith("failure:"):
        metrics["diagnosis_cases"] = 1
        metrics["diagnosis_correct"] = int(result["status"] == exp["status"])
    if result["budgets_spent"]["replans"]:
        metrics["replans"] = result["budgets_spent"]["replans"]

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "audit": audit,
        "metrics": metrics,
        "tiers": [s["resolved"]["tier"] for s in trace if s.get("resolved")],
        "got": {"status": result["status"], "answer": result["answer"],
                "reason": result["reason"]},
        "budgets": result["budgets_spent"],
    }


def run_case(case: dict) -> dict:
    kind = case["input"].get("kind")
    if kind == "invariant":
        check = case["input"]["check"]
        if check not in INVARIANTS:
            return {"passed": False, "error": f"unknown invariant check {check}"}
        return INVARIANTS[check]()
    if kind == "observe":
        return _run_observe_case(case)
    if kind == "mutation":
        return _run_mutation_case(case)
    if kind == "verifier":
        return _run_verifier_case(case)
    if kind == "classify":
        return _run_classify_case(case)
    if kind == "relocate":
        return _run_relocate_case(case)
    if kind == "schema":
        return _run_schema_case(case)
    if kind == "url-guard":
        from .server import url_ok

        wrong = [u for u, want in case["input"]["checks"] if url_ok(u) != want]
        return {"passed": not wrong, "wrong": wrong}
    if kind == "screening":
        from .agent import screen

        wrong = [t for t, want in case["input"]["checks"] if (screen(t) is not None) != want]
        return {"passed": not wrong, "wrong": wrong}
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
