"""The agent loop: screen -> plan -> execute step-by-step -> assemble result.

Every step is postcondition-verified against the page (never self-reported).
Failures carry exactly one top-level class from docs/evals/failure-taxonomy.md,
assigned by `classify` — rules over the action and the error, never an LLM.

One deterministic plan lint runs between the plan and the first action
(`plan_gap`): an aggregate-shaped task whose plan cannot express the comparison
is replanned once with a note naming the gap, and stopped rather than executed
if the gap survives (specs/decisions/ADR-016-m31-plan-lint.md). It is a second
consumer of the replan budget, and it is not a recovery ladder — nothing failed.

Two recovery ladders, both chosen from the observed failure distribution
(docs/evals/scope-checkpoint.md) rather than from imagination:

  locate -> re-observe -> relocate at a different tier -> act -> verify
  act    -> re-observe -> replan the remaining steps -> continue

Every other class stays a loud classified stop. Output: specs/001-browser-contract.md.
"""

import contextlib
import json
import re
import time
from pathlib import Path

from .planner import PlanError
from .resolver import TARGET_KEYS, ResolveError, relocation_candidates, resolve
from .verifier import is_aggregate, rank, verify

MAX_FIXES = 2         # relocation rungs per failed step
MAX_REPLANS = 2       # replans per task
SETTLE_TRIES, SETTLE_MS = 10, 200
SETTLE_BUDGET_MS = SETTLE_TRIES * SETTLE_MS  # the same 2s a postcondition gets
# Deliberately its own knob, not SETTLE_BUDGET_MS. The two are equal today and
# have no reason to move together: one bounds how long a page may take to go
# quiet, the other how long a font may take to load. Sharing the name would
# mean tightening the settle loop silently shortened evidence capture.
SCREENSHOT_TIMEOUT_MS = 2_000
PAGE_TEXT_KEEP = 2000  # evidence digest per extraction — enough for anchors, bounded

# ponytail: keyword screen — LLM-based scope screening only if evals demand it.
# One now does, in BOTH directions, and the pattern below is the cheap half.
#
# False negatives are the dangerous half. `\blog ?in\b` needed a word boundary
# after `in`, so "log into" — the commonest English phrasing — sailed through,
# and the deployed agent typed placeholder credentials into a real Google login
# form (T9 probe, run e5e657d3; case l5-refuse-login-contracted). The verb group
# now absorbs inflections and "into", and separators allow a hyphen, so log in /
# log into / logging into / signed into / sign-in all match while `signing`,
# `Loginov` and `sign` alone still do not.
#
# `check-?out` deliberately does NOT match spaced "check out": that is ambiguous
# with "look at" in ordinary English, and a false refusal on a reviewer's task
# costs honesty points (screening-word-boundary).
#
# M10 probe #2 (docs/analysis.md §8a-2) found the same false-negative shape
# again, on the destructive-verb half rather than the login half: "permanently
# deleting all emails" matched neither the inflection (`delete` only, not
# `deleting`) nor the determiner set (`my|the|this` only, not `all`), so the
# agent opened a real browser against mail.google.com instead of refusing at
# $0.00 (run b07d62d3). Widened the same way the login half was: inflections
# (delete/deletes/deleted/deleting) and a wider, still-adjacent determiner set
# (my/the/this/these/those/all/every/any/our) — adjacency is kept so an
# unrelated mention ("what does the delete button do?") does not trip it
# (case l5-refuse-delete-determiners). Deliberately NOT widened to
# remove/erase/wipe/clear: nothing exercised that gap, and guessing at
# synonyms nobody probed is exactly the unwatched widening this repo's
# eval-first rule exists to prevent — D21, docs/support-matrix.md.
#
# Latin terms need \b (case screening-word-boundary: 'signing' contains 'signin');
# CJK terms must stay boundary-free — \b never matches inside a CJK run.
SCOPE_BLOCK = re.compile(
    r"\b(?:log|sign)(?:g?ed|g?ing)?[\s-]?in(?:to)?\b"
    r"|\b(?:password|captcha|payment|purchase|buy|pay|download)\b"
    r"|\bcheck-?out\b"
    r"|\bcredit card\b"
    r"|\bplace (?:an?|the) order\b"
    r"|\bdelet(?:e|es|ed|ing)\s+(?:my|the|this|these|those|all|every|any|our)\b"
    r"|登入|登录|密碼|密码|驗證碼|验证码|付款|購買|购买|刪除|删除|下載|下载",
    re.IGNORECASE,
)


# Can this element hold a typed value at all? Not `Locator.is_editable`, which
# answers "enabled and not readonly" and cheerfully returns True for a <button>
# (Playwright 1.49) — the exact element the OL relocation landed on. A readonly
# or disabled input still passes here on purpose: the element is the right one
# and its STATE is the problem, which is an `act` failure, not a `locate` one.
FILLABLE_JS = """el => el.isContentEditable || el.tagName === 'TEXTAREA'
  || (el.tagName === 'LABEL' && !!el.control)
  || (el.tagName === 'INPUT'
      && !['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image'].includes(el.type))"""


class StepError(Exception):
    """A step failure whose class the executor already knows — an empty
    extraction, a missing identity anchor, a plan the executor cannot honour.
    Everything else is classified from the action and the exception type."""

    def __init__(self, cls: str, note: str):
        self.cls = cls
        super().__init__(note)


def classify(action: str, exc: BaseException) -> str:
    """Failed step -> exactly one taxonomy class (docs/evals/failure-taxonomy.md).

    Deterministic rules, no LLM — this function is what diagnosis accuracy
    grades. The action carries as much of the decision as the exception does:
    the same Playwright timeout is `nav` on a navigate and `act` on a click.
    """
    if isinstance(exc, StepError):
        return exc.cls
    if isinstance(exc, ResolveError):
        return "locate"
    return "nav" if action == "navigate" else "act"


# Per run. The stub planner spends 0 tokens; a live one is capped here.
RUN_BUDGETS = {"actions": 30, "llm_tokens": 100_000}


def budget_stop(spent: dict) -> str | None:
    """Run-level resource check. Non-None means: stop now, loudly, classified.

    Ladder budgets (fixes per step, replans per task) are deliberately not here.
    Running out of actions or tokens is an `env` stop about resources; running
    out of ladder rungs keeps the class of the failure the ladder was trying to
    fix, because that is what the run actually died of.
    """
    over = [f"{k} {spent.get(k, 0)}/{cap}" for k, cap in RUN_BUDGETS.items()
            if spent.get(k, 0) >= cap]
    return "budget exhausted: " + ", ".join(over) if over else None


def screen(task: str) -> str | None:
    m = SCOPE_BLOCK.search(task)
    return f"out of scope (matched '{m.group(0)}'): auth/CAPTCHA/payment/destructive/download tasks are unsupported" if m else None


def plan_gap(task: str, steps: list) -> str | None:
    """Deterministic pre-flight over a PLAN. Non-None means: do not execute it.

    One rule, and it is the one PR #25's verifier guard was built to catch after
    the fact: an aggregate-shaped task ("which X has the most/least Y") whose
    plan contains no enumerating step. `verify()` already fails that run — but
    only once the browser has moved and a wrong answer has been produced to fail.
    Here the same judgement is made from the plan alone, before the first action.

    Structural, not behavioral, and no site knowledge (CLAUDE.md rule 6): it
    reads the task's shape and the plan's actions, nothing about any page. It is
    deliberately not an LLM critic — a second model has no more ground truth
    than the first, and would put two stubbed models in an offline gate that
    currently stubs one (specs/decisions/ADR-016-m31-plan-lint.md).

    `is_aggregate` is shared with the verifier guard on purpose: one regex, two
    callers, so widening the vocabulary widens both or neither. Its ceiling is
    the ceiling of a regex over English — same as SCOPE_BLOCK's.
    """
    if not is_aggregate(task):
        return None
    reads = [s.get("action") for s in steps or []
             if str(s.get("action") or "").startswith("extract")]
    if reads == ["extract_all"]:
        return None
    # Every shape other than "exactly one enumeration and nothing else" leaves
    # the comparison with no single set of values to rank over, and all of them
    # are quiet rather than loud. Zero: a single `extract` guesses the winner.
    # Two enumerations: a list of lists. One enumeration PLUS a plain `extract`:
    # the answer is a composite, `rank` never runs on it (it reduces an
    # enumeration only when the enumeration is the whole answer), and the
    # relaxed aggregate guard passes it because the trace does carry an
    # `extract_all` — an unranked candidate list reported as `success` for a
    # "which one" question, which is the defect this lint exists to stop.
    # Found by the M31 spec-drift audit against this function's own first
    # version, which asked only whether SOME step enumerated.
    return ("the task asks which item of a set ranks highest or lowest, so the plan must "
            f"read the page exactly once, with `extract_all`; this one reads it as {reads}. "
            "A single `extract` guesses the winner; a second read makes the answer a "
            "composite with nothing to rank. Enumerate the candidates once — the comparison "
            "is done in code, so extract the values to compare, not the answer")


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
        raise StepError("task", f"unknown expected_state key {key!r}")

    for _ in range(SETTLE_TRIES):
        try:
            if all([await holds(k, v) for k, v in expected.items()]):
                return True
        except StepError:
            raise
        except Exception:
            pass
        await page.wait_for_timeout(SETTLE_MS)
    return False


async def navigate(page, url: str) -> None:
    """Go to `url` and leave the page in a state that can be READ, not merely
    one where `goto` returned.

    Playwright's default `wait_until="load"` waits for every image, stylesheet
    and subframe — none of which any locator tier reads — so a single hanging
    subresource makes a fully rendered page unreachable. openlibrary.org's
    edition pages did exactly that: content complete in 4.4s, `load` still
    pending at 25s, and the agent blaming the site with `failure:nav` for a page
    it could see (cases nav-load-event-never-fires and its `navigate`-step twin
    nav-action-load-event-never-fires).

    `domcontentloaded` alone would be the opposite mistake. The pre-plan path
    snapshots the page for the planner on the very next line, and a snapshot
    taken mid-hydration hands the planner roles that do not exist yet — which
    surfaces later as a `locate` failure on a page that was fine: an
    intermittent bug that also misattributes itself. So the wait for `load`
    stays; it just stops being unbounded. A healthy page has already fired it
    by the time `goto` returns and pays nothing, and a page that never fires it
    costs 2s — the same budget a postcondition gets — and then proceeds to be
    read, which was always possible.

    `networkidle` was the other candidate and is stronger for hydration, but it
    waits 500ms past the last request on EVERY navigation, healthy or not:
    measured, that was +34s on the fast suite, breaching the 60s ADR-002
    budget to buy a guarantee no case asks for. Bounded `load` keeps the
    behaviour every existing case was written against and fixes only the case
    that was broken.

    Both call sites route through here (the pre-plan hop and the `navigate`
    action), because fixing one would leave the other on the old behaviour and
    the eval for it green.

    Worst case is 22s, not the 20s the goto argument suggests: the document has
    its own 20s, then the settle adds up to 2s on top.
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("load", timeout=SETTLE_BUDGET_MS)
    except PlaywrightTimeoutError:
        pass  # the page never went quiet; read it anyway, that is the point
    # Anything else — a crash or a close inside that window — propagates and is
    # classified. Swallowing it here would discard the real cause and let it
    # resurface as a `locate` failure on the next line, which is the
    # misattribution family this function exists to close.


def evidence_window(body: str, value: str, anchor: str | None = None) -> str:
    """Bounded page-text evidence that still contains what it will be judged on:
    the extracted value, and the identity anchor if the page carries one.

    A flat head-truncation would fail the verifier's grounding check on any page
    longer than PAGE_TEXT_KEEP — a false `failure:semantic` on a correct run. The
    anchor is the same argument one field over, and it went unnoticed until a
    live product page put a wall of description between its title and its
    specification table (case evidence-window-keeps-the-anchor).

    Selecting the window is evidence handling, not grading: whatever is absent
    from the page is absent from the window too, and the check fails, which is
    the true verdict.
    """
    def around(i: int) -> str:
        lo = max(0, i - PAGE_TEXT_KEEP // 2)
        return body[lo:lo + PAGE_TEXT_KEEP]

    if len(body) <= PAGE_TEXT_KEEP:
        return body
    i = body.find(value)
    win = around(i) if i >= 0 else body[:PAGE_TEXT_KEEP]
    j = body.find(anchor) if anchor else -1
    if j >= 0 and anchor not in win:
        win += "\n…\n" + around(j)
    return win


def assemble_result(trace, answer, budgets, failure=None, reason=None, final_url=None,
                    page_digest=None, extractions=None, verdict=None, model=None):
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
        # Which planner model produced this run. `None` from callers that do not
        # plan with a named model (the fast suite stubs the planner). It exists so
        # a run record is self-attributing: the M9 ablation submits a model and
        # writes the answer into a committed report, and without an echo every
        # row's attribution is the driver's own assertion about a deployment that
        # can be redeployed mid-sweep (PR #15, R4).
        "model": model,
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


async def run_task(task: str, url: str | None, planner, run_dir: str | Path, headless: bool = True,
                   url_guard=None, on_step=None, model=None, browser=None):
    """`browser`: an already-running Chromium to borrow instead of launching one.
    Callers that leave it None — the gateway and the CLI, i.e. production — get a
    private browser per run, because two callers' tasks must not share a process.
    The eval harness passes one browser for the whole suite: per-run driver start
    + launch + close measured 11.3s of the `fast` suite's 67.0s (ADR-013).
    `headless` is the borrowed browser's business, not ours.
    Isolation between runs does not depend on this: every run gets its own
    BrowserContext either way, so cookies and storage never cross."""
    t0 = time.monotonic()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    budgets = {"actions": 0, "llm_tokens": 0, "llm_usd": 0.0, "replans": 0, "ms": 0}
    trace: list[dict] = []
    # Holds at most one record awaiting the index of the attempt that replaces
    # it; resolved when that attempt is created, so a run that dies before it
    # never ships a supersede pointing into nothing.
    pending_supersede: list[dict] = []
    # Raw evidence for the OutcomeVerifier: what was read, and what the page
    # said at the moment it was read. The verifier never sees our conclusion.
    extractions: list[dict] = []

    # Hand each finished step to a live watcher (the gateway's SSE endpoint).
    # Every attempt is emitted, including the ones a ladder supersedes: the
    # stream is the trace, not a highlight reel (stream-shows-every-step).
    emit = on_step or (lambda _rec: None)

    def done(answer=None, failure=None, reason=None, final_url=None, digest=None, verdict=None):
        budgets["ms"] = int((time.monotonic() - t0) * 1000)
        result = assemble_result(trace, answer, budgets, failure, reason, final_url,
                                 digest, extractions, verdict, model)
        (run_dir / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in trace) + "\n")
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    if reason := screen(task):
        return done(failure="unsupported", reason=reason)

    from playwright.async_api import async_playwright

    from .observe import observe

    answers: list = []
    async with contextlib.AsyncExitStack() as stack:
        if browser is None:
            pw = await stack.enter_async_context(async_playwright())
            browser = await pw.chromium.launch(headless=headless, args=["--no-sandbox"])
            stack.push_async_callback(browser.close)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            # Pre-plan navigation + observation: the planner never plans blind
            # (live failures dee8ad5d / 2e70785a — guessed roles, invented
            # postconditions). The evolving prefix itself is below: a step whose
            # postcondition fails is replaced by a plan made from the page now.
            obs = None
            if url:
                if url_guard and not url_guard(url):
                    return done(failure="task", reason=f"blocked URL: {url!r}")
                s0 = time.monotonic()
                rec = {
                    "i": 1, "action": "navigate", "target": None, "value": url, "anchor": None,
                    "resolved": None, "expected_state": None, "postcondition_ok": None,
                    "failure_class": None, "note": "pre-plan observation",
                    "retry_or_recovery": None, "superseded_by": None, "page_changed": None,
                    "screenshot": None, "ms": 0,
                }
                trace.append(rec)
                budgets["actions"] += 1
                try:
                    await navigate(page, url)
                    obs = await observe(page)
                    (run_dir / "observation.json").write_text(json.dumps(obs, indent=2))
                    rec["postcondition_ok"] = True
                except Exception as e:
                    rec["failure_class"] = "nav"
                    rec["note"] = f"{type(e).__name__}: {e}"
                    rec["ms"] = int((time.monotonic() - s0) * 1000)
                    emit(rec)
                    return done(failure="nav", reason=f"pre-plan navigation failed: {e}")
                rec["ms"] = int((time.monotonic() - s0) * 1000)
                emit(rec)

            try:
                steps, usage = await planner(task, url, obs)
                budgets["llm_tokens"] += usage["llm_tokens"]
                budgets["llm_usd"] += usage["llm_usd"]
            except PlanError as e:
                # The call worked and the MODEL did not produce a plan. Separated
                # from every other exception here, where the type is known,
                # because downstream (the M9 ablation) has to tell a model that
                # cannot plan from a provider that is down — and a consumer
                # pattern-matching one flat message string got it backwards for a
                # round (PR #15, R9). Its billed usage is charged to the model
                # that emitted the prose (R10).
                budgets["llm_tokens"] += e.usage["llm_tokens"]
                budgets["llm_usd"] += e.usage["llm_usd"]
                return done(failure="env", reason=f"planner rejected: {e}")
            except Exception as e:
                return done(failure="env", reason=f"planner failed: {e}")

            # --- Plan lint: between the plan and the first action -------------
            # A plan that cannot answer the question does not get to move the
            # browser. Replan once, with a note naming the gap, charged to the
            # SAME replan budget the act ladder spends from — so the lint cannot
            # buy itself extra attempts — and stopped by the same no-progress
            # rule: an identical or empty plan, or a second plan carrying the
            # same gap, ends the run instead of executing. There is no third
            # pass, and no path where a gapped plan runs anyway.
            # The note also reaches the TRACE, on the first step of the new plan
            # — a replan whose reason exists only in a planner prompt is a plan
            # change with no evidence behind it. It is deliberately NOT labelled
            # `recovery`: nothing failed and no ladder ran, and ADR-003 keeps
            # that flag for a classified failure that switched strategy.
            lint_note = None
            if gap := plan_gap(task, steps):
                # What actually happened, in the planner's own terms: a plan was
                # rejected, nothing ran, the page is as it was. The act ladder's
                # "a previous attempt failed / plan only the steps still needed"
                # is false on every clause here (PR #29 R5).
                gap_note = ("Your previous plan was rejected before anything ran: " + gap
                            + "\nNothing has executed and the page is unchanged; plan the "
                              "whole task from the page above.")
                try:
                    new_steps, usage = await planner(task, url, obs, note=gap_note)
                except PlanError as e:  # same split as the first plan
                    budgets["llm_tokens"] += e.usage["llm_tokens"]
                    budgets["llm_usd"] += e.usage["llm_usd"]
                    return done(failure="env", reason=f"replanner rejected: {e}")
                except Exception as e:
                    return done(failure="env", reason=f"replanner failed: {e}")
                budgets["llm_tokens"] += usage["llm_tokens"]
                budgets["llm_usd"] += usage["llm_usd"]
                if not new_steps or new_steps == steps or plan_gap(task, new_steps):
                    return done(failure="task",
                                reason=f"plan rejected before execution: {gap}; the replan "
                                       "did not close the gap")
                budgets["replans"] += 1
                lint_note = f"replanned before execution — plan lint: {gap}"
                steps = new_steps

            async def execute(step, rec):
                """Perform one step against the page. Raises; the caller classifies."""
                action = step["action"]
                if action == "navigate":
                    if url_guard and not url_guard(step.get("value") or ""):
                        raise StepError("task", f"blocked URL: {step.get('value')!r}")
                    await navigate(page, step["value"])
                    return
                if action not in ("click", "fill", "extract", "extract_all"):
                    raise StepError("task", f"unknown action {action!r}")
                # A key the resolver does not implement used to be dropped, and
                # the step ran against whatever was left of its target — the plan
                # quietly reinterpreted, the run reported on the weaker task it
                # actually did (case resolver-unknown-target-key).
                if unknown := set(step.get("target") or {}) - TARGET_KEYS:
                    raise StepError("task", f"unsupported target key(s) {sorted(unknown)}")
                # `index` and `near` both mean "of these matches, that one", which
                # is the opposite of what `extract_all` asks for. Honouring the
                # selector would enumerate exactly one value, rank it against
                # nothing, and hand the verifier a trace whose `extract_all` step
                # relaxes the aggregate guard for a single-shot read — the wrong
                # answer of run 734d3d1f wearing this milestone's badge. Closed
                # the same way an unknown target key is: loudly, as a plan the
                # executor will not reinterpret (case extract-all-refuses-a-selector).
                if action == "extract_all" and any(
                        (step.get("target") or {}).get(k) is not None for k in ("index", "near")):
                    raise StepError("task", "extract_all enumerates every match; `index`/`near` "
                                            "select one, so the plan says two different things")
                # `extract_all` wants every match, so ambiguity is the answer
                # rather than a locate failure — the only difference in how a
                # target is resolved.
                loc, tier = await resolve(page, step.get("target") or {},
                                          many=action == "extract_all")
                rec["resolved"] = {"tier": tier, "description": str(step.get("target"))}
                if action == "click":
                    await loc.click(timeout=10_000)
                elif action == "fill":
                    # An element that cannot hold a value is the WRONG element,
                    # so this is a locate failure however Playwright phrases it.
                    # Called it `act` and the act ladder (replan) chased a problem
                    # the locate ladder (different tier) owns — which is how a
                    # relocation onto a non-fillable match laundered its own
                    # failure class on a live site (relocate-fill-non-editable,
                    # live-ol-search-a11y-invisible).
                    if not await loc.evaluate(FILLABLE_JS):
                        raise StepError("locate", f"resolved element is not fillable: {step.get('target')}")
                    await loc.fill(step.get("value") or "", timeout=10_000)
                    # A fill verifies itself by readback, so it needs no authored
                    # postcondition to count as checked.
                    back = await loc.input_value()
                    if back != (step.get("value") or ""):
                        raise StepError("act", f"field readback {back!r} != filled value")
                    rec["postcondition_ok"] = True
                else:
                    # `extract` reads one element; `extract_all` reads every
                    # match, which is the comparison primitive the plan
                    # vocabulary lacked (probe #3, live-books-cheapest-travel).
                    # The ranking over those values happens in code at answer
                    # assembly, never in the model.
                    vals = ([v.strip() for v in await loc.all_inner_texts()]
                            if action == "extract_all" else [(await loc.inner_text()).strip()])
                    vals = [v for v in vals if v]
                    if not vals:
                        raise StepError("extract", "extraction returned empty text")
                    body = await page.inner_text("body")
                    anchor = step.get("anchor")
                    # body_len is the real page the value was read from -- verify()'s
                    # not_a_dump denominator prefers this over len(page_text), because
                    # page_text is evidence_window()'s output: capped at PAGE_TEXT_KEEP
                    # and doubled when a distant anchor forces a second window onto it
                    # (case verifier-dump-ratio-anchor-flip).
                    # One evidence record per value: `grounded` and `not_a_dump`
                    # judge per extraction, so an enumeration is judged row by
                    # row (verifier-list-rows-not-a-dump) rather than as one
                    # page-sized blob.
                    extractions.extend(
                        {"value": v, "page_text": evidence_window(body, v, anchor),
                         "body_len": len(body)} for v in vals)
                    answers.append(vals if action == "extract_all" else vals[0])
                    # Identity anchor (verifier L1): the entity the task names
                    # must be present where the answer was read.
                    if anchor and anchor not in body:
                        raise StepError("semantic", f"identity anchor {anchor!r} absent from the page the answer was read from")

            async def attempt(step, note=None, recovery=None):
                """One execution of one step: appends its trace record, returns
                (record, failure class or None). Every attempt is recorded —
                including the ones a ladder later supersedes — because the trace
                is what shows an evaluator that the strategy changed."""
                rec = {
                    "i": len(trace) + 1, "action": step["action"], "target": step.get("target"),
                    "value": step.get("value"), "anchor": step.get("anchor"), "resolved": None,
                    "expected_state": step.get("expected_state"), "postcondition_ok": None,
                    "failure_class": None, "note": note, "retry_or_recovery": recovery,
                    "superseded_by": None, "page_changed": None, "screenshot": None, "ms": 0,
                }
                trace.append(rec)
                # A replan is only allowed to skip the step it replaces once the
                # replacement attempt actually exists. Writing the pointer early
                # shipped traces whose run-killing step claimed to be superseded
                # by an index that was never created (case supersede-never-dangles).
                if pending_supersede:
                    pending_supersede.pop()["superseded_by"] = rec["i"]
                budgets["actions"] += 1
                s0 = time.monotonic()
                cls = None
                # Did this action change anything at all? The only evidence that
                # separates a replan legitimately skipping work already done from
                # one laundering an action that did nothing (replan-cannot-launder-noop-action).
                before = (await page.inner_text("body")
                          if not step["action"].startswith("extract") else None)
                try:
                    await execute(step, rec)
                    if url_guard and not url_guard(page.url):
                        # The guard is not just an input filter: a click, a 302 or
                        # a meta-refresh can walk the browser off the allowed host
                        # after the submitted URL passed (url-guard-holds-after-navigation).
                        raise StepError("task", f"navigated to blocked URL: {page.url!r}")
                    if before is not None:
                        rec["page_changed"] = (await page.inner_text("body")) != before
                    checked = await check_state(page, step.get("expected_state"))
                    if checked is not None or rec["postcondition_ok"] is None:
                        rec["postcondition_ok"] = checked
                    if rec["postcondition_ok"] is False:
                        raise StepError("act", f"expected_state not reached: {step.get('expected_state')}")
                except Exception as exc:
                    cls = classify(step["action"], exc)
                    rec["failure_class"] = cls
                    rec["note"] = "; ".join(filter(None, [rec["note"], f"{type(exc).__name__}: {exc}"]))
                shot = f"step_{rec['i']}.png"
                try:
                    # Bounded, because "best-effort" and "unbounded" cannot both
                    # be true. Playwright waits for fonts before it shoots, and
                    # on a page whose `load` never fires that wait runs to its
                    # 30s default — per step, silently, inside a block whose
                    # whole point is that failing here is acceptable. It cost
                    # nav-load-event-never-fires 32s and its twin 64s, in a
                    # suite ADR-002 budgets at 60s total.
                    await page.screenshot(path=str(run_dir / shot),
                                          timeout=SCREENSHOT_TIMEOUT_MS)
                    rec["screenshot"] = shot
                except Exception:
                    pass  # evidence best-effort; the postcondition is the gate
                rec["ms"] = int((time.monotonic() - s0) * 1000)
                emit(rec)
                return rec, cls

            async def look():
                """Fresh observation for a ladder, or None if the page cannot be
                observed. A ladder is a best-effort second chance: if looking at
                the page fails too, the run must still end as the classified
                failure it already is, never as an uncaught exception with no
                class at all (INV-1)."""
                try:
                    return await observe(page)
                except Exception:
                    return None

            si = 0
            # A replan's strategy switch belongs on the FIRST step of the new
            # plan — that is the attempt that differs from what failed. The rest
            # of the plan is ordinary execution and is not labelled recovery.
            # `pending_recovery` is what carries the label, so the plan lint can
            # leave its own note on that step without claiming a ladder ran.
            pending, pending_recovery = lint_note, False
            while si < len(steps):
                if stop := budget_stop(budgets):
                    return done(failure="env", reason=stop)
                step = steps[si]
                rec, cls = await attempt(step, note=pending,
                                         recovery="recovery" if pending_recovery else None)
                pending, pending_recovery = None, False

                # --- Family 1: locate -> relocation (self-maintenance) --------
                # Stale locator -> fresh a11y snapshot -> same intent at a
                # different tier -> act -> verify. Rungs come from the snapshot,
                # never from stored site knowledge (CLAUDE.md rule 6).
                if cls == "locate" and (fresh := await look()) is not None:
                    for cand in relocation_candidates(step.get("target") or {}, fresh)[:MAX_FIXES]:
                        rec["superseded_by"] = len(trace) + 1
                        alt = {**step, "target": cand}
                        rec, cls = await attempt(
                            alt, note=f"relocation after locate failure: retargeting as {cand}",
                            recovery="recovery")
                        if cls is None:
                            step = alt
                            break

                # --- Family 2: act -> postcondition invalidated -> replan -----
                if cls == "act":
                    if budgets["replans"] >= MAX_REPLANS:
                        rec["note"] += f"; replan budget exhausted ({MAX_REPLANS})"
                    elif (fresh := await look()) is not None:
                        try:
                            new_steps, usage = await planner(
                                task, page.url, fresh,
                                note=(f"A previous attempt failed: step {rec['i']} "
                                      f"({step['action']}) failed: {rec['note']}\n"
                                      "Plan only the steps still needed from the page above."))
                        except PlanError as e:  # same split as the first plan
                            budgets["llm_tokens"] += e.usage["llm_tokens"]
                            budgets["llm_usd"] += e.usage["llm_usd"]
                            return done(failure="env", reason=f"replanner rejected: {e}")
                        except Exception as e:
                            return done(failure="env", reason=f"replanner failed: {e}")
                        budgets["llm_tokens"] += usage["llm_tokens"]
                        budgets["llm_usd"] += usage["llm_usd"]
                        # Three ways a replan is not progress. The first two are
                        # no-ops; the third is the dangerous one — a plan that
                        # drops the failed action and reads the page as if it had
                        # worked, when nothing on the page moved. The benign twin
                        # (recovery-replan-postcondition) clicks a control that
                        # really did re-sort the list, so page_changed tells them
                        # apart where nothing about the PLAN can.
                        # Every extraction verb, not the literal string: M31 added
                        # `extract_all` and this test kept naming only `extract`,
                        # so the same laundering in the new verb walked straight
                        # through (PR #29 R1, case
                        # replan-cannot-launder-noop-action-extract-all).
                        drops_action = bool(new_steps) and str(
                            new_steps[0].get("action") or "").startswith("extract")
                        if not new_steps or new_steps == steps[si:]:
                            rec["note"] += "; replan made no progress (identical or empty plan)"
                        elif new_steps[0] == steps[si]:
                            # Family 1 enforces "a rung must be a different tier";
                            # this is family 2's equivalent. Re-issuing the step
                            # that just failed is a retry, and specs/001 keeps
                            # retries out of the recovery metric by construction.
                            rec["note"] += "; replan re-issued the step that just failed"
                        elif drops_action and not rec.get("page_changed"):
                            rec["note"] += ("; replan would skip a failed action that changed "
                                            "nothing on the page")
                        # The lint runs at EVERY point the executor adopts a plan,
                        # not only the first one. `steps[:si] + new_steps` is the
                        # plan of record after this replan, executed prefix
                        # included, so a replan that adds a second enumeration is
                        # refused here exactly as the first plan would have been —
                        # the run then ends as the `act` failure it already was.
                        # Linting only the first plan let a mid-run replan produce
                        # the unranked list of lists ADR-016 names as the defect
                        # (PR #29 R3, case plan-lint-holds-across-a-midrun-replan).
                        elif lint := plan_gap(task, steps[:si] + new_steps):
                            rec["note"] += f"; replan rejected by the plan lint: {lint}"
                        else:
                            budgets["replans"] += 1
                            pending_supersede.append(rec)
                            pending_recovery = True
                            pending = (f"replan #{budgets['replans']} after act failure at step "
                                       f"{rec['i']}: {len(new_steps)} step(s) planned from the "
                                       "page as it actually is")
                            # Evolving prefix: what already executed stays; the
                            # failed step and everything after it is replaced by
                            # a plan made from what the page actually shows now.
                            # ponytail: extractions from the executed prefix are
                            # kept, so a replan that re-extracts the same value
                            # would append it twice and turn a scalar answer into
                            # a list. No case produces it (ADR-003); dedupe by
                            # (value, step intent) if one ever does.
                            steps = steps[:si] + new_steps
                            continue

                if cls:
                    return done(failure=cls,
                                reason=f"step {rec['i']} ({step['action']}): {rec['note']}")
                si += 1

            digest = (await page.inner_text("body"))[:500]
            final_url = page.url
        finally:
            await ctx.close()  # the run's own context; the browser may be shared

    # One extract -> scalar answer; several -> list (contract: answer string|list).
    answer = answers[0] if len(answers) == 1 else (answers or None)
    # An `extract_all` enumeration is reduced HERE, in code: the plan gathered
    # every candidate and `rank` picks the one the task's superlative asks for.
    # Whether to reduce at all is `rank`'s own decision, from the task text: a
    # task that asks for the enumeration keeps its list, a task that asks for one
    # item out of it gets one. Both mistakes have been made here and both are
    # cased — reducing a list-shaped task to one row (PR #29 R2,
    # extract-all-list-task-keeps-every-row) and publishing the raw enumeration
    # as the answer to a single-answer ranking (PR #29 R9,
    # extract-all-cheapest-wording-still-reduces). The `len(answers) == 1` half
    # stays here because it is about the PLAN, not the task: a plan that also
    # extracts something else is composing a list, not ranking one
    # (multi-extract-list). More than one enumeration never reaches here for an
    # aggregate task, because `plan_gap` runs at BOTH points where the executor
    # adopts a plan — the first plan and an act-ladder replan (PR #29 R3). A tie
    # is refused rather than guessed, and a refusal is `semantic`: the page was
    # read correctly and does not decide.
    if len(answers) == 1 and isinstance(answer, list):
        try:
            answer = rank(task, answer)
        except ValueError as e:
            return done(failure="semantic", reason=str(e), final_url=final_url, digest=digest)
    # The run is graded by the verifier, not by having reached this line.
    verdict = verify(trace=trace, extractions=extractions, answer=answer, task=task)
    return done(answer=answer, final_url=final_url, digest=digest, verdict=verdict)
