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
from .planner import live_planner, stub_planner
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


def _subst(obj, url: str):
    """`$FIXTURE_URL` in a stub plan -> the URL this run's fixture is served from."""
    return json.loads(json.dumps(obj).replace("$FIXTURE_URL", url))


def _run_agent(task: str, url: str | None, planner, **kw) -> dict:
    """One agent run in a throwaway run dir — what every E2E-shaped case needs.
    The dir is temporary because the eval grades the returned result and the
    trace inside it; the on-disk artifacts are for a human debugging a real run."""
    with tempfile.TemporaryDirectory() as run_dir:
        return asyncio.run(run_task(task, url, planner, run_dir, **kw))


# --- pure-code invariant checks --------------------------------------------
# Inert fixtures: assemble_result reads a trace only for emptiness and each
# step's `screenshot`, so one step and one budget dict serve every check here.
_TRACE = [{"i": 1, "action": "extract", "postcondition_ok": True, "screenshot": None}]
_BUDGETS = {"actions": 1, "llm_tokens": 0, "llm_usd": 0.0, "ms": 1}


def _check_inv0() -> dict:
    """INV-0: a completed run with empty output must not report success."""
    r = assemble_result(trace=_TRACE, answer="", budgets=_BUDGETS)
    return {"passed": r["status"] != "success", "status": r["status"]}


CLASSES = ["nav", "locate", "act", "extract", "semantic", "env", "task"]


def _check_inv1() -> dict:
    """INV-1: every non-success status carries exactly one known class."""
    wrong = []
    for cls in CLASSES:
        st = assemble_result(trace=_TRACE, answer="a", budgets=_BUDGETS,
                             failure=cls)["status"]
        if st != f"failure:{cls}" or st.count(":") != 1:
            wrong.append((cls, st))
    st = assemble_result(trace=_TRACE, answer="a", budgets=_BUDGETS,
                         failure="unsupported")["status"]
    if st != "unsupported":
        wrong.append(("unsupported", st))
    return {"passed": not wrong, "wrong": wrong}


def _check_inv2() -> dict:
    """INV-2: a FAIL/INCONCLUSIVE verdict can never be reported as success."""
    bad = []
    for v in ("FAIL", "INCONCLUSIVE"):
        r = assemble_result(trace=_TRACE, answer="an answer", budgets=_BUDGETS,
                            verdict={"verdict": v, "reason": "planted"})
        if r["status"] == "success":
            bad.append(v)
    ok = assemble_result(trace=_TRACE, answer="an answer", budgets=_BUDGETS,
                         verdict={"verdict": "PASS", "reason": None})
    return {"passed": not bad and ok["status"] == "success", "leaked": bad}


def _check_evidence_window_miss_bounded() -> dict:
    """evidence_window must still return a bounded window when the value is
    absent from the body on a page longer than PAGE_TEXT_KEEP — that window
    is what `grounded` then correctly fails on. No browser: a pure probe of
    the function itself (agent.py:170)."""
    from .agent import PAGE_TEXT_KEEP, evidence_window

    body = "x" * (PAGE_TEXT_KEEP + 1000)
    win = evidence_window(body, "VALUE-NOT-ON-PAGE")
    wrong = []
    if len(win) > PAGE_TEXT_KEEP:
        wrong.append(f"window length {len(win)} exceeds PAGE_TEXT_KEEP {PAGE_TEXT_KEEP}")
    if win != body[:PAGE_TEXT_KEEP]:
        wrong.append("window is not the head of the page when the value is absent")
    return {"passed": not wrong, "wrong": wrong, "window_len": len(win)}


def _check_dump_ratio_anchor_flip() -> dict:
    """`not_a_dump`'s denominator must be the real page (`body_len`), not the
    stored evidence window -- which agent.py caps at PAGE_TEXT_KEEP and can
    double when a distant `anchor` forces a second window onto it (agent.py:
    171-173). Reviewer-reported defect: the SAME value on the SAME page
    flipped FAIL -> PASS depending only on whether the plan carried a distant
    anchor, because the window (not the page) was the denominator. Pure probe
    of evidence_window() and verify() directly, no browser."""
    from .agent import evidence_window
    from .verifier import verify

    value = "V" * 776
    anchor = "ANCHOR_TOKEN"
    body = "p" * 2000 + value + "m" * 1000 + anchor + "a" * 600
    win_plain = evidence_window(body, value)
    win_anchored = evidence_window(body, value, anchor)
    trace = [{"i": 1, "action": "extract", "postcondition_ok": True}]

    def not_a_dump(page_text, body_len=None):
        e = {"value": value, "page_text": page_text}
        if body_len is not None:
            e["body_len"] = body_len
        return verify(trace=trace, extractions=[e], answer=value)["checks"]["not_a_dump"]

    wrong = []
    if win_plain == win_anchored:
        wrong.append("windows must differ (anchor must force a second window) for this probe to mean anything")
    # With body_len supplied -- what agent.py now records at extraction time --
    # both windows are judged against the same real page, so the verdict must
    # not depend on which window happened to get stored.
    plain_ok, anchored_ok = not_a_dump(win_plain, len(body)), not_a_dump(win_anchored, len(body))
    if plain_ok != anchored_ok:
        wrong.append(f"verdict still depends on the anchor with body_len present: "
                     f"plain={plain_ok} anchored={anchored_ok}")
    # The true page fraction (776/4388 ~= 0.18) is well under DUMP_RATIO, so a
    # correct fix reads this as a real answer, not a dump, on either window.
    if not plain_ok or not anchored_ok:
        wrong.append(f"body_len-denominated ratio should read as a real answer: plain={plain_ok} anchored={anchored_ok}")
    return {"passed": not wrong, "wrong": wrong,
            "win_plain_len": len(win_plain), "win_anchored_len": len(win_anchored)}


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
    r = assemble_result(trace=_TRACE, answer="a",
                        budgets={"actions": 30, "llm_tokens": 0, "llm_usd": 0.0,
                                 "replans": 0, "ms": 1},
                        failure="env", reason=budget_stop({"actions": 30}))
    if r["status"] != "failure:env" or not r["reason"] or not r["evidence"]["trace"]:
        wrong.append(f"exhaustion was not a loud classified failure: {r['status']}")
    return {"passed": not wrong, "wrong": wrong}


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
    from .mutate import MUTATIONS, apply_mutation

    src = (FIXTURES / case["input"]["fixture"]).read_text()
    # Coverage first: the catalogue's own docstring claims every entry in its
    # table is pinned here, and that held by coincidence — this case graded
    # whatever blocks it happened to list, so a new mutation added without one
    # would ship unguarded and green (PR #12, R11). Missing BOTH ways: a
    # mutation with no checks block is unguarded, a checks block naming no
    # mutation is a guard pointed at nothing.
    wrong = [{"uncovered_mutations": sorted(set(MUTATIONS) - set(case["input"]["checks"]))}] \
        if set(MUTATIONS) - set(case["input"]["checks"]) else []
    wrong += [{"checks_for_unknown_mutation": sorted(set(case["input"]["checks"]) - set(MUTATIONS))}] \
        if set(case["input"]["checks"]) - set(MUTATIONS) else []
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
    fixture_url = f"{_base_url()}/fixtures/{inp['fixture']}"
    steps = _subst(inp["stub_plan"], fixture_url)
    result = _run_agent(inp["task"], fixture_url, stub_planner([steps]))

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
    # This probe only exercises supersede resolution — the evidence content is
    # irrelevant to what it tests. A bare {"value": "a", "page_text": "a"} has
    # a dump ratio of 1.0 (the value IS the whole window), which reads as a
    # page dump to `not_a_dump` and once made this case fail for an unrelated
    # reason: the placeholder scaffolding looked like a dump, not the run
    # (ADR-008). Padded to a realistic evidence-window length so the ratio
    # sits nowhere near DUMP_RATIO.
    _INERT_PAGE_TEXT = (
        "ok — inert placeholder evidence, padded to a realistic "
        "evidence-window length so the dump ratio sits nowhere near the "
        "DUMP_RATIO threshold; this probe only exercises supersede "
        "resolution, not evidence content (see ADR-008)."
    )
    for sc in inp.get("superseded", []):
        v = verify(trace=sc["trace"], extractions=[{"value": "ok", "page_text": _INERT_PAGE_TEXT}], answer="ok")
        if (v["verdict"] == "PASS") != sc["pass"]:
            wrong.append({"superseded": sc["note"], "should_pass": sc["pass"],
                          "verdict": v["verdict"], "checks": v["checks"]})
    # Same padding, for the same reason: measured at ratio 0.27-0.32 unpadded
    # (M7 phase 2), too close to DUMP_RATIO=0.35 for comfort even though this
    # probe checks the `identity_anchors` key specifically, not the overall
    # verdict. Filler contains none of the anchor strings under test, so it
    # cannot change which anchors are present or absent.
    _ANCHOR_PADDING = (
        " Additional inert catalogue filler appended so this scaffolded "
        "page_text reads at a realistic evidence-window length rather than "
        "a synthetic short string whose dump ratio is noise near the "
        "threshold (see ADR-008)."
    )
    for sc in inp.get("anchors", []):
        v = verify(
            trace=[{"i": 1, "action": "extract", "postcondition_ok": True}],
            extractions=[{"value": sc["answer"], "page_text": t + _ANCHOR_PADDING} for t in sc["page_texts"]],
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
            # Deliberately NOT agent.navigate(): production asks "is this page
            # usable enough to act on?", observe ground truth asks "what does a
            # fully settled page expose?". Forcing one navigation semantics onto
            # both leaks the production abstraction into the harness, and an
            # observation taken mid-load would make these cases flake rather
            # than grade. Strict `load` is the right contract here.
            #
            # ponytail: strict, but on Playwright's 30s DEFAULT rather than a
            # budget anyone chose. Pointed at `slow-asset.html` — whose `load`
            # never fires, and which lives in this same fixtures directory —
            # this raises after 30.4s and the runner reports a traceback, so an
            # incompatible fixture reads as "the observer broke" instead of
            # "this fixture is not a valid strict-observe subject". Ceiling:
            # diagnosability, not correctness — no production path and no
            # existing case touches it. Upgrade: keep strict `load`, give it an
            # explicit 5-10s eval budget, catch PlaywrightTimeoutError and
            # return {"passed": False, "failure": "eval_env", "reason": ...}.
            # Do NOT route through navigate(): that changes the ground-truth
            # contract. Same lesson as the screenshot bound one level up —
            # try/except bounds error propagation, never latency.
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
    plans = _subst(plans, fixture_url or "")
    # An injected marker predicate, not the production url_ok: fixtures are
    # served on loopback and the real guard blocks loopback, so passing url_ok
    # here would fail every fixture case for the wrong reason. This grades that
    # the guard is CONSULTED as the browser moves; url-guard-literal-ips grades
    # what it decides.
    guard = (lambda u: inp["block_host"] not in u) if inp.get("block_host") else None
    # `planner: "live"` spends real tokens against the real model, so only a
    # `full`-tagged case may ask for it. No key -> live_planner raises here and
    # the case fails loudly; stubbing it would grade a capability nobody ran
    # (CLAUDE.md rule 4).
    planner = live_planner() if inp.get("planner") == "live" else stub_planner(plans)
    result = _run_agent(inp["task"], inp.get("url", fixture_url), planner, url_guard=guard)

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
        metrics.update(mutation_metrics(exp, result["status"], trace))
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


def mutation_metrics(exp: dict, status: str, trace: list) -> dict:
    """Mutation counters for one L4 case — extracted so they can be graded.

    They were inline in `_run_fixture_case`, where nothing could assert them:
    the case's own `passed` never reads `metrics`, so the whole published
    "mutation N/M passed, K by relocating" line rested on code with no case
    behind it (case mutation-metrics-honesty).
    """
    # Surviving a mutation means the run ended in a real answer. Three separate
    # things can make that false, and each of them was counted as a survival at
    # some point in M8's history:
    #   1. the run did not succeed — the second term used to be "matched its
    #      expectation", so a case that expected AND got failure:locate landed
    #      in the numerator (PR #12, R8). `l4-shop-render-delayed` is now
    #      excluded by its status alone, without needing the opt-in key;
    #   2. the case expected a failure and the agent succeeded anyway — a
    #      regression that makes the case red, and is not a survival to publish;
    #   3. the case declares the run a loss even though it "succeeded": the
    #      wrong-answer pin `l4-shop-element-reordered`, which is what
    #      `mutation_survived: false` is for and the only remaining use of it.
    survived = (status == "success" and exp.get("status", "success") == "success"
                and bool(exp.get("mutation_survived", True)))
    # A rescue is a labelled attempt that WORKED. Every relocation rung wears
    # `retry_or_recovery: "recovery"` and supersedes the attempt before it,
    # including the rungs that lose, so counting labels rather than successes
    # credited relocation for a run where all rungs failed and the replan made
    # the save (PR #12, R7).
    rescues = [s for s in trace
               if s.get("retry_or_recovery") == "recovery" and not s.get("failure_class")]
    # `recovery` is worn by BOTH ladders, so the label cannot say which one ran.
    # The attempt a rescue supersedes can: a `locate` failure is the relocation
    # ladder (a different tier), an `act` failure is the replan ladder (a
    # different plan). l4-shop-overlay-modal is rescued without any tier ever
    # changing — its four resolved tiers are all `role` — and it was published
    # inside "N by relocating", the count ADR-002 introduced precisely to keep
    # the flattering reading out (PR #12, R1).
    failed = {s["superseded_by"]: s for s in trace if s.get("superseded_by")}
    relocated = [s for s in rescues if failed.get(s["i"], {}).get("failure_class") == "locate"]
    # Both recovery counters are gated on survival: a run that lost is not a
    # rescue, whatever its trace tried on the way down (PR #12, R3). Rungs
    # tried are still reported, separately, as raw context.
    return {
        "mutation_cases": 1,
        "mutation_passed": int(survived),
        "mutation_recovered": int(survived and bool(rescues)),
        "mutation_relocated": int(survived and bool(relocated)),
    }

def _check_mutation_metrics() -> dict:
    """The mutation counters must count what their label says.

    Pure code over synthetic traces — the shapes are taken from real runs, so
    each row names the case it was measured from. Rows 2 and 4 are the ones no
    browser case can assert: a replan-family rescue must not be counted as a
    relocation, and a run that did not survive must not appear in any recovery
    numerator (its rungs were tried and lost).
    """
    def reloc_trace(cls):  # step 2 fails, step 3 is the labelled rescue
        return [{"i": 2, "failure_class": cls, "superseded_by": 3},
                {"i": 3, "retry_or_recovery": "recovery"}]

    # The relocation ladder tried, every rung lost, and the replan family made
    # the save. Every rung wears the `recovery` label and supersedes the
    # original `locate` failure, so any predicate that only reads "was a locate
    # failure superseded by a labelled step" credits relocation for a rescue it
    # did not make (PR #12, R7; measured on shop.html?mut=overlay-modal with a
    # role-less first target).
    rungs_lost_replan_won = [
        {"i": 1, "failure_class": "locate", "superseded_by": 2},
        {"i": 2, "retry_or_recovery": "recovery", "failure_class": "act", "superseded_by": 3},
        {"i": 3, "retry_or_recovery": "recovery"},
    ]

    rows = [
        ("relocation rescue (l4-shop-duplicate-labels)", {}, "success", reloc_trace("locate"),
         {"mutation_cases": 1, "mutation_passed": 1, "mutation_recovered": 1, "mutation_relocated": 1}),
        ("replan rescue, nothing relocated (l4-shop-overlay-modal)", {}, "success", reloc_trace("act"),
         {"mutation_cases": 1, "mutation_passed": 1, "mutation_recovered": 1, "mutation_relocated": 0}),
        ("declared non-survivor (l4-shop-element-reordered)", {"mutation_survived": False}, "success", [],
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("non-survivor that still tried a rung", {"mutation_survived": False}, "success", reloc_trace("locate"),
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("expected failure, correctly diagnosed (l4-shop-render-delayed)",
         {"status": "failure:locate", "mutation_survived": False}, "failure:locate", reloc_trace("locate"),
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("survived with nothing to recover (l4-shop-ids-renamed)", {}, "success", [],
         {"mutation_cases": 1, "mutation_passed": 1, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("rungs lost, replan won (PR #12, R7)", {}, "success", rungs_lost_replan_won,
         {"mutation_cases": 1, "mutation_passed": 1, "mutation_recovered": 1, "mutation_relocated": 0}),
        ("expected failure, no mutation_survived key (PR #12, R8)",
         {"status": "failure:locate"}, "failure:locate", [],
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("expected failure, agent succeeded anyway", {"status": "failure:locate"}, "success", [],
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
        ("expected success, run failed", {}, "failure:locate", reloc_trace("locate"),
         {"mutation_cases": 1, "mutation_passed": 0, "mutation_recovered": 0, "mutation_relocated": 0}),
    ]
    wrong = [{"row": note, "want": want, "got": got}
             for note, exp, status, trace, want in rows
             if (got := mutation_metrics(exp, status, trace)) != want]
    return {"passed": not wrong, "wrong": wrong}


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
    steps = _subst(inp["stub_plan"], fixture_url)

    live: list[dict] = []
    result = _run_agent(
        inp["task"], fixture_url, stub_planner([steps]),
        # Copy on arrival: the executor mutates its record after emitting
        # (screenshot, ms, superseded_by). Holding the live reference would
        # compare the final trace against itself and pass unconditionally.
        on_step=lambda rec: live.append(json.loads(json.dumps(rec))),
    )
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
        result = _run_agent("Sort by price and name the cheapest.",
                            f"{base}/fixtures/shop.html", stub_planner(plans))
    finally:
        A.RUN_BUDGETS.clear()
        A.RUN_BUDGETS.update(orig)

    trace = result["evidence"]["trace"]
    present = {s["i"] for s in trace}
    dangling = [{"i": s["i"], "superseded_by": s["superseded_by"]} for s in trace
                if s.get("superseded_by") and s["superseded_by"] not in present]
    return {"passed": not dangling, "wrong": {"dangling": dangling},
            "got": {"status": result["status"], "steps": len(trace)}}


LABELS_PATH = Path(__file__).parents[2] / "evals" / "labels" / "verifier-sample.jsonl"


def _run_verifier_labels_case(case: dict) -> dict:
    """M7 verifier accuracy: replays the hand-labeled sample through the exact
    runtime call agent.py makes (no `expect`, no `state` — docs/evals/
    evaluation-methodology.md "Verifier accuracy estimation"), and grades the
    verifier's PASS/FAIL against a human label of the ANSWER, never against
    what the run itself claimed. Offline and frozen: it replays committed
    JSONL, so it is `fast`-tagged even though half the records came from live
    sites originally (evals/labels/capture.py)."""
    records = [json.loads(line) for line in LABELS_PATH.read_text().splitlines() if line.strip()]
    tp = fp = fn = tn = 0
    fp_ids, fn_ids = [], []
    for r in records:
        v = verify(trace=r["trace"], extractions=r["extractions"], answer=r["answer"])
        predicted_pass, actually_correct = v["verdict"] == "PASS", r["label"] == "correct"
        if predicted_pass and actually_correct:
            tp += 1
        elif predicted_pass:
            fp += 1
            fp_ids.append(r["id"])
        elif actually_correct:
            fn += 1
            fn_ids.append(r["id"])
        else:
            tn += 1
    matrix = {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return {
        "passed": matrix == case["expect"]["matrix"],
        "matrix": matrix,
        "want_matrix": case["expect"]["matrix"],
        "metrics": {
            "precision": tp / (tp + fp) if (tp + fp) else None,
            "recall": tp / (tp + fn) if (tp + fn) else None,
            "n": len(records),
            "false_positive_ids": fp_ids,
            "false_negative_ids": fn_ids,
        },
    }


def _run_url_guard_case(case: dict) -> dict:
    from .server import url_ok

    wrong = [u for u, want in case["input"]["checks"] if url_ok(u) != want]
    return {"passed": not wrong, "wrong": wrong}


def _run_screening_case(case: dict) -> dict:
    from .agent import screen

    wrong = [t for t, want in case["input"]["checks"] if (screen(t) is not None) != want]
    return {"passed": not wrong, "wrong": wrong}


def _run_parse_plan_case(case: dict) -> dict:
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


INVARIANTS = {"inv0": _check_inv0, "inv1": _check_inv1, "inv2": _check_inv2,
              "inv3": _check_inv3, "supersede-dangling": _check_supersede_dangling,
              "evidence-window-miss-bounded": _check_evidence_window_miss_bounded,
              "mutation-metrics": _check_mutation_metrics,
              "dump-ratio-anchor-flip": _check_dump_ratio_anchor_flip}


def _run_invariant_case(case: dict) -> dict:
    check = case["input"]["check"]
    if check not in INVARIANTS:
        return {"passed": False, "error": f"unknown invariant check {check}"}
    return INVARIANTS[check]()


# `input.kind` -> runner. An unknown kind is a fixture E2E case, which is the
# default shape; every other kind names the narrower thing it grades.
KINDS = {
    "classify": _run_classify_case,
    "gateway-error": _run_gateway_error_case,
    "invariant": _run_invariant_case,
    "matrix": _run_matrix_case,
    "matrix-drift": _run_matrix_drift_case,
    "mutation": _run_mutation_case,
    "observe": _run_observe_case,
    "parse-plan": _run_parse_plan_case,
    "relocate": _run_relocate_case,
    "schema": _run_schema_case,
    "screening": _run_screening_case,
    "stream": _run_stream_case,
    "url-guard": _run_url_guard_case,
    "verifier": _run_verifier_case,
    "verifier-labels": _run_verifier_labels_case,
}


def run_case(case: dict) -> dict:
    return KINDS.get(case["input"].get("kind"), _run_fixture_case)(case)
