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
              "inv3": _check_inv3, "supersede-dangling": lambda: _check_supersede_dangling()}


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
    # The observation budget must not be spent entirely on chrome: content the
    # task is about has to survive the cap (observe-content-survives-chrome).
    names, roles = {e["name"] for e in obs["elements"]}, {e["role"] for e in obs["elements"]}
    starved = ([n for n in exp.get("must_include_names", []) if n not in names]
               + [r for r in exp.get("must_include_roles", []) if r not in roles])
    return {
        "passed": not missing and not unnameable and not starved,
        "missing": missing,
        "advertised_unresolvable": unnameable,
        "starved_by_chrome": starved,
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
    # An injected marker predicate, not the production url_ok: fixtures are
    # served on loopback and the real guard blocks loopback, so passing url_ok
    # here would fail every fixture case for the wrong reason. This grades that
    # the guard is CONSULTED as the browser moves; url-guard-literal-ips grades
    # what it decides.
    guard = (lambda u: inp["block_host"] not in u) if inp.get("block_host") else None
    with tempfile.TemporaryDirectory() as run_dir:
        result = asyncio.run(
            run_task(inp["task"], inp.get("url", fixture_url), stub_planner(plans), run_dir,
                     url_guard=guard)
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
    # A "recovery" label claims a strategy CHANGED. An attempt identical to the
    # one it replaced is a retry, and specs/001 keeps retries out of the
    # recovery metric by construction, not by intention.
    if exp.get("no_recovery_label_on_identical_step"):
        intent = lambda s: (s.get("action"), json.dumps(s.get("target"), sort_keys=True),
                            s.get("value"), json.dumps(s.get("expected_state"), sort_keys=True))
        by_i = {s["i"]: s for s in trace}
        relabelled = [s["i"] for s in trace if s.get("retry_or_recovery") == "recovery"
                      for o in trace if o.get("superseded_by") == s["i"]
                      and intent(o) == intent(by_i[s["i"]])]
        checks["no_recovery_label_on_identical_step"] = not relabelled

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
        # Graded on the AUDIT, not on the runtime's own claim. Keyed off
        # result["status"] == "success", a run that "recovered" into a wrong
        # answer counted toward the headline recovery number even when
        # ground truth said FAIL — the metric flattering itself with the
        # mechanism it is supposed to be measuring (cold review, M3).
        metrics["recovery_verified"] = int(bool(recovered) and all(checks.values()))
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


def _run_stream_case(case: dict) -> dict:
    """The progress stream must show the run that happened, not a tidier one.

    Grades the `on_step` hook the gateway's SSE endpoint is built on, not the
    HTTP framing — POST /tasks plans with the live model, and the fast suite
    spends $0.00. Adding a stub backdoor to a public endpoint to test it here
    would be a worse trade than testing one layer down."""
    inp, exp = case["input"], case["expect"]
    fixture_url = f"{_base_url()}/fixtures/{inp['fixture']}"
    if inp.get("mut"):
        fixture_url += f"?mut={inp['mut']}"
    steps = json.loads(json.dumps(inp["stub_plan"]).replace("$FIXTURE_URL", fixture_url))

    live: list[dict] = []
    with tempfile.TemporaryDirectory() as run_dir:
        result = asyncio.run(run_task(
            inp["task"], fixture_url, stub_planner([steps]), run_dir,
            # Copy on arrival: the executor mutates its record after emitting
            # (screenshot, ms, superseded_by). Holding the live reference would
            # compare the final trace against itself and pass unconditionally.
            on_step=lambda rec: live.append(json.loads(json.dumps(rec))),
        ))
    final = result["evidence"]["trace"]

    checks = {}
    # Same steps, same order, exactly once each: nothing dropped, nothing invented.
    checks["live_matches_final"] = (
        [s["i"] for s in live] == [s["i"] for s in final]) == exp["live_matches_final"]
    # The honesty half. This run's text-tier click fails and is superseded by a
    # relocated attempt; a stream that emits only what worked would still satisfy
    # the ordering check above, because the surviving steps are in order.
    failed_final = [s["i"] for s in final if s.get("failure_class")]
    checks["emits_failed_attempt"] = (
        bool(failed_final) and set(failed_final) <= {s["i"] for s in live}
    ) == exp["emits_failed_attempt"]
    checks["terminal_status"] = result["status"] == exp["terminal_status"]
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "got": {"live_i": [s["i"] for s in live], "final_i": [s["i"] for s in final],
                "failed_i": failed_final, "status": result["status"]},
        "budgets": result["budgets_spent"],
    }


def _run_matrix_case(case: dict) -> dict:
    """Every citation in the honesty table must resolve to a real case.

    Checks that the evidence EXISTS, never that a declared status is right:
    declaring is a human judgment act, and a pass rate that thresholds itself
    into "supported" is the thing the methodology doc forbids."""
    from .server import CASE_CITATION, parse_matrix

    doc = parse_matrix()
    # Case dirs only. Globbing evals/*/*.json swept in evals/report/*.json, so a
    # report filename like `20260816-192727-fast` counted as a valid case id.
    evals_dir = Path(__file__).parents[2] / "evals"
    known = {p.stem for d in ("golden", "adversarial") for p in (evals_dir / d).glob("*.json")}
    legal = set(case["expect"]["statuses"])

    bad_status = [
        {"domain": r["domain"], "tc": tc, "status": v}
        for r in doc["rows"] for tc, v in r["cells"].items() if v not in legal
    ]
    dangling = sorted(set(CASE_CITATION.findall(doc["citation_text"])) - known)
    return {
        "passed": not bad_status and not dangling,
        "wrong": {"illegal_status": bad_status, "dangling_citations": dangling},
        "got": {"rows": len(doc["rows"]), "limitations": len(doc["limitations"]),
                "citations": len(set(CASE_CITATION.findall(doc["citation_text"])))},
    }


def _run_gateway_error_case(case: dict) -> dict:
    """The gateway's catch-all must return the contract shape, not a stub dict.

    Forces the no-key path by blanking OPENROUTER_API_KEY for the duration: the
    app runs in a thread in this process, so the run fails before any HTTP call
    to OpenRouter and the case costs $0.00 on a developer machine that has a key
    (cost-discipline rule 4) instead of quietly making a live request."""
    import os

    inp, exp = case["input"], case["expect"]
    base = _base_url()
    prev = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = ""
    try:
        req = urllib.request.Request(
            f"{base}/tasks", data=json.dumps({"task": inp["task"]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            run_id = json.load(r)["run_id"]
        for _ in range(200):
            rec = _get_json(f"/tasks/{run_id}")
            if rec.get("status") != "running":
                break
            time.sleep(0.05)
        else:
            return {"passed": False, "error": "gateway run never left 'running'"}
    finally:
        if prev is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = prev

    got = {"result": sorted(rec)}
    for section in ("evidence", "budgets_spent"):
        # `or {}` would launder exactly the null this case exists to catch.
        got[section] = sorted(rec[section]) if isinstance(rec[section], dict) else None
    wrong = {k: got[k] for k, want in exp["keys"].items() if got[k] != sorted(want)}
    checks = {"shape": not wrong,
              "classified": str(rec.get("status", "")).startswith(exp["status_prefix"])}
    return {"passed": all(checks.values()), "checks": checks, "wrong": wrong,
            "got": {"status": rec.get("status"), "reason": rec.get("reason")}}


def _run_matrix_drift_case(case: dict) -> dict:
    """Ordinary maintenance of the matrix doc must break loudly, not quietly.

    Each variant is an edit a future milestone would plausibly make. A variant
    that parses without raising is a document that silently declared nothing."""
    from .server import MATRIX_DOC, parse_matrix

    src = MATRIX_DOC.read_text(encoding="utf-8")
    quiet = []
    for v in case["input"]["variants"]:
        old, new = v["replace"]
        if old not in src:
            return {"passed": False, "error": f"variant anchor not in the doc: {old!r}"}
        try:
            got = parse_matrix(src.replace(old, new))
        except ValueError:
            continue  # loud — what we want
        quiet.append({"note": v["note"], "rows": len(got["rows"]),
                      "limitations": len(got["limitations"])})
    return {"passed": not quiet, "wrong": {"parsed_quietly": quiet}}


def _check_supersede_dangling() -> dict:
    """No emitted trace may point superseded_by at a step that does not exist.

    Drives a real run into the action budget one step after a replan — the path
    that produced the dangling pointer, and the one where verify() is never
    called, so the verifier's own supersedes_resolve gate cannot catch it."""
    from . import agent as A

    base, orig = _base_url(), dict(A.RUN_BUDGETS)
    A.RUN_BUDGETS["actions"] = 2  # pre-plan navigate + the failing click
    plans = [
        [{"action": "click", "target": {"role": "button", "name": "Sort by price (low to high)"},
          "expected_state": {"text_visible": "never rendered"}},
         {"action": "extract", "target": {"role": "link", "index": 0}}],
        [{"action": "extract", "target": {"role": "link", "index": 0}}],
    ]
    try:
        with tempfile.TemporaryDirectory() as run_dir:
            result = asyncio.run(run_task(
                "Sort by price and name the cheapest.", f"{base}/fixtures/shop.html",
                stub_planner(plans), run_dir))
    finally:
        A.RUN_BUDGETS.clear()
        A.RUN_BUDGETS.update(orig)

    trace = result["evidence"]["trace"]
    present = {s["i"] for s in trace}
    dangling = [{"i": s["i"], "superseded_by": s["superseded_by"]} for s in trace
                if s.get("superseded_by") and s["superseded_by"] not in present]
    return {"passed": not dangling, "wrong": {"dangling": dangling},
            "got": {"status": result["status"], "steps": len(trace)}}


def run_case(case: dict) -> dict:
    kind = case["input"].get("kind")
    if kind == "matrix-drift":
        return _run_matrix_drift_case(case)
    if kind == "gateway-error":
        return _run_gateway_error_case(case)
    if kind == "stream":
        return _run_stream_case(case)
    if kind == "matrix":
        return _run_matrix_case(case)
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
