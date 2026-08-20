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
- `gateway-model` — `POST /tasks`'s model allowlist, and that the model actually
  reaches the planner factory (the planner is swapped for a recorder: $0.00)
- `ablation-table` — the M9 cost/model table in docs/analysis.md carries no
  number that no committed report produced (pure code, no browser)
- (default)      — fixture E2E: real agent, real browser, planner stubbed at the
  module boundary. `$FIXTURE_URL` in a step value is substituted with the served
  fixture URL; `mut` selects a mutation; `reset_form` clears TC5 ground truth.

The fixture sites are served by the real FastAPI app on loopback (started once
per process) so eval and production exercise the same serving path.
"""

import asyncio
import json
import re
import socket
import tempfile
import threading
import time
import urllib.error
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

    out = {
        "passed": all(checks.values()),
        "checks": checks,
        "audit": audit,
        "metrics": metrics,
        "tiers": [s["resolved"]["tier"] for s in trace if s.get("resolved")],
        "got": {"status": result["status"], "answer": result["answer"],
                "reason": result["reason"]},
        "budgets": result["budgets_spent"],
    }
    # A case may pin the WRONG answer as its expectation, because that is what
    # the build really produces (l4-shop-element-reordered,
    # live-quotes-js-role-tier-blind). `expect.answer` is layer-2 ground truth
    # to verify(), so such a run publishes a fully green audit —
    # `answer_matches: true`, `ground_truth: true` — for an answer every
    # document here calls wrong. The prose said so; the committed report did
    # not, and "hostile results published raw" is a claim about the artifact
    # (PR #12, R14). This key travels with the result into evals/report/*.json
    # so a reader with jq and no prose cannot read that PASS as "verified
    # correct".
    if exp.get("answer_is_known_wrong"):
        out["known_wrong_ground_truth"] = (
            "expect.answer pins the WRONG answer this build produces; a PASS here means "
            "'the agent reproduced the known-wrong answer', never 'the answer is correct'")
    return out


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
    # ponytail: the family is read from the IMMEDIATELY superseded attempt only.
    # Ceiling (PR #12, R15, declared not fixed — support-matrix D11): if rung 1
    # retargets at a new tier and then fails `act` — the laundering shape
    # live-ol-search-a11y-invisible records — and rung 2 wins, the rescue's
    # predecessor reads `act` and a real relocation is not counted. Undercount,
    # never a flatter; no case in the suite produces it today. Upgrade: walk the
    # supersede chain back to the failure that started the ladder, with a row in
    # mutation-metrics-honesty pinning the intended answer first.
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


def _run_declared_keys_case(case: dict) -> dict:
    """Which cases carry an opt-in `expect` key is a documented fact — grade it.

    Both keys exist to make a case say something the harness cannot infer, and
    both are described in prose that has already gone stale once: the
    methodology doc still claimed `mutation_survived` kept two cases out of the
    survival numerator, a round after one of them stopped using it (PR #12,
    R12). Sets, not counts, so the failure names the file.

    ponytail: this grades the CASE FILES against a declared list, not the prose
    that describes them — editing the markdown back to the stale claim leaves
    the suite green (PR #12, R17). Parsing the doc the way parse_matrix parses
    the support matrix is the upgrade, and it needs the doc to carry a
    machine-readable shape first.
    """
    evals_dir = Path(__file__).parents[2] / "evals"
    # rglob and the case's own `id`, matching how evals/run.py discovers and
    # names cases — filenames equal ids today, and a guard that quietly stopped
    # seeing a subdirectory would be the same silence it exists to prevent.
    cases = [json.loads(p.read_text(encoding="utf-8"))
             for d in ("golden", "adversarial") for p in (evals_dir / d).rglob("*.json")]
    files = {c.get("id", "<unnamed>"): c for c in cases}
    wrong = []
    for key, want in case["input"]["declared"].items():
        # Presence, not truthiness: `mutation_survived` is meaningful precisely
        # when it is `false`, so a `.get(key)` test finds nobody carrying it.
        got = sorted(cid for cid, c in files.items() if key in (c.get("expect") or {}))
        if got != sorted(want):
            wrong.append({"key": key, "declared": sorted(want), "actual": got})
    # A pin with no `expect.answer` marks nothing: the key only means anything
    # where an answer is being asserted as ground truth.
    empty = sorted(cid for cid, c in files.items()
                   if (c.get("expect") or {}).get("answer_is_known_wrong")
                   and "answer" not in (c.get("expect") or {}))
    if empty:
        wrong.append({"key": "answer_is_known_wrong", "marks_nothing_no_expect_answer": empty})
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


def _run_gateway_model_case(case: dict) -> dict:
    """`POST /tasks`'s `model` field: allowlisted or loudly refused, never dropped.

    Two things need proving and neither is visible from outside the process. That
    a non-allowlisted model is refused *before* a run exists — `/tasks` is public
    and unauthenticated, so an unbounded model field is a stranger pointing this
    deployment's key at the priciest model on OpenRouter. And that an allowlisted
    one actually reaches `live_planner`, because a parameter that is accepted and
    silently ignored looks identical from the HTTP side to one that works, and
    would make the whole M9 ablation measure the default model four times.

    `server.live_planner` is swapped for a recorder that captures the model and
    raises, so the gateway's catch-all turns the run into a classified failure
    without a browser, a network call, or a cent of spend (cost-discipline rule
    4). The recorder replaces a module attribute from the eval side — it is not
    a stub backdoor added to a public endpoint, which is the trade
    `_run_stream_case` declines — a policy this PR briefly broke and then
    honoured: the mismatched-model simulation in `_run_ablation_run_one_case`
    wraps `agent.assemble_result` from here rather than the eval-only branch it
    first put in `server._execute` (PR #15, R13)."""
    from . import server as S

    seen: list = []

    def recorder(model=None):
        seen.append(model)
        raise RuntimeError("eval recorder: planner never constructed")

    base, prev = _base_url(), S.live_planner
    wrong = []
    # The allowlist and the frozen verification evidence must name the same four
    # models. Without this the ADR's "every id verified against OpenRouter on
    # <date>" is a claim about a list that can be edited independently of the
    # snapshot it was verified from (spec-drift audit, M9).
    if verified := case["input"].get("verified_ids_file"):
        from .planner import ABLATION_MODELS, ALLOWED_MODELS, CEILING_MODEL, DEFAULT_MODEL

        snap = json.loads((Path(__file__).parents[2] / verified).read_text(encoding="utf-8"))
        snap_ids = [m["id"] for m in snap["models"]]
        if snap_ids != list(ALLOWED_MODELS):
            wrong.append({"allowlist": list(ALLOWED_MODELS), "verified_snapshot": snap_ids,
                          "read_on": snap.get("_read_on")})
        # The owner's ceiling, DERIVED from the snapshot rather than compared
        # against a second copy of the same numbers. The old version held a
        # literal in planner.py and checked the snapshot against it, so it could
        # only ever detect the two transcriptions disagreeing — never that the
        # ceiling model had moved in reality, which is exactly what happened
        # (PR #15, R16). Now there is one source, and the ruling it encodes is
        # "the ceiling is the model": whatever `CEILING_MODEL` lists for is the
        # bar, and every other ablated model must sit at or under it.
        if case["input"].get("price_ceiling"):
            price = {m["id"]: m["pricing"] for m in snap["models"]}
            if CEILING_MODEL not in ABLATION_MODELS or CEILING_MODEL not in price:
                wrong.append({"ceiling_model_missing": CEILING_MODEL,
                              "note": "the ceiling is defined by a model that must be both "
                                      "ablated and frozen; nothing else can derive from it"})
            else:
                ceiling = {k: float(price[CEILING_MODEL][k]) for k in ("prompt", "completion")}
                wrong += [{"over_the_owner_ceiling": mid, "field": k,
                           "list_price": price[mid][k], "ceiling_model": CEILING_MODEL,
                           "ceiling": cap}
                          for mid in ABLATION_MODELS for k, cap in ceiling.items()
                          if mid in price and float(price[mid][k]) > cap]
                # The other direction, and the one that keeps ADR-010 Decision 6
                # honest: the incumbent must still be OVER the bar. If a price
                # move ever brought it under, the exclusion needs re-deciding,
                # not re-asserting.
                if all(float(price[DEFAULT_MODEL][k]) <= cap for k, cap in ceiling.items()):
                    wrong.append({"default_now_fits_the_ceiling": DEFAULT_MODEL,
                                  "pricing": price[DEFAULT_MODEL], "ceiling": ceiling})
    # The swap goes INSIDE the try whose finally restores it. It used to sit above
    # the snapshot block, so a renamed or malformed snapshot file raised with the
    # recorder still installed, breaking every later case in the same process and
    # attributing the damage to unrelated cases (PR #15, R6).
    S.live_planner = recorder
    try:
        for chk in case["input"]["checks"]:
            payload = {"task": case["input"]["task"]}
            # `model: null` in a case file means "omit the field"; the sentinel is
            # how a case says "send an explicit JSON null", which is a different
            # request and, since PR #15 R8, a pinned one.
            if chk.get("model") == "__EXPLICIT_NULL__":
                payload["model"] = None
            elif chk.get("model") is not None:
                payload["model"] = chk["model"]
            before = len(seen)
            try:
                req = urllib.request.Request(
                    f"{base}/tasks", data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as r:
                    code, body = r.status, json.load(r)
            except urllib.error.HTTPError as e:
                code, body = e.code, json.loads(e.read().decode() or "{}")
            got = {"http": code}
            if code == 200:
                for _ in range(200):  # let the run reach the recorder and terminate
                    if _get_json(f"/tasks/{body['run_id']}").get("status") != "running":
                        break
                    time.sleep(0.05)
                else:
                    wrong.append({"model": chk.get("model"), "note": "run never left 'running'"})
            else:
                got["detail"] = body.get("detail")
            got["planner_model"] = seen[before] if len(seen) > before else None
            want = {"http": chk["http"], "planner_model": chk["planner_model"]}
            if chk.get("detail_contains"):
                want["detail"] = chk["detail_contains"]
                got["detail"] = chk["detail_contains"] if chk["detail_contains"] in str(
                    got.get("detail")) else got.get("detail")
            if {k: got.get(k) for k in want} != want:
                wrong.append({"model": chk.get("model"), "want": want,
                              "got": {k: got.get(k) for k in want}})
    finally:
        S.live_planner = prev
    return {"passed": not wrong, "wrong": wrong, "recorded_models": seen}


def _run_ablation_run_one_case(case: dict) -> dict:
    """`failure:env` is four different events, and the table must not conflate them.

    `agent.py` returns `failure:env` for a missing key, a provider 4xx, a planner
    that emitted prose instead of a plan, a replan that raised, and a run that
    exhausted its budgets — and returns `failure:nav` for a page that would not
    load, before the planner is ever called. Some of those are the environment
    and must abort the sweep; the rest are planning quality and ARE the
    measurement. Getting the split wrong publishes a provider outage or a dead
    site as a model's incompetence (PR #15, R9 and R14) or a model's incompetence
    as free (R10) — all of them land in the same cells of the same table.

    Four halves, because each covers a shape the others cannot reach:
      - `checks`: truth table over `evals.ablation.is_measurement`, an ALLOWLIST
        of statuses that say something about the model (default-deny);
      - `e2e`: a real `run_one` whose planner reports usage and then emits prose.
        Must come back SCORED, and must carry the cost the provider billed;
      - `e2e_fatal`: a real `run_one` whose planner raises `HTTPError 402`. Must
        abort — this is the shape a truth table alone let through for a round;
      - `model_echo`: a gateway attributing the run to a different model. Must
        abort (R4).
    """
    import evals.ablation as AB

    from . import agent as A
    from . import server as S
    from .planner import PlanError, stub_planner

    inp, wrong = case["input"], []
    # `live_planner` is where the usage is built and where the ordering bug was.
    # The e2e half below raises a PlanError the CASE constructs, so it cannot see
    # that ordering at all — reverting the production fix left this case green
    # until this probe existed (PR #15, R10, discrimination pass).
    # Envelopes the planner cannot recognise. These are NOT the model answering
    # badly — they are the response not being an OpenRouter response — so they
    # must stay ordinary exceptions and abort the sweep. Default-deny: only a
    # positively-recognised "the model answered, and the answer is not a plan"
    # gets scored (PR #15, R18).
    for env in inp.get("planner_envelope", []):
        import io
        import os

        from . import planner as P

        body = json.dumps(env["body"]).encode()
        prev_open, prev_key = P.urllib.request.urlopen, os.environ.get("OPENROUTER_API_KEY")
        P.urllib.request.urlopen = lambda *a, _b=body, **k: io.BytesIO(_b)
        os.environ["OPENROUTER_API_KEY"] = "eval-probe-not-a-key"
        try:
            asyncio.run(P.live_planner("tencent/hy3")("t", "https://example.com"))
            wrong.append({"envelope": env["note"], "note": "accepted as a plan"})
        except P.PlanError as e:
            wrong.append({"envelope": env["note"],
                          "classed_as_the_models_fault": str(e)[:120],
                          "would_be_scored": AB.is_measurement(
                              "failure:env", f"planner rejected: {e}"),
                          "note": "an unrecognised envelope is the environment, not the model; "
                                  "scoring it publishes an outage as a 0/5 cell"})
        except Exception as e:
            if AB.is_measurement("failure:env", f"planner failed: {e}"):
                wrong.append({"envelope": env["note"],
                              "aborts": False, "reason": f"planner failed: {e}"[:120]})
        finally:
            P.urllib.request.urlopen = prev_open
            if prev_key is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = prev_key

    for probe in inp.get("planner_usage", []):
        import io
        import os

        from . import planner as P

        # Every shape of "the response arrived and carried no plan". They all
        # cost money and they must all read as the model's doing, not the
        # environment's — `content: null` did not, because the extraction sat one
        # line above the guarded block (PR #15, R15).
        if "choices" in probe:
            payload = {"choices": probe["choices"], "usage": probe["usage"]}
        else:
            msg = probe.get("message", {"content": probe.get("content")})
            choice = {"message": msg}
            if probe.get("finish_reason"):
                choice["finish_reason"] = probe["finish_reason"]
            payload = {"choices": [choice], "usage": probe["usage"]}
        body = json.dumps(payload).encode()
        prev_open, prev_key = P.urllib.request.urlopen, os.environ.get("OPENROUTER_API_KEY")
        P.urllib.request.urlopen = lambda *a, **k: io.BytesIO(body)
        os.environ["OPENROUTER_API_KEY"] = "eval-probe-not-a-key"
        try:
            asyncio.run(P.live_planner("tencent/hy3")("t", "https://example.com"))
            wrong.append({"live_planner_accepted_a_response_with_no_plan": probe["note"]})
        except P.PlanError as e:
            if e.usage != probe["expect_usage"]:
                wrong.append({"probe": probe["note"], "billed_usage_dropped": e.usage,
                              "provider_reported": probe["expect_usage"]})
            if not AB.is_measurement("failure:env", f"planner rejected: {e}"):
                wrong.append({"probe": probe["note"],
                              "note": "PlanError raised but the driver would not score it"})
        except Exception as e:
            wrong.append({"probe": probe["note"],
                          "not_a_PlanError": f"{type(e).__name__}: {e}",
                          "note": "the response arrived and carried no plan; classing it as a "
                                  "transport failure aborts the sweep and discards the billed cost"})
        finally:
            P.urllib.request.urlopen = prev_open
            if prev_key is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = prev_key
    # Every prefix `is_measurement` keys on must (a) be written literally in the
    # production source and (b) be exercised by a row below. A truth table is a
    # list of strings somebody typed; without this it can go on grading a state
    # production stopped producing, which is exactly what happened to
    # `planner failed: KeyError: 'choices'` when the response guard moved
    # (PR #15, R18). Closes the class, not the instance.
    if inp.get("prefixes_must_be_reachable"):
        src = "".join(f.read_text(encoding="utf-8")
                      for f in sorted(Path(__file__).parent.glob("*.py"))
                      if f.name != "eval_adapter.py")
        pinned = [r or "" for _, r, _ in inp["checks"]]
        for pref in AB.MODEL_FAULT_REASONS + (AB.OUR_OWN_REFUSAL,):
            if pref not in src:
                wrong.append({"prefix_not_written_in_production": pref,
                              "note": "is_measurement keys on a string no code path emits"})
            if not any(r.startswith(pref) for r in pinned):
                wrong.append({"prefix_never_exercised_by_the_truth_table": pref})

    for status, reason, want in inp["checks"]:
        got = AB.is_measurement(status, reason)
        if got != want:
            wrong.append({"status": status, "reason": reason,
                          "want_measurement": want, "got": got})

    base = _base_url()
    prev_planner, prev_guard, prev_assemble = S.live_planner, S.url_ok, A.assemble_result
    # Fixtures are served on loopback and the production guard refuses loopback;
    # this grades the driver, not the guard (url-guard-literal-ips grades that).
    S.url_ok = lambda u: True

    def spec_for(cfg):
        return {"id": "probe", "task": cfg["task"], "fixture": cfg["fixture"], "url": None,
                "answer": "irrelevant", "ground_truth": "n/a"}

    try:
        # --- a billed completion that is not a plan: scored, and not free -----
        cfg = inp["e2e"]
        billed = cfg["billed_usage"]

        def prose_planner(model=None):
            async def plan(*a, **k):
                raise PlanError(cfg["plan_error"], usage=dict(billed))
            return plan

        S.live_planner = prose_planner
        try:
            row = AB.run_one(base, cfg["model"], spec_for(cfg), 60, [])
        except SystemExit as e:
            row = None
            wrong.append({"aborted_the_sweep_on_a_planning_failure": str(e)[:300]})
        if row is not None:
            if row["correct"] is not False:
                wrong.append({"scored_a_non-plan_run_as_correct": row})
            if "reason" not in row:
                wrong.append("the row carries no `reason`, so a reader cannot tell a model "
                             "that flailed from one that was never asked")
            if row.get("model") != cfg["model"]:
                wrong.append({"row_model": row.get("model"), "submitted": cfg["model"]})
            spent = row.get("budgets") or {}
            got_cost = {"llm_tokens": spent.get("llm_tokens"), "llm_usd": spent.get("llm_usd")}
            if got_cost != billed:
                wrong.append({"billed_but_unreported": billed, "row_recorded": got_cost,
                              "note": "the provider charged for this completion; publishing the "
                                      "cell at $0.00 under-reports exactly the failing runs the "
                                      "ablation exists to find"})

        # --- a provider fault during planning: aborts, never a 0/5 cell -------
        f = inp["e2e_fatal"]

        def http_planner(model=None):
            async def plan(*a, **k):
                raise urllib.error.HTTPError(
                    "https://openrouter.ai/api/v1/chat/completions", f["http_status"],
                    f["http_reason"], {}, None)
            return plan

        S.live_planner = http_planner
        try:
            bad = AB.run_one(base, f["model"], spec_for(f), 60, [])
            wrong.append({"published_a_provider_fault_as_a_model_result": bad,
                          "note": f"HTTP {f['http_status']} during planning was scored as an "
                                  "incorrect cell instead of aborting the sweep"})
        except SystemExit:
            pass  # loud, which is the contract

        # --- a start URL that never loads: not a measurement of anything ------
        # Pre-plan navigation runs before the planner exists, so this cell would
        # be a model scoring 0/5 at $0.00 for a site being down (PR #15, R14).
        u = inp["e2e_unreachable"]
        S.live_planner = lambda model=None: stub_planner(
            [[{"action": "extract", "target": {"role": "heading", "index": 0}}]])
        try:
            bad = AB.run_one(base, u["model"],
                             {"id": "unreachable", "task": u["task"], "fixture": None,
                              "url": u["url"], "answer": "irrelevant", "ground_truth": "n/a"},
                             60, [])
            wrong.append({"published_a_dead_site_as_a_model_result": bad,
                          "note": "pre-plan navigation failed before any planner call; this cell "
                                  "says nothing about the model"})
        except SystemExit:
            pass  # loud, which is the contract

        # --- a gateway attributing the run to a different model ---------------
        # Patched from the EVAL side by wrapping the result assembler, so no
        # eval-only branch lives in the gateway's execution path (PR #15, R13).
        S.live_planner = lambda model=None: stub_planner(
            [[{"action": "extract", "target": {"role": "heading", "index": 0}}]])
        echoes = inp["model_echo"]["echoes"]

        def lying_assemble(*a, **kw):
            out = prev_assemble(*a, **kw)
            out["model"] = echoes
            return out

        A.assemble_result = lying_assemble
        try:
            AB.run_one(base, inp["model_echo"]["submits"], spec_for(cfg), 60, [])
            wrong.append("run_one accepted a run the gateway attributed to a different model")
        except SystemExit:
            pass  # loud, which is the contract
    finally:
        S.live_planner, S.url_ok, A.assemble_result = prev_planner, prev_guard, prev_assemble
    return {"passed": not wrong, "wrong": wrong}


def _run_ablation_preflight_case(case: dict) -> dict:
    """The driver must refuse to spend against a build that drops `model`.

    The one M9 code path that would otherwise have no case behind it, and the one
    guarding twenty paid runs. Both branches are driven against the real app on
    loopback: as shipped it refuses the bogus model and `preflight` returns; with
    the allowlist patched to accept anything — a stand-in for the pre-M9 build,
    which drops the unknown field and answers 200 — `preflight` must raise.

    Free in both directions. The refusal never constructs a planner, and the probe
    task trips `agent.screen` before `run_task` plans, so even the accepting
    branch spends nothing; that is asserted here rather than assumed, since it is
    the reason this check is safe to run against a deployment that has a key."""
    from evals.ablation import preflight

    from . import server as S
    from .agent import screen

    base, wrong = _base_url(), []
    probe = case["input"]["probe_task"]
    # The probe's safety property, MEASURED rather than proxied. `screen(probe)`
    # being truthy is not the claim; the claim is that a build which accepts the
    # model field runs the probe, reaches the scope screen, and stops there
    # having called no planner and spent nothing. On this machine there is no
    # key, so `live_planner` raises and the run ends `failure:env` long before
    # the screen — which is why the proxy passed while the property was untested
    # (PR #15, R5). Install a planner factory that SUCCEEDS and records, so
    # reaching the planner at all is observable.
    if not screen(probe):
        wrong.append("the preflight probe task is NOT refused by the scope screen, "
                     "so on a build that accepts the model field it would really plan")
    called, prev_planner = [], S.live_planner

    def counting_planner(model=None):
        async def plan(*a, **k):
            called.append(model)
            return [], {"llm_tokens": 0, "llm_usd": 0.0}
        return plan

    S.live_planner = counting_planner
    try:
        req = urllib.request.Request(
            f"{base}/tasks", data=json.dumps({"task": probe}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            rid = json.load(r)["run_id"]
        for _ in range(200):
            rec = _get_json(f"/tasks/{rid}")
            if rec.get("status") != "running":
                break
            time.sleep(0.05)
        got = {"status": rec.get("status"), "llm_usd": (rec.get("budgets_spent") or {}).get("llm_usd"),
               "planner_calls": len(called)}
        want = {"status": "unsupported", "llm_usd": 0.0, "planner_calls": 0}
        if got != want:
            wrong.append({"probe_run_is_not_free_and_refused": got, "want": want})
    finally:
        S.live_planner = prev_planner
    try:
        preflight(base)
    except SystemExit as e:
        wrong.append({"shipped_build_rejected_by_its_own_preflight": str(e)})
    prev = S.ALLOWED_MODELS
    # Accepts anything — what a build predating the `model` field does by dropping it.
    S.ALLOWED_MODELS = type("AcceptsAnything", (), {"__contains__": lambda self, x: True})()
    try:
        # The simulation has to be real before its result means anything. This case
        # patches a module attribute by NAME, and the name it patches has already
        # changed once (ABLATION_MODELS -> ALLOWED_MODELS, when the allowlist and
        # the ablation set were split). A patch that lands on the wrong name is a
        # no-op, the endpoint keeps refusing, `preflight` keeps raising, and this
        # case reports PASS while testing nothing at all — the exact shape of an
        # eval nobody has ever seen red. So: prove the door is open first.
        req = urllib.request.Request(
            f"{base}/tasks", data=json.dumps({"task": probe, "model": "definitely/not-allowlisted"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                accepted = r.status == 200
        except urllib.error.HTTPError:
            accepted = False
        if not accepted:
            wrong.append("the 'old build' simulation did not take effect — the endpoint still "
                         "refused the bogus model, so this case would have graded nothing")
        preflight(base)
        wrong.append("preflight PASSED a build that accepts a non-allowlisted model — "
                     "the ablation would run every model and measure one")
    except SystemExit:
        pass  # loud, which is the contract
    finally:
        S.ALLOWED_MODELS = prev
    return {"passed": not wrong, "wrong": wrong}


# --- the ablation table's honesty guard ------------------------------------
# `docs/analysis.md` must never carry a cost/latency number that no committed
# report produced (CLAUDE.md rule 4, and the M9 plan's own validation line:
# "table from committed report runs, not estimates"). The section is delivered
# in two stages — mechanism now, numbers after the deployment redeploys with a
# model parameter — and a table that sits empty for a while is exactly where an
# illustrative row gets pasted in "just to show the shape" and never removed.
# So the rule is graded, not written: while the section declares itself pending
# it must contain zero data rows, and the moment it names a report every cell
# must be re-derivable from that report by the driver's own formatter.

ABLATION_MARKER = "<!-- ablation-table -->"
PENDING_MARKER = "PENDING — no ablation report exists yet"
ABLATION_REPORT_REF = re.compile(r"evals/report/([0-9A-Za-z._-]+-ablation\.json)")
# The shape of a published result, for lines that name no model id at all:
# a dollar figure, an n-of-five score, or a latency percentile.
RESULT_FIGURE = re.compile(r"\$\s?\d|\b\d+\s*/\s*5\b|\bp(?:50|95)\b", re.I)


# `## 9.` -> "9", so `## 9a.` and `## 9.1` read as continuations of it. Cutting
# the section at the *next* `## ` let a fabricated table live under `## 9a.
# Preliminary ablation numbers`, directly under the graded one for any reader and
# invisible to every check (PR #15, R3).
_HEADING_NUM = re.compile(r"^## +(\d+)")


def _doc_section(text: str, heading: str) -> str | None:
    """The block from `heading` through its continuation sub-headings, or None."""
    i = text.find(heading)
    if i < 0:
        return None
    num = (_HEADING_NUM.match(heading) or _HEADING_NUM.match(text[i:i + 40]))
    num = num.group(1) if num else None
    lines = text[i:].splitlines(keepends=True)
    out = [lines[0]]
    for line in lines[1:]:
        if line.startswith("## "):
            m = _HEADING_NUM.match(line)
            # A continuation carries the same leading number (9a, 9.1, 9b).
            if not (num and m and m.group(1) == num):
                break
        out.append(line)
    return "".join(out)


def _table_after_marker(section: str) -> tuple[list, list, list]:
    """(header cells, data rows, the table's own raw lines) after ABLATION_MARKER."""
    if ABLATION_MARKER not in section:
        raise KeyError(f"no {ABLATION_MARKER} in the section")
    rows, raw, started = [], [], False
    for line in section.split(ABLATION_MARKER, 1)[1].splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if started:
                break  # the table ended
            continue
        started = True
        raw.append(s)
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue  # header underline
        rows.append(cells)
    if not rows:
        raise KeyError("no table after the marker")
    return rows[0], rows[1:], raw


def grade_ablation_section(section: str, resolve, document: str) -> list:
    """Problems with one ablation section. Empty list = honest.

    `resolve(name)` returns the named report as a dict, or None if there is no
    such file — injected so the report-mode branch can be exercised without
    waiting for a real paid run to exist. `document` is the whole file the section
    came from: the ablation table's header is distinctive enough to be swept for
    document-wide, and a second copy of it is a lie wherever it sits.

    `document` is REQUIRED, and that is the fix for a defect rather than a style
    choice. It used to default to `None` and fall back to `section`, so the one
    call that graded the real `docs/analysis.md` silently narrowed the sweep to
    §9 while every synthetic variant passed it explicitly — the document-wide
    check graded only inputs the case constructed and never the file it protects
    (PR #15, R12). A forgotten argument is now a TypeError instead of a quiet
    downgrade. For a synthetic section, pass the section as its own document."""
    from evals.ablation import HEADER, markdown_rows

    from .planner import ALLOWED_MODELS

    problems = []
    try:
        header, rows, own_lines = _table_after_marker(section)
    except KeyError as e:
        return [f"ablation table unreadable: {e}"]
    if header != HEADER:
        problems.append({"header": header, "want": HEADER})
    # The marked table is the only one graded, so numbers parked in ANY other table
    # in this section would be invisible to everything below — and "a second table
    # showing the expected shape" is the most natural way to smuggle them in. Two
    # nets: no second copy of the ablation table, and no table row anywhere else in
    # the section that names a model (cold review, M9). Prose may name the models —
    # the section has to be able to say which four they are — but a table row that
    # does is a results row wherever it sits.
    header_line = "| " + " | ".join(HEADER) + " |"
    # Document-wide, not section-wide: this header is unique enough to sweep the
    # whole file for, and it removes the section boundary from the equation for
    # the one shape that matters most — a full copy of the graded table.
    if (n := document.count(header_line)) != 1:
        problems.append(f"the document holds {n} ablation tables; exactly one, under "
                        f"{ABLATION_MARKER}, is the graded one")
    # Two nets, and the first one is STRUCTURAL because the content one has now
    # been walked around three times: round 1 enumerated model ids, round 2
    # enumerated markdown syntaxes, round 3 enumerated number spellings ("4 of 5",
    # unsigned costs, "80% correct at 0.04 cents"). A rule about structure cannot
    # be respelled.
    #
    # 1. This section contains exactly ONE table: the graded one. Any other table
    #    row is a results table however its cells are written (PR #15, R17). This
    #    is why §9's "where the pieces live" table became a bullet list — the
    #    section has no legitimate second table, and a rule with no exceptions is
    #    a rule nobody has to reason about. It holds in report mode too, so the
    #    real table can be published at stage two without touching the guard.
    # 2. No result-shaped figure on any other line, in any syntax — prose,
    #    bullets, blockquotes, code. This catches the shapes that are not tables.
    stray_rows = [ln for ln in section.splitlines()
                  if (s := ln.strip()).startswith("|") and s not in own_lines]
    if stray_rows:
        problems.append({"a_second_table_in_the_section": stray_rows})
    stray = [ln for ln in section.splitlines()
             if (s := ln.strip()) and s not in own_lines and not s.startswith("|")
             and RESULT_FIGURE.search(s)]
    if stray:
        problems.append({"result_shaped_figures_outside_the_graded_table": stray})
    ref = ABLATION_REPORT_REF.search(section)
    if not ref:
        if PENDING_MARKER not in section:
            problems.append("names no ablation report and does not declare itself pending")
        if rows:
            problems.append({"numeric_rows_with_no_report_behind_them": rows})
        return problems
    report = resolve(ref.group(1))
    if report is None:
        return problems + [f"names a report that does not exist: {ref.group(1)}"]
    # Naming a report and still showing the pending banner tells the reader the
    # opposite of what the rows say (PR #15, R7).
    if PENDING_MARKER in section:
        problems.append(f"names {ref.group(1)} and still declares itself "
                        f"{PENDING_MARKER!r}")
    # Sorted, not positional: requiring the doc's row ORDER to match the report's
    # would turn "present the table sorted by cost" into a red case whose cheapest
    # fix is hand-editing the committed report — a perverse incentive pointed at
    # the one artifact that must stay untouched (cold review, M9). Every row must
    # still be exactly a row the report supports, and every model must appear once.
    want = markdown_rows(report)
    if sorted(rows) != sorted(want):
        problems.append({"doc_rows": rows, "rows_the_report_supports": want})
    return problems


def _grade_document(doc: str, heading: str, resolve) -> list:
    """Grade a whole analysis document: locate the section, grade it in scope.

    One function so the committed file and every whole-document variant go
    through the SAME path. They used to be two call sites, and only the variant
    one passed the document scope — so the document-wide sweep graded synthetic
    inputs and never the real file, and no variant could reveal it because a
    clean document narrows to the same answer either way (PR #15, R12)."""
    section = _doc_section(doc, heading)
    if section is None:
        return [f"no section {heading!r}"]
    return grade_ablation_section(section, resolve, doc)


def _run_ablation_table_case(case: dict) -> dict:
    inp = case["input"]
    root = Path(__file__).parents[2]
    section = _doc_section((root / inp["doc"]).read_text(encoding="utf-8"), inp["heading"])
    if section is None:
        return {"passed": False, "error": f"{inp['doc']} has no section {inp['heading']!r}"}
    reports = root / "evals" / "report"

    def resolve(name):
        p = reports / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    doc = (root / inp["doc"]).read_text(encoding="utf-8")
    wrong = {}
    # `document=doc` is not optional here. Without it `scope` falls back to the
    # section and the document-wide duplicate-table sweep — the headline of the
    # round-1 R3 repair — graded only the synthetic variants and never the file it
    # is published as protecting. A guard that passes by grading nothing is the
    # failure mode this repo ranks worst (PR #15, R12).
    if (live := _grade_document(doc, inp["heading"], resolve)):
        wrong["committed_doc"] = live
    # Appended variants edit the DOCUMENT, not the section: they are the shapes
    # that escape by living outside whatever boundary the section has. The
    # section is re-derived from the edited document, so a boundary that lets
    # them through shows up here (PR #15, R3).
    for v in inp.get("append_variants", []):
        # `table_copy` pastes the graded table verbatim somewhere else in the REAL
        # document, which is the shape only a document-wide sweep of the real file
        # can catch (PR #15, R12).
        if v.get("table_copy"):
            _, _, own = _table_after_marker(section)
            edited = doc.replace(v["insert_before"], "\n".join(own) + "\n\n" + v["insert_before"], 1)
        else:
            edited = doc + v["text"]
        # Same entry point as the committed-document check above, deliberately:
        # that is what makes this variant able to pin the scope that check uses.
        if not _grade_document(edited, inp["heading"], resolve):
            wrong.setdefault("accepted_an_appended_table", []).append(v["note"])
    # Each variant is an edit a future session might plausibly make. A variant
    # the grader ACCEPTS is the guard failing in the flattering direction.
    for v in inp["variants"]:
        old, new = v["replace"]
        if old not in section:
            return {"passed": False, "error": f"variant anchor not in the section: {old!r}"}
        if not _grade_document(doc.replace(old, new), inp["heading"], resolve):
            wrong.setdefault("accepted_a_tampered_section", []).append(v["note"])
    # Report mode has no committed report to grade against yet, and dead-on-
    # arrival is how a two-stage delivery loses its guard between the stages.
    # Round-trip it against a synthetic one instead: the driver's own formatter
    # must be accepted, one edited cell must not, and a named-but-absent report
    # must not.
    from evals.ablation import markdown_table

    _, _, own_graded = _table_after_marker(section)
    rep, name = inp["synthetic"]["report"], "20260101-000000-ablation.json"
    syn = f"Measured in `evals/report/{name}`.\n\n{ABLATION_MARKER}\n{markdown_table(rep)}\n"
    res = lambda n: rep if n == name else None  # noqa: E731
    if (round_trip := grade_ablation_section(syn, res, syn)):
        wrong["rejected_the_drivers_own_table"] = round_trip
    old, new = inp["synthetic"]["tamper"]
    if old not in syn:
        return {"passed": False, "error": f"tamper anchor not in the synthetic table: {old!r}"}
    if not grade_ablation_section(syn.replace(old, new), res, syn.replace(old, new)):
        wrong["accepted_a_number_the_report_does_not_support"] = [old, new]
    if not grade_ablation_section(syn, lambda n: None, syn):
        wrong["accepted_a_report_that_does_not_exist"] = True
    # A section that names a report and still shows the pending banner tells the
    # reader the opposite of what its own rows say (PR #15, R7).
    # Stage-two writability. A guard that has to be WEAKENED to publish correct
    # content is a defect now, not later — so this drives the real §9 through the
    # exact transition the human will make after the ablation runs: drop the
    # pending banner, name the committed report, paste the driver's own table
    # under the marker. It must come back clean without touching the grader
    # (reviewer's question under PR #15 R11).
    if inp.get("stage_two_writable"):
        from evals.ablation import markdown_table

        stage2 = (doc.replace(PENDING_MARKER, f"Measured in `evals/report/{name}`.", 1)
                     .replace(f"{ABLATION_MARKER}\n" + "\n".join(own_graded),
                              f"{ABLATION_MARKER}\n{markdown_table(rep)}", 1))
        if ABLATION_MARKER + "\n" + markdown_table(rep) not in stage2:
            wrong["stage_two_rewrite_did_not_apply"] = True
        elif (blocked := _grade_document(stage2, inp["heading"], res)):
            wrong["would_have_to_weaken_the_guard_to_publish_the_real_table"] = blocked
    if inp.get("report_mode_must_reject_pending"):
        pend = f"{PENDING_MARKER}\n\n{syn}"
        if not grade_ablation_section(pend, res, pend):
            wrong["accepted_a_report_that_still_declares_itself_pending"] = True
    return {"passed": not wrong, "wrong": wrong}


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
    "ablation-preflight": _run_ablation_preflight_case,
    "ablation-run-one": _run_ablation_run_one_case,
    "ablation-table": _run_ablation_table_case,
    "classify": _run_classify_case,
    "declared-keys": _run_declared_keys_case,
    "gateway-error": _run_gateway_error_case,
    "gateway-model": _run_gateway_model_case,
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
