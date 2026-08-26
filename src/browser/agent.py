"""The agent loop: screen -> plan -> execute step-by-step -> assemble result.

Every step is postcondition-verified against the page (never self-reported).
Failures carry exactly one top-level class from docs/evals/failure-taxonomy.md,
assigned by `classify` — rules over the action and the error, never an LLM.

One deterministic plan lint runs between the plan and the first action
(`plan_gap`), and it refuses two shapes: an aggregate-shaped task whose plan
cannot express the comparison (specs/decisions/ADR-018-m31-plan-lint.md), and
any plan that extracts from the accessibility document root — a container whose
text is the whole page (specs/decisions/ADR-024-document-root-is-not-an-answer.md).
Either way the plan is replanned once with a note naming the gap, and stopped
rather than executed if the gap survives. It is a second consumer of the replan
budget, and it is not a recovery ladder — nothing failed.

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

from .judge import JUDGE_ATTEMPTS, RUN_JUDGE_BUDGET
from .observe import page_text
from .planner import PlanError
from .resolver import (DOC_ROOT_ROLES, TARGET_KEYS, ResolveError,
                        relocation_candidates, resolve)
from .verifier import is_aggregate, rank, verify

# The executor's whole vocabulary (ADR-027 Decision 2 widens it; ADR-028 records
# the semantics). `navigate` is handled before this set is consulted because it
# is the only action that moves the browser without resolving anything.
#
# Shared by both modes on purpose: the loop replaces the planning CADENCE, not
# the machinery, so a verb mode B can execute is a verb the loop can call and
# vice versa — which is what makes `loop-mode-b-cannot-read-the-un-awaited-result`
# an honest A/B rather than a comparison of two vocabularies.
ACTIONS = ("navigate", "click", "fill", "extract", "extract_all", "observe",
           "select_option", "scroll", "press", "wait_for", "go_back", "final_answer")

# Actions that CANNOT run without a resolved element. `scroll` and `press` are
# deliberately absent: both have a page-level form (scroll the window, send a
# key to whatever has focus) that is a real browsing primitive, and demanding a
# target for them would mean a plan has to name an element it does not care
# about.
NEEDS_TARGET = {"click", "fill", "extract", "extract_all", "observe", "select_option"}

# What a `<select>` currently offers, as (value, label) pairs — `null` for an
# element that is not one. Read twice by the select step (before and after
# waiting out a fetch-painted control), hence a constant rather than two
# string literals that can drift apart.
OPTIONS_JS = "el => el.options ? [...el.options].map(o => [o.value, o.label]) : null"

# Actions that leave the page as they found it, so `attempt` does not pay for a
# before/after comparison. `observe` reads, and `final_answer` is the loop's
# terminal call — it acts on nothing at all.
READ_ONLY_ACTIONS = {"observe", "final_answer"}

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
# CJK terms have no boundary to lean on — Python `re` puts no `\b` inside a CJK
# run and there is no whitespace — so they match as bare substrings and fire
# inside a LONGER word that means something else.
#
# M45 measured that, tried to fix it three times, and shipped none of the three.
# The measurement is real: the repo's first live probe in Chinese (ADR-031,
# docs/analysis.md §8a-5) refused three legitimate READ tasks at $0.00 with an
# empty trace — 密碼 inside 密碼學 (cryptography, run 8304ee3b), 購買 inside
# 購買力平價 (purchasing power parity, run be20ba6a, a read task in this repo's
# own target domain), 刪除 inside 刪除的檔案 ("deleted files", run 038bc371).
#
# Each attempted repair was a per-term negative lookahead, and each was falsified
# by an ordinary Chinese sentence that the lookahead un-refused:
#
#   [刪删]除(?!的)          把購物車裡要刪除的商品都刪掉   (cold review)
#                           — 的 marks an attributive reading in a genuine
#                             destructive ask as readily as in a question
#   [購购][買买](?!力平[價价])  我要購買力平價這本書           (PR #56 R2)
#                           — "buy the book Purchasing Power Parity"; 力平價
#                             starts the OBJECT, on a bookstore, which is a
#                             live domain in docs/support-matrix.md
#   密[碼码](?![學学])      幫我重設密碼學生帳號           (PR #56 R2)
#                           — 學生帳號 ("student account") begins with 學
#
# The pattern is the finding: the continuation that makes a term part of a
# different word is indistinguishable, to a regex, from the first character of
# the object a real request is acting on. Every narrowing therefore trades a
# false refusal for a false ALLOW in a security-adjacent screen, and this screen
# fails CLOSED. So the alternation below is byte-for-byte what it was before
# M45, and M45's contribution here is the measurement, the cases that pin every
# falsified attempt, and the residual declared in docs/support-matrix.md D31.
#
# What might actually work is a rule about the REQUEST FRAME rather than about
# the term's neighbours — every false positive above is a question about a page
# (…是什麼？ / …的定義 / …會保留多久？) and every false negative is an imperative
# (幫我… / 請… / 我要…). That is a different mechanism, unprobed in either
# language, and it is filed as tasks/TODO.md M45-D8 rather than guessed at here.
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

# M34 R2-1: an approximate character offset of `el`'s own text within
# `document.body`'s rendered text -- walks up from `el` to <body>, summing
# the text length of every preceding ELEMENT sibling at each level. Not
# exact (bare text-node siblings between elements are not counted, and
# `innerText`'s own whitespace collapsing is not reproduced here), but it
# does not need to be: `_closest_occurrence` (below) only uses it to pick
# WHICH occurrence of a repeated value is real, among candidates that are
# typically hundreds of characters apart, not to index precisely into text.
TEXT_OFFSET_JS = """el => {
  let offset = 0, node = el;
  while (node && node.tagName !== 'BODY') {
    let sib = node.previousElementSibling;
    while (sib) {
      offset += (sib.innerText !== undefined ? sib.innerText : (sib.textContent || '')).length;
      sib = sib.previousElementSibling;
    }
    node = node.parentElement;
  }
  return offset;
}"""


def _closest_occurrence(body: str, value: str, hint: int) -> int:
    """Absolute offset of the occurrence of `value` in `body` nearest `hint`
    (a DOM-derived approximate offset, see TEXT_OFFSET_JS) -- the same value
    can legitimately appear more than once on one page (a decoy blurb and
    the real answer, case verifier-context-anchors-real-occurrence /
    PR #30 R2-1), and `str.find` alone always returns the FIRST, which is
    not necessarily the one the resolver actually matched. -1 if `value`
    is not in `body` at all."""
    best, best_d = -1, None
    i = body.find(value)
    while i >= 0:
        d = abs(i - hint)
        if best_d is None or d < best_d:
            best, best_d = i, d
        i = body.find(value, i + 1)
    return best


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


def changed_nothing(rec: dict) -> bool:
    """Did this attempt leave the page as it found it?

    The only evidence a laundering guard has, and the two guards that read it
    disagreed for one commit (PR #34 R8). `page_changed` is `False` when the
    attempt ran and moved nothing, and `null` when it never got far enough to
    be compared — every act failure raised INSIDE `execute` (a click timeout, a
    fill readback mismatch) leaves it null, because the before/after comparison
    is on the line after `execute` returns. Neither value is evidence that
    anything moved, so both mean the same thing here, and asking it in one
    place is what stops the next guard from picking a different half.
    """
    return not rec.get("page_changed")


def reads_without_acting(steps) -> bool:
    """Does this plan reach an EXTRACTION with nothing that changes the page
    before it?

    The question every replan has to answer before it is allowed to drop a
    failed action: a plan that only READS is reporting the state the failed
    action was supposed to change (`replan-cannot-launder-noop-action`). It
    was once asked as "is the first step an `extract`", which was the same
    question while `extract` was the only step that neither acted nor
    enumerated. Two branches then broke it at once, each finding its own half:

      * M31 added `extract_all`, which launders identically while the literal
        string `extract` does not match it (PR #29 R1,
        `replan-cannot-launder-noop-action-extract-all`);
      * M32 added `observe`, which changes nothing, so `[observe, extract]`
        drops the failed action just as surely (PR #34 R1,
        `observe-cannot-launder-noop-action`).

    Either fix alone reverts the other on merge, and the intersection
    `[observe, extract_all]` passes both pre-merge tests while laundering under
    either (`observe-cannot-launder-extract-all`). So: every extraction verb
    terminates the scan, and `observe` is transparent to it — for the same
    reason its `page_changed` is null. A plan that looks and THEN acts is not
    laundering and is not refused.
    """
    for step in steps:
        action = str(step.get("action") or "")
        if action.startswith("extract"):
            return True
        if action != "observe":
            return False
    return False


# Per run. The stub planner spends 0 tokens; a live one is capped here.
RUN_BUDGETS = {"actions": 30, "llm_tokens": 100_000}

# Loop mode's own (ADR-027 Decision 4, ADR-028). Runaway protection, not a cost
# gate: the mandate says cost is not a constraint, which is a budget statement
# and not permission to stop measuring — so the ceilings are generous, the
# ACCOUNTING is unchanged, and every run still records what it spent.
#
# `llm_usd` is here and not in RUN_BUDGETS on purpose. Mode B plans once with a
# model held under ADR-010's price ceiling, so tokens are a faithful meter for
# it; loop mode calls a frontier model once per step, where the same token count
# can be two orders of magnitude apart in money. A ceiling that cannot trip on
# dollars is not runaway protection for this mode
# (`loop-usd-ceiling-stops-the-run-loudly`).
LOOP_BUDGETS = {"actions": 40, "llm_tokens": 400_000, "llm_usd": 5.00}

# How many times the loop may arrive at the SAME (URL, page-signature) state
# with nothing new extracted before the harness intervenes. The N-th visit
# forces a strategy change; the one after it ends the run with that reason.
LOOP_REVISIT_CAP = 3


def budget_stop(spent: dict, caps: dict | None = None) -> str | None:
    """Run-level resource check. Non-None means: stop now, loudly, classified.

    Ladder budgets (fixes per step, replans per task) are deliberately not here.
    Running out of actions or tokens is an `env` stop about resources; running
    out of ladder rungs keeps the class of the failure the ladder was trying to
    fix, because that is what the run actually died of.

    `caps` is the mode's budget table, defaulting to mode B's. One function, two
    tables — a second copy of this loop for loop mode would be a second place to
    forget a key, and `>=` is the whole subtlety here.
    """
    caps = caps or RUN_BUDGETS
    over = [f"{k} {spent.get(k, 0)}/{cap}" for k, cap in caps.items()
            if spent.get(k, 0) >= cap]
    return "budget exhausted: " + ", ".join(over) if over else None


def page_signature(obs: dict | None) -> str:
    """A cheap fingerprint of one PAGE STATE, for the no-progress harness.

    Roles, names and the head of the page text — the same things the model is
    shown, which is the point: two turns the model cannot tell apart must not
    look like progress to the harness either. Not the URL: the caller pairs this
    with `page.url`, because a SPA changes state without changing URL and a
    query string changes URL without changing state.
    """
    if not obs:
        return ""
    return json.dumps([[e.get("role"), e.get("name")] for e in obs.get("elements", [])],
                      sort_keys=True) + "|" + (obs.get("text_head") or "")[:200]


def screen(task: str) -> str | None:
    m = SCOPE_BLOCK.search(task)
    return f"out of scope (matched '{m.group(0)}'): auth/CAPTCHA/payment/destructive/download tasks are unsupported" if m else None


# `DOC_ROOT_ROLES` (imported from resolver.py, where its other reader lives) is
# the accessibility document root: Chromium's `WebArea`, `RootWebArea` in other
# builds. Stripped and case-folded because the spelling in a plan is the MODEL's,
# not Chromium's.
#
# ARIA's `document` role is NOT in that set, and the first version of it had it.
# It is not the root: it is an author-supplied role on an in-page container
# (`<div class="modal-dialog" role="document">` is Bootstrap boilerplate), and
# unlike the two root spellings it RESOLVES — on the cold review's fixture,
# `get_by_role("document", name="Order confirmation")` returned a 40-character
# confirmation inside a dialog, refused with a reason asserting that node was
# "the ENTIRE page". That is a false statement about the page, generated from
# the plan alone, which is exactly what a plan-time rule may not do.
#
# `observe` walks that snapshot from its root and the root is in neither
# SKIP_ROLES nor NAME_PROHIBITED, so element #1 of every observation the planner
# is shown is `WebArea — <the page title>`: the most answer-shaped string in the
# list, attached to the one node whose text is the whole document. T-M40-2
# measured four of five live tasks planning exactly that.
#
# Refused only for the extraction verbs. M32's drill-down targets a container ON
# PURPOSE — `observe {role: WebArea}` is a plan about what to look at next, not
# an answer offered from a container — and that distinction is the reason this
# is a rule about the ACTION and the ROLE together, not about the role alone.
#
# Scope, deliberately: the document root, not landmarks (`main`, `navigation`,
# `contentinfo`, …) and not `document`. A root's text is the entire page by
# construction, so refusing it has no false-positive case to argue about; any
# other container is a judgement about how much of the page is too much, which
# `verify`'s `not_a_dump` already makes with the page in hand and a calibrated
# ratio (ADR-008). Two guards, each where its evidence is.


def root_target_gap(step) -> str | None:
    """Does this step read from the accessibility document root? Then refuse it.

    ADR-024's rule, in the one place both of its anchors can ask for it
    (ADR-027 Decision 5). ADR-024 anchored it "at every point the executor
    adopts a plan" — an anchor loop mode does not have, and without re-homing a
    loop-mode `WebArea` extract is exactly the T-M40-2 shape with no guard,
    because ADR-024 deliberately moved the root OUT of `verify`'s remit. The
    judgement therefore lives here and is asked twice: by `plan_gap` before mode
    B executes anything, and by `execute` as a call is emitted, which is the
    only "before" a loop has.

    Writing a second copy for the loop was the alternative and it is the shape
    this repo has been burned by four times (ADR-018's two call sites, M32's
    unlinted third adoption point): one rule, one function, two callers.

    Refused only for the extraction verbs, and only for the ROOT — `observe` on
    the same target is M32's drill-down and is untouched, ARIA `document` is not
    the root, and any other container stays with `verify`'s calibrated
    `not_a_dump`. The whole argument is at DOC_ROOT_ROLES above.
    """
    # `isinstance`, because a lint is not the thing that raises: `parse_plan`
    # validates only that the top level is a list, and `parse_tool_call`
    # validates only that arguments are an object, so a string target or a step
    # that is not a dict at all reaches here (PR #46 R1-4).
    if not isinstance(step, dict) or not str(step.get("action") or "").startswith("extract"):
        return None
    target = step.get("target")
    role = str(target.get("role") or "") if isinstance(target, dict) else ""
    if role.strip().lower() not in DOC_ROOT_ROLES:
        return None
    return (f"{step['action']!r} targets {role!r}, the accessibility root of the document — the "
            "node `observe` lists first on every page, whose accessible name is the page title "
            "and whose text is the ENTIRE page. It cannot be the answer to anything, and it "
            "carries no other string to retarget by, so the page title is all a relocation could "
            "ask for next. Name the element that holds the value; if you can see a container but "
            "not its contents, `observe` that container first")


def plan_gap(task: str, steps: list) -> str | None:
    """Deterministic pre-flight over a PLAN. Non-None means: do not execute it.

    Two rules, in the order a plan fails them.

    The first is about the TARGET and holds for every task shape: an extraction
    step aimed at the accessibility document root (DOC_ROOT_ROLES). Refused
    before the aggregate rule, and above its early return, because the shape it
    catches is an ordinary single-answer question — T-M40-2's whole re-probe is
    non-aggregate, and a clause below that return would have been dead code for
    all of it.

    The second is the one PR #25's verifier guard was built to catch after the
    fact: an aggregate-shaped task ("which X has the most/least Y") whose plan
    contains no enumerating step. `verify()` already fails that run — but only
    once the browser has moved and a wrong answer has been produced to fail.
    Here the same judgement is made from the plan alone, before the first action.

    Structural, not behavioral, and no site knowledge (CLAUDE.md rule 6): it
    reads the task's shape, the plan's actions and the roles they name — nothing
    about any page. It is deliberately not an LLM critic — a second model has no
    more ground truth than the first, and would put two stubbed models in an
    offline gate that currently stubs one
    (specs/decisions/ADR-018-m31-plan-lint.md).

    `is_aggregate` is shared with the verifier guard on purpose: one regex, two
    callers, so widening the vocabulary widens both or neither. Its ceiling is
    the ceiling of a regex over English — same as SCOPE_BLOCK's.
    """
    for step in steps or []:
        # `isinstance`, because a lint is not the thing that raises: this clause
        # runs for EVERY task shape, where the aggregate rule below used to
        # return None immediately on a plain task, and `parse_plan` validates
        # only that the top level is a list — a string target, or a step that is
        # not a dict at all, reaches here (PR #46 R1-4). The `reads` comprehension
        # below carries the same guard: the first version of this fix covered
        # only this loop, so the identical plan still raised on an aggregate task
        # (PR #46 R6), which is what a partial guard is worth.
        #
        # What happens instead of raising, precisely, because the first version
        # of this comment overclaimed it: a malformed TARGET is "no gap" here and
        # the executor rejects it loudly (TARGET_KEYS). A malformed STEP is "no
        # gap" here and then dies at `step["action"]` in the step loop with an
        # uncaught TypeError — no status, no failure class. That is pre-existing
        # and unchanged by this PR (`main` reaches the same line the same way),
        # it is the executor's contract rather than the lint's, and it is logged
        # as T-M40-2-6 rather than fixed here.
        # `observe` names a container ON PURPOSE — see DOC_ROOT_ROLES.
        if gap := root_target_gap(step):
            return "the plan reads " + gap
    if not is_aggregate(task):
        return None
    reads = [s for s in steps or []
             if isinstance(s, dict) and str(s.get("action") or "").startswith("extract")]
    actions = [s.get("action") for s in reads]
    if actions == ["extract_all"]:
        # The plan enumerates once — now check what it says it did with the
        # enumeration. `rank: false` means "the answer is the whole set", which
        # contradicts a task `is_aggregate` has already identified as asking
        # for one item OF a set. Code held both halves of that contradiction
        # and compared them nowhere for three rounds, so a plan that declared
        # it did NO comparison satisfied the guard whose job is to notice that
        # nothing compared anything (PR #29 R20, case
        # plan-lint-refuses-a-declared-non-comparison).
        if reads[0].get("rank") is True:
            return None
        return ("the task asks which item of a set ranks highest or lowest, and the plan "
                "enumerates the set but declares `rank: false` — that the answer is the "
                "whole enumeration. Those cannot both be right about this task. Declare "
                "`rank: true` and let code do the comparison, or the answer is a candidate "
                "list offered as the answer to a which-one question")
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
            # `page_text`, not `page.inner_text("body")`: a postcondition that
            # cannot see an iframe or an open shadow root is a postcondition
            # that fails on a page the run handled correctly
            # (`shadow-dom-value-is-reachable-and-grounded`).
            return want in (await page_text(page))
        if key == "role_visible":
            # Same widening, one layer down: a locator never crosses a frame
            # boundary, so the main frame alone is the wrong question to ask.
            for scope in [page, *(getattr(page, "frames", None) or [page])[1:]]:
                loc = (scope.get_by_role(want["role"], name=want["name"])
                       if want.get("name") else scope.get_by_role(want["role"]))
                if await loc.count() >= 1 and await loc.first.is_visible():
                    return True
            return False
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


def _window_lo(body: str, i: int) -> int:
    """Start of the PAGE_TEXT_KEEP-wide window `evidence_window` centres on
    offset `i` -- shared with the extract step (agent.py) so it can compute
    where `i` lands INSIDE that window (case verifier-context-anchors-real-
    occurrence / PR #30 R2-1) without duplicating this arithmetic."""
    return max(0, i - PAGE_TEXT_KEEP // 2) if len(body) > PAGE_TEXT_KEEP else 0


def evidence_window(body: str, value: str, anchor: str | None = None,
                    offset: int | None = None) -> str:
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

    `offset` (M34 R2-1): the REAL position of `value` in `body`, when the
    caller already knows it (`_closest_occurrence`) -- `value` can legitimately
    occur more than once, and centring on `body.find(value)` (the default,
    still used when `offset` is None) always picks the first, whether or not
    that is where the extraction actually came from.
    """
    def around(i: int) -> str:
        return body[_window_lo(body, i):_window_lo(body, i) + PAGE_TEXT_KEEP]

    if len(body) <= PAGE_TEXT_KEEP:
        return body
    i = offset if offset is not None and offset >= 0 else body.find(value)
    win = around(i) if i >= 0 else body[:PAGE_TEXT_KEEP]
    j = body.find(anchor) if anchor else -1
    if j >= 0 and anchor not in win:
        win += "\n…\n" + around(j)
    return win


def assemble_result(trace, answer, budgets, failure=None, reason=None, final_url=None,
                    page_digest=None, extractions=None, verdict=None, model=None,
                    mode="plan"):
    if failure:
        status = "unsupported" if failure == "unsupported" else f"failure:{failure}"
    else:
        status = "success"
    # INV-0: never success with empty output (specs/000, specs/001).
    if status == "success" and (not answer or not trace):
        status, reason = "failure:extract", reason or "empty answer or empty trace"
    # INV-2: the executor's claim never outranks the verifier (specs/000).
    # M28: ...and a rejected answer is not an answer. The demoted run used to
    # carry the rejected extraction as its `answer` -- a whole infobox, ~1.5k
    # chars, on the deployed build (run 4bade630, case
    # extract-container-dump-is-not-the-answer). What was read stays in
    # `evidence.extractions`, in full, where the verifier read it from; the
    # user-facing field says what the verdict says: nothing here answers.
    if status == "success" and verdict and verdict.get("verdict") != "PASS":
        status = "failure:semantic"
        reason = reason or f"verifier {verdict['verdict']}: {verdict.get('reason')}"
        answer = None
    return {
        "status": status,
        # Which CADENCE produced this run. Beside `model` and for the same
        # reason: a run record has to be self-attributing. Without it a loop run
        # and a mode B run of the same task on the same model are byte-identical
        # in shape, and the only way to tell them apart is counting
        # `final_answer` steps in the trace — while M44's whole job is comparing
        # the two modes from committed run records (spec-drift audit finding 9).
        # This is a property of the RUN, not of a step, so ADR-028 §7's "the
        # trace gains no fields" is untouched.
        "mode": mode,
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


async def _apply_judge(judge, task, answer, extractions, verdict, budgets) -> dict:
    """M36's terminal-verdict boundary. Called exactly once, and only when
    `verdict` already carries a layer-1 PASS (agent.py never has ground truth,
    so this IS the runtime path verify()'s L2 never touches) -- the judge is
    the last rung of the escalation ladder, not a replacement for the free
    checks above it (cost-discipline rule 1).

    FAIL CLOSED is the entire point of this function. Three ways in and every
    one of them ends the same way -- the verdict becomes FAIL, never "keep
    the prior PASS and move on":
      1. the per-run budget is already spent (RUN_JUDGE_BUDGET, one call/run);
      2. `judge(...)` raises ANYTHING -- JudgeError (missing key, malformed
         response, provider/network failure) or any other exception;
      3. `judge(...)` returns cleanly and rejects.
    A judge that certifies is the only path that leaves PASS standing, and
    even then the check is recorded (`judge_responsive: true`) so the
    per-stage hit-rate is honest about how many runs needed it.

    ADR-023 narrows WHEN (2) fires, never WHETHER it does: an unreadable
    completion body is not a verdict, so there is nothing to fail closed on
    yet, and the SAME call is made once more (`JUDGE_ATTEMPTS`, judge.py) with
    the same prompt. A second failure ends the run exactly as the first used
    to. Only `JudgeError.retryable` earns that -- a refusal, a wrong-shaped
    response, a missing key and a reasoned FAIL are all answers a second
    identical call would only reproduce. Both attempts are billed, and
    `judge_attempts` records which happened, so the extra call can never be
    invisible in the cost line.
    """
    checks = dict(verdict["checks"])
    if budgets["judge_calls"] >= RUN_JUDGE_BUDGET:
        checks["judge_available"] = False
        # Zero, not absent: `judge_attempts` is present on every path that
        # reached this boundary (specs/001), and a budget refusal made no
        # provider attempt at all (cold review R5).
        checks["judge_attempts"] = 0
        return {**verdict, "verdict": "FAIL", "checks": checks,
                "reason": f"judge budget exhausted ({RUN_JUDGE_BUDGET}/run), failing closed"}
    # One judge BOUNDARY call per run (RUN_JUDGE_BUDGET), which ADR-023 may
    # spend over up to JUDGE_ATTEMPTS provider attempts. Counted here, before
    # the loop, so a retry can never buy a second trip through this function.
    budgets["judge_calls"] += 1
    evidence = " ".join(e.get("page_text", "") for e in extractions or [])
    for attempt in range(1, JUDGE_ATTEMPTS + 1):
        try:
            certify, reason, usage = await judge(task, answer, evidence)
            break
        except Exception as e:
            # A completion that failed to parse still burned the provider's
            # tokens. Billed either way, so the retry cannot hide inside the
            # run's token/USD budget (ADR-023, cost-discipline rule 1).
            spent = getattr(e, "usage", None) or {}
            budgets["judge_tokens"] += spent.get("llm_tokens", 0)
            budgets["judge_usd"] += spent.get("llm_usd", 0.0)
            if attempt < JUDGE_ATTEMPTS and getattr(e, "retryable", False):
                continue
            checks["judge_attempts"] = attempt
            checks["judge_available"] = False
            return {**verdict, "verdict": "FAIL", "checks": checks,
                    "reason": f"judge unavailable, failing closed: {type(e).__name__}: {e}"}
    budgets["judge_tokens"] += usage.get("llm_tokens", 0)
    budgets["judge_usd"] += usage.get("llm_usd", 0.0)
    checks["judge_attempts"] = attempt
    checks["judge_responsive"] = certify
    if not certify:
        return {**verdict, "verdict": "FAIL", "checks": checks, "reason": f"judge rejected: {reason}"}
    return {**verdict, "checks": checks}


async def run_task(task: str, url: str | None, planner, run_dir: str | Path, *, judge,
                   headless: bool = True, url_guard=None, on_step=None, model=None, browser=None,
                   mode: str = "plan", driver=None, loop_budgets=None):
    """`mode` (ADR-027 Decision 1): "plan" is architecture B — one planning call
    over a condensed observation, then deterministic execution with
    observe/replan as the recovery path — and stays the default for every
    offline suite and every $0 path. "loop" calls `driver` after EVERY action
    with a fresh observation and lets the model choose the next tool call.
    The two modes share the executor's action implementations, the resolver, the
    trace schema, the verifier and the judge; the loop replaces the planning
    cadence and nothing else.

    `driver`: required in loop mode and refused outside it, the same
    injection-boundary shape `planner` and `judge` have. There is no default and
    nothing here can fall back to spending money.

    `loop_budgets`: the loop's caps, defaulting to `LOOP_BUDGETS`. Injectable
    for the same reason the judge is: runaway protection that can only be
    exercised by ACTUALLY running away is protection nothing checks. The two
    ceiling cases trip a cap of a few tokens and a few cents rather than
    scripting 500,000 tokens and $99 of stub usage — which is what they did
    first, and which put `cost $99.0000` on the headline of a suite whose whole
    claim is $0.00 (cost-discipline rule 4). The shipped numbers are recorded in
    ADR-028; what the cases grade is that the mechanism stops the run and says
    which cap it was.

    `judge`: required, no default -- same injection-boundary shape as
    `planner` (planner.py's docstring). Every caller names `stub_judge(...)`
    or `live_judge()` explicitly; nothing here can default to spending money.
    `browser`: an already-running Chromium to borrow instead of launching one.
    Callers that leave it None — the gateway and the CLI, i.e. production — get a
    private browser per run, because two callers' tasks must not share a process.
    The eval harness passes one browser for the whole suite: per-run driver start
    + launch + close measured 11.3s of the `fast` suite's 67.0s (ADR-013).
    `headless` is the borrowed browser's business, not ours.
    Isolation between runs does not depend on this: every run gets its own
    BrowserContext either way, so cookies and storage never cross."""
    if mode not in ("plan", "loop"):
        raise ValueError(f"unknown mode {mode!r}")
    if (driver is None) != (mode != "loop"):
        raise ValueError(f"mode {mode!r} needs exactly one of planner/driver, not both or neither")
    t0 = time.monotonic()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    budgets = {"actions": 0, "llm_tokens": 0, "llm_usd": 0.0, "replans": 0, "ms": 0,
               "judge_calls": 0, "judge_tokens": 0, "judge_usd": 0.0}
    trace: list[dict] = []
    # Holds at most one record awaiting the index of the attempt that replaces
    # it; resolved when that attempt is created, so a run that dies before it
    # never ships a supersede pointing into nothing.
    pending_supersede: list[dict] = []
    # Raw evidence for the OutcomeVerifier: what was read, and what the page
    # said at the moment it was read. The verifier never sees our conclusion.
    extractions: list[dict] = []
    # Every distinct page (by URL) this run has actually loaded, body text at
    # the time it was last seen. M34: a string that is identical across two
    # different pages of the same run is very likely site furniture (nav,
    # banner) rather than an answer to a page-specific question -- this is
    # the raw material for verify()'s `not_page_furniture` check, keyed by
    # URL so re-visiting a page updates rather than duplicates its evidence.
    page_bodies: dict[str, str] = {}

    # Hand each finished step to a live watcher (the gateway's SSE endpoint).
    # Every attempt is emitted, including the ones a ladder supersedes: the
    # stream is the trace, not a highlight reel (stream-shows-every-step).
    emit = on_step or (lambda _rec: None)

    def done(answer=None, failure=None, reason=None, final_url=None, digest=None, verdict=None):
        budgets["ms"] = int((time.monotonic() - t0) * 1000)
        result = assemble_result(trace, answer, budgets, failure, reason, final_url,
                                 digest, extractions, verdict, model, mode)
        (run_dir / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in trace) + "\n")
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    if reason := screen(task):
        return done(failure="unsupported", reason=reason)

    from playwright.async_api import async_playwright

    from .observe import DRILL_TEXT_HEAD, observe

    # At most one scoped observation, produced by an `observe` step and consumed
    # by the replan it triggers. A list rather than a variable so `execute`
    # (nested) can write it without a `nonlocal` dance.
    drilled: list[dict] = []

    answers: list = []

    async def finalize(final_url, digest):
        """Everything between the last action and the result, for BOTH modes.

        One extract -> scalar answer; several -> list (contract: answer
        string|list). An `extract_all` enumeration is reduced HERE, in code:
        the run gathered every candidate and `rank` picks the one the task's
        superlative asks for. Whether to reduce is the PLAN's (or the loop's)
        declaration, not a guess from the task text — three repairs guessed,
        from the answer's shape, from `is_aggregate`, then from a three-word
        enumerate regex, and each shipped a raw enumeration as the answer to a
        single-answer question (PR #29 R2, R9, R16). The executor refuses an
        `extract_all` that does not declare, so by the time an enumeration
        reaches here `enumerated` is a bool, never a guess. Everything about
        the COMPARISON is still code's: which value wins, and by what rule.

        The `len(answers) == 1` half is about the PLAN, not the task: a run
        that also extracts something else is composing a list, not ranking one
        (multi-extract-list). More than one enumeration never reaches here for
        an aggregate task, because `plan_gap` runs at EVERY point where mode B
        adopts a plan — the first plan, an act-ladder replan (PR #29 R3), and
        the drill-down replan M32 added, which was adopted unlinted until
        PR #34 R16 and made this sentence false: a mid-run drill-down could add
        a second enumeration and the run reported `success` with a list of
        lists. All three splice through one `adopt()`, so the claim rests on
        there being one path rather than on three call sites being remembered.
        Loop mode has no adoption point at all, which is why the same
        `plan_gap` is asked once more over the executed trace before this
        function is reached (ADR-027 Decision 5). A tie is refused rather than
        guessed, and a refusal is `semantic`: the page was read correctly and
        does not decide.

        Extracted as a function by M42 because loop mode has to reach it from
        inside the browser context while mode B reaches it from outside, and
        two copies of the grading tail is exactly the divergence ADR-027's
        "the verifier and the judge are shared" forbids.

        ponytail: extractions from an executed prefix are kept, so a replan
        that re-extracts the same value would append it twice and turn a scalar
        answer into a list. No case produces it (ADR-003); dedupe by (value,
        step intent) if one ever does.
        """
        answer = answers[0] if len(answers) == 1 else (answers or None)
        # Superseded attempts are excluded, and in loop mode that filter is
        # what makes this correct rather than decorative: a first `extract_all`
        # that omitted `rank` is refused by `execute` in a message that teaches
        # the model the exact retry, so "the first enumeration in the trace" was
        # the FAILED one, `enumerated` came back None, `rank` never ran, and the
        # raw candidate list was the answer to a which-one question (cold review
        # 2, `loop-failed-enumeration-does-not-disarm-rank`).
        enumerated = next((s.get("rank") for s in trace
                           if s.get("action") == "extract_all" and not s.get("superseded_by")
                           and not s.get("failure_class")),
                          None)
        if len(answers) == 1 and isinstance(answer, list) and enumerated is not None:
            try:
                answer = rank(task, answer, enumerated)
            except ValueError as e:
                return done(failure="semantic", reason=str(e), final_url=final_url, digest=digest)
        # The run is graded by the verifier, not by having reached this line.
        verdict = verify(trace=trace, extractions=extractions, answer=answer, task=task)
        # M36: the judge is the LAST rung of the escalation ladder -- a run that
        # failed L1 needs no judge call, the free deterministic checks above
        # already caught it (cost-discipline rule 1). Only a run that survived
        # every one of them reaches the terminal-verdict boundary.
        if verdict["verdict"] == "PASS":
            verdict = await _apply_judge(judge, task, answer, extractions, verdict, budgets)
        return done(answer=answer, final_url=final_url, digest=digest, verdict=verdict)

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
                    "rank": None, "resolved": None, "expected_state": None, "postcondition_ok": None,
                    "failure_class": None, "note": "pre-plan observation",
                    "retry_or_recovery": None, "superseded_by": None, "page_changed": None,
                    "screenshot": None, "ms": 0,
                }
                trace.append(rec)
                budgets["actions"] += 1
                try:
                    await navigate(page, url)
                    obs = await observe(page)
                    page_bodies[page.url] = await page_text(page)
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

            async def execute(step, rec):
                """Perform one step against the page. Raises; the caller classifies."""
                action = step["action"]
                if action == "navigate":
                    if url_guard and not url_guard(step.get("value") or ""):
                        raise StepError("task", f"blocked URL: {step.get('value')!r}")
                    await navigate(page, step["value"])
                    return
                if action not in ACTIONS:
                    raise StepError("task", f"unknown action {action!r}")
                if action == "final_answer":
                    # The loop's terminal call. It performs nothing — the answer
                    # is assembled in code from what was extracted, never from
                    # what the model says — but it IS a tool call, so it gets a
                    # trace record like every other one and the run's terminal
                    # decision is in the evidence rather than implied by it.
                    return
                if action == "wait_for":
                    # The wait IS the postcondition: `attempt` calls
                    # `check_state` on the way out, which polls for the same
                    # SETTLE_BUDGET_MS a postcondition gets and fails `act` when
                    # the predicate never holds. So there is nothing to do here
                    # except refuse a wait that does not say what it waits for —
                    # which would otherwise be a sleep, and the domain skill's
                    # rule is never sleep, always assert.
                    if not step.get("expected_state"):
                        raise StepError("task", "a wait_for must carry the expected_state it is "
                                                "waiting for; a wait with no predicate is a sleep")
                    return
                if action == "go_back":
                    # Browser history, the one navigation primitive that needs
                    # no URL. `go_back` returns None when there was nothing to
                    # go back to, which is an act failure and not a quiet no-op
                    # the next step reads through.
                    #
                    # ponytail: Playwright also returns None for a same-document
                    # history entry, so an in-page back on a pushState app reads
                    # as a failure here. No fixture has that shape; the upgrade
                    # is to compare page.url before and after instead, once one
                    # does.
                    if await page.go_back(wait_until="domcontentloaded") is None:
                        raise StepError("act", "go_back: this tab has no earlier page to "
                                               "return to")
                    return
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
                # `extract_all` returns a set, and the answer is either that set
                # or one item of it. Nothing in the plan's shape, the page or the
                # trace distinguishes them, and three repairs that inferred it
                # from the task text each shipped a raw enumeration as the answer
                # to a single-answer question (PR #29 R2, R9, R16). So the plan
                # must say, and a plan that does not is one the executor cannot
                # honour — the same closed-world refusal an unknown action or an
                # unsupported target key already gets
                # (case extract-all-undeclared-intent-fails-loud).
                if action == "extract_all" and not isinstance(step.get("rank"), bool):
                    raise StepError("task", "extract_all must declare `rank`: true if the answer "
                                            "is the one item the task ranks for, false if the "
                                            "answer is the enumeration itself")
                # `extract_all` wants every match, so ambiguity is the answer
                # rather than a locate failure — the only difference in how a
                # target is resolved.
                # ADR-024's refusal, re-homed to tool-call time (ADR-027
                # Decision 5). In mode B `plan_gap` has already refused this
                # plan and the clause is unreachable; in loop mode this IS the
                # refusal, raised as the call is emitted so the root read never
                # happens, and the model is told why and chooses again.
                if gap := root_target_gap(step):
                    raise StepError("task", gap)
                loc = None
                if step.get("target") or action in NEEDS_TARGET:
                    loc, tier, narrowed = await resolve(
                        page, step.get("target") or {}, many=action == "extract_all",
                        anchor=step.get("anchor"), task=task, action=action)
                    rec["resolved"] = {"tier": tier, "description": str(step.get("target"))}
                # WHICH narrowing rung settled an ambiguity the plan left open
                # (M38). It goes in the trace because a run that answered from
                # one of several matches has to say so — but NOT as
                # `retry_or_recovery`: nothing failed and no ladder ran, the
                # same ruling the plan lint above and M32's drill-down got, and
                # the recovery metric counts rungs that rescued a classified
                # failure (specs/001, ADR-003).
                    if narrowed:
                        rec["note"] = "; ".join(
                            x for x in (rec["note"], f"narrowed: {narrowed}") if x)
                if action == "observe":
                    # An observation asserts nothing about the page, so there is
                    # nothing for an expected_state to hold. Refused rather than
                    # ignored (`resolver-unknown-target-key`'s rule): left to
                    # `check_state`, a failing assertion raised StepError("act")
                    # for a step that acted on nothing, diagnosed the run
                    # `failure:act` and opened the act/replan recovery ladder for
                    # it (M32 cold review, runner-up; case
                    # observe-step-cannot-carry-expected-state).
                    if step.get("expected_state"):
                        raise StepError(
                            "task", "an observe step cannot carry expected_state: "
                                    f"{step['expected_state']}")
                    # Drill-down (M32, ADR-020): re-observe THIS subtree with the
                    # whole element budget and a longer text head, then hand it
                    # to the replanner below. Reads the page and changes nothing,
                    # so like `extract` it has no postcondition of its own.
                    drilled.append(await observe(page, root=loc,
                                                 text_head=DRILL_TEXT_HEAD))
                elif action == "click":
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
                elif action == "select_option":
                    # The options are READ first, then one is chosen by value.
                    # Letting Playwright match the string itself would mean two
                    # attempts (label, then value), each burning its own timeout
                    # on the failure path — 20s per absent option in a suite
                    # budgeted at 90s — and would tell the model nothing about
                    # what it could have picked instead.
                    want = step.get("value") or ""
                    opts = await loc.evaluate(OPTIONS_JS)
                    if opts is None:
                        # The wrong element, not a broken action — the same
                        # ruling `fill` gets when it lands on something that
                        # cannot hold a value (`relocate-fill-non-editable`).
                        raise StepError("locate", "resolved element has no options to select: "
                                                  f"{step.get('target')}")
                    if not opts:
                        # NO options is not the same as no MATCHING option. A
                        # `<select>` painted from a `fetch()` is in the DOM,
                        # resolvable and empty until the response lands, and the
                        # eager read above is taken the instant the element
                        # resolved — which is precisely the auto-wait that
                        # reading the options ourselves gives up. So wait for the
                        # first option to exist, once, and read again. A control
                        # that never fills still fails loudly below, having paid
                        # the wait; nothing else on the page is waited on
                        # (`action-select-option-waits-for-fetch-painted-options`).
                        try:
                            # `attached`, not the default `visible`: the options
                            # of a closed `<select>` are never visible, so the
                            # default state waits out the whole timeout and only
                            # then reads a list that arrived seconds earlier
                            # (measured: 10.2s vs 1.6s on the case below).
                            await loc.locator("option").first.wait_for(
                                state="attached", timeout=10_000)
                        except Exception:
                            pass  # let the empty-offer message below say it
                        opts = await loc.evaluate(OPTIONS_JS)
                    match = next((o for o in opts if want in o), None)
                    if match is None:
                        raise StepError("act", f"no option matches {want!r}; this control offers "
                                               f"{[label for _v, label in opts]}")
                    await loc.select_option(value=match[0], timeout=10_000)
                    # Readback, for the reason `fill` reads back: the postcondition
                    # is what the browser says is selected, not that the call
                    # returned (`action-select-option-refuses-an-absent-option`).
                    if await loc.input_value() != match[0]:
                        raise StepError("act", f"select readback is not {want!r}")
                    rec["postcondition_ok"] = True
                elif action == "press":
                    # State-changing like a click, and verified the same way: by
                    # the authored expected_state, which `verify` now requires of
                    # every state-changing verb rather than of `click` alone.
                    if not step.get("value"):
                        raise StepError("task", "a press must name the key in `value`")
                    if loc is not None:
                        await loc.press(step["value"], timeout=10_000)
                    else:
                        await page.keyboard.press(step["value"])
                elif action == "scroll":
                    # `window.scrollBy`, not `mouse.wheel`: the wheel dispatches
                    # an event and the scroll lands whenever it lands, so the
                    # postcondition below would be a race. This is the same
                    # site-agnostic primitive either way — no selector, no DOM
                    # path, nothing a reader could not do.
                    before_y = await page.evaluate("() => window.scrollY")
                    if loc is not None:
                        await loc.scroll_into_view_if_needed(timeout=10_000)
                        if not await loc.is_visible():
                            raise StepError("act", "scrolled to the target and it is still not "
                                                   f"visible: {step.get('target')}")
                    else:
                        await page.evaluate("d => window.scrollBy(0, d)",
                                            int(step.get("value") or 800))
                        if await page.evaluate("() => window.scrollY") == before_y:
                            raise StepError("act", "scroll moved nothing: the page is already at "
                                                   "that position, so there is nothing further "
                                                   "down to read")
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
                    body = await page_text(page)
                    anchor = step.get("anchor")
                    # M34 R2-1: which occurrence of `val` is this, when it is not
                    # unique on the page (a decoy blurb beside the real answer,
                    # case verifier-context-anchors-real-occurrence)? A DOM-derived
                    # hint (TEXT_OFFSET_JS) picks the real one via `_closest_
                    # occurrence`, rather than `evidence_window`/`_context` always
                    # taking the first. `real_offset < 0` (value somehow not found
                    # in body at all -- should not happen when `loc.inner_text()`
                    # just returned it, but this is evidence capture, not an
                    # assumption) degrades to the old first-occurrence behaviour
                    # in both `evidence_window` and `value_offset` below.
                    # `.first` is load-bearing: an `extract_all` locator resolves
                    # to every match, and Playwright's strict mode refuses
                    # `evaluate` on a multi-match locator. The hint is about
                    # vals[0] either way; every later value falls back to its own
                    # first occurrence, below.
                    real_offset = _closest_occurrence(
                        body, vals[0], await loc.first.evaluate(TEXT_OFFSET_JS))
                    # body_len is the real page the value was read from -- verify()'s
                    # not_a_dump denominator prefers this over len(page_text), because
                    # page_text is evidence_window()'s output: capped at PAGE_TEXT_KEEP
                    # and doubled when a distant anchor forces a second window onto it
                    # (case verifier-dump-ratio-anchor-flip).
                    # M34: evidence for verify()'s `not_page_furniture` -- every
                    # OTHER distinct page this run has already loaded, excluding
                    # the one the value was just read from. A value that is also
                    # verbatim on a different page is very likely nav/banner
                    # furniture, not an answer to a page-specific question
                    # (docs/analysis.md §8a-3). Recorded BEFORE this page's own
                    # body is (re-)stored below, so a page never gets compared
                    # against itself.
                    #
                    # M31: one evidence record per enumerated value, because
                    # `grounded`, `not_a_dump` and `not_page_furniture` all judge
                    # per extraction — an enumeration is judged row by row
                    # (verifier-list-rows-not-a-dump), not as one page-sized blob.
                    # `extract` contributes exactly one value, so the loop is the
                    # same code for both verbs.
                    other_page_text = " ".join(t for u, t in page_bodies.items() if u != page.url)
                    for v in vals:
                        # M34 R2-1: which occurrence of `v` is this, when it is
                        # not unique on the page? The DOM hint picks the real one
                        # rather than always taking the first. For `extract_all`
                        # the hint is the step's locator, which spans every match,
                        # so each value falls back to its own first occurrence —
                        # the pre-M34 behaviour, per value.
                        off = (real_offset if v == vals[0]
                               else _closest_occurrence(body, v, -1))
                        extractions.append(
                            {"value": v,
                             "page_text": evidence_window(body, v, anchor, offset=off),
                             "body_len": len(body), "other_page_text": other_page_text,
                             "value_offset": (off - _window_lo(body, off)) if off >= 0 else None})
                    page_bodies[page.url] = body
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
                    "value": step.get("value"), "anchor": step.get("anchor"),
                    "rank": step.get("rank"), "resolved": None,
                    "expected_state": step.get("expected_state"), "postcondition_ok": None,
                    "failure_class": None, "note": note, "retry_or_recovery": recovery,
                    "superseded_by": None, "page_changed": None, "screenshot": None, "ms": 0,
                }
                trace.append(rec)
                # A replan is only allowed to skip the step it replaces once the
                # replacement attempt actually exists. Writing the pointer early
                # shipped traces whose run-killing step claimed to be superseded
                # by an index that was never created (case supersede-never-dangles).
                # `observe` is excluded: `superseded_by` claims "this failed
                # attempt was replaced by that one", and an observation replaces
                # nothing — it reads. The pointer waits for the first attempt
                # that actually acts (PR #34 R1/R2). If the run ends before one,
                # nothing is written and the failed step keeps
                # `superseded_by: null`, which is the safe direction
                # `supersede-never-dangles` asks for.
                # `observe` and `final_answer` are excluded for the same reason:
                # `superseded_by` claims "this failed attempt was REPLACED by
                # that one", and neither replaces anything — one reads, and the
                # other stops. If the run ends before a replacement exists,
                # nothing is written and the failed step keeps
                # `superseded_by: null`, which is the safe direction
                # `supersede-never-dangles` asks for and, in loop mode, the
                # direction that correctly leaves a give-up-after-a-failure run
                # graded on its failure.
                if pending_supersede and step["action"] not in ("observe", "final_answer"):
                    pending_supersede.pop()["superseded_by"] = rec["i"]
                budgets["actions"] += 1
                s0 = time.monotonic()
                cls = None
                # Did this action change anything at all? The only evidence that
                # separates a replan legitimately skipping work already done from
                # one laundering an action that did nothing (replan-cannot-launder-noop-action).
                before = (await page_text(page)
                          if not step["action"].startswith("extract")
                          and step["action"] not in READ_ONLY_ACTIONS else None)
                # Where this step's evidence starts, so a step that FAILS can be
                # rolled back to it. `execute` writes `extractions` and `answers`
                # before every check it can still fail — the identity-anchor
                # check is the one that raises after the write, and the URL guard
                # below raises after `execute` has returned entirely. That was
                # harmless for five milestones because mode B ends the run at the
                # first failed step, so nothing ever read what a failed step had
                # written. Loop mode makes a failed call routine and the refused
                # read stayed in `answers`: `success`, verdict PASS, with the
                # trace carrying `failure_class: 'semantic'` on the very step the
                # answer came from (cold review 1, `loop-refused-anchor-is-not-
                # an-answer`). Rolled back HERE rather than by reordering that
                # one check, because "a failed step leaves no evidence behind" is
                # the property, and it has two instances already.
                mark = (len(extractions), len(answers))
                try:
                    await execute(step, rec)
                    if url_guard and not url_guard(page.url):
                        # The guard is not just an input filter: a click, a 302 or
                        # a meta-refresh can walk the browser off the allowed host
                        # after the submitted URL passed (url-guard-holds-after-navigation).
                        raise StepError("task", f"navigated to blocked URL: {page.url!r}")
                    if before is not None:
                        # The SAME scope `before` was read at, and that scope
                        # is every frame. Two findings pin the pair, and neither
                        # alone constrains this line:
                        #
                        #   * asymmetric (`before` main-only, `after` all frames)
                        #     made every step of any framed page read as changed,
                        #     disarming `changed_nothing` — the whole evidence
                        #     behind the anti-laundering guard, in BOTH modes —
                        #     and telling the loop driver a no-op did something
                        #     (PR #57 R1,
                        #     `replan-cannot-launder-noop-action-in-a-frame`);
                        #   * symmetric-but-frames-BLIND flipped the sign instead
                        #     of removing the defect: a control whose only effect
                        #     is inside an iframe — an inspector's source pane,
                        #     the exact shape M42 leg (a) exists for — recorded
                        #     `false`, so the guard refused a legitimate replan
                        #     and the run died stating as fact that a step which
                        #     had just loaded a document ID "changed nothing on
                        #     the page" (PR #57 R13,
                        #     `replan-after-an-iframe-only-change-is-not-laundering`).
                        #
                        # Symmetric and frames-aware is the only setting under
                        # which both cases are green, and they are the same page
                        # shape with and without a real effect. The hazard the
                        # previous comment cited — a third-party iframe with a
                        # ticking clock flipping this true on every step — is
                        # real but has never been demonstrated here, while the
                        # false negative was; this repo widens on what a probe
                        # found, not on what someone imagined. Declared as the
                        # accepted cost in `observe.page_text` and tracked as
                        # T-M42-14 with the repro that would close it.
                        after = await page_text(page)
                        rec["page_changed"] = after != before
                        page_bodies[page.url] = after
                    checked = await check_state(page, step.get("expected_state"))
                    if checked is not None or rec["postcondition_ok"] is None:
                        rec["postcondition_ok"] = checked
                    if rec["postcondition_ok"] is False:
                        raise StepError("act", f"expected_state not reached: {step.get('expected_state')}")
                except Exception as exc:
                    cls = classify(step["action"], exc)
                    rec["failure_class"] = cls
                    rec["note"] = "; ".join(filter(None, [rec["note"], f"{type(exc).__name__}: {exc}"]))
                    del extractions[mark[0]:], answers[mark[1]:]
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


            # --- Loop mode: the model chooses every step (ADR-027, ADR-028) ---
            async def drive_loop():
                """One tool call per model turn, a fresh observation after each.

                What is NOT in here is the point. The executor's actions, the
                resolver, the trace schema, `finalize`'s answer assembly, the
                verifier and the judge are the same objects mode B uses; this
                function owns the CADENCE, the loop budgets, the no-progress
                harness, and the two guards that lost their anchor when the plan
                did (ADR-027 Decision 5).

                A failed call is not a failed RUN here, and that is the whole
                difference from mode B's ladders: mode B has to guess a recovery
                from a fresh observation because its plan is already written,
                while the loop simply tells the model what happened and asks
                again. The budgets and the no-progress harness are what stop
                that from being unbounded — an eval this repo watched red
                (`loop-no-progress-revisit-ends-the-run-loudly`) rather than a
                property anyone asserted.
                """
                observation, note, last_state = obs, None, None
                seen: dict = {}
                while True:
                    if stop := budget_stop(budgets, loop_budgets or LOOP_BUDGETS):
                        return done(failure="env", reason=stop, final_url=page.url)

                    # --- no-progress harness (M42 leg b) ---------------------
                    # A step cap is not a harness: it lets a run grind its whole
                    # budget down in a circle and then report a RESOURCE
                    # failure, which names the symptom and not the cause. The
                    # interviewer's 首頁↔dashboard loop was 18 model calls and 2
                    # repairs of exactly that. `answers` is the fact counter
                    # because an extraction is the only thing that adds a fact;
                    # re-arriving somewhere having learnt something is progress.
                    # A VISIT, not a turn. Counting turns was this harness's
                    # own first defect and its golden case caught it: select an
                    # option, click, then wait for the result is three turns on
                    # one page whose observation barely moves, and it was being
                    # called a circle and killed at the third one. A visit
                    # begins when the run ARRIVES somewhere it was not the turn
                    # before, which is what "revisits the same state" means and
                    # what the 首頁↔dashboard loop actually does.
                    #
                    # ponytail: the other no-progress shape — the same call
                    # repeated forever on one page — is bounded by the step cap
                    # rather than named here. Add a (state, call) repeat counter
                    # if a run ever produces it; nothing has.
                    # DISTINCT values, not the count: re-reading the same
                    # breadcrumb on every pass around a 首頁↔dashboard circle is
                    # not progress, and counting extractions let exactly that
                    # reset the harness forever and die at the budget cap
                    # instead — the symptom-not-cause failure this exists to
                    # replace, on the reported trace shape (cold review 7).
                    facts = len({str(a) for a in answers})
                    state = (page.url, page_signature(observation))
                    st = seen.setdefault(state, {"visits": 0, "facts": facts})
                    if facts > st["facts"]:
                        st.update(visits=0, facts=facts)
                    if state != last_state:
                        st["visits"] += 1
                    last_state = state
                    if st["visits"] > LOOP_REVISIT_CAP:
                        return done(failure="env", final_url=page.url, reason=(
                            f"no progress: step {len(trace)} arrived at {page.url} in the same "
                            f"page state for the {st['visits']}th time with nothing new "
                            "extracted, and the forced strategy change did not move it"))
                    if st["visits"] == LOOP_REVISIT_CAP:
                        # Forced strategy change first, loud stop second. Ending
                        # on the first repeat would refuse the legitimate case
                        # (a page revisited on the way somewhere); ending never
                        # is the circle. `env` for the same reason `budget_stop`
                        # and the drill-down's own no-progress guard use it — a
                        # ladder that could not help IS the failure — with the
                        # difference that the reason now says why.
                        note = (f"NO PROGRESS: you have been on this exact page state "
                                f"{st['visits']} times and nothing new has been extracted since. "
                                "Repeating what you have already tried will end this run. Change "
                                "strategy: read what is already on this page, look inside a "
                                "container you have not opened, or stop with what you have.")

                    try:
                        call, usage = await driver(task, page.url, observation, trace, answers,
                                                   note)
                    except PlanError as e:
                        # Same split as mode B's first plan: the call worked and
                        # the MODEL did not produce a tool call. Its billed
                        # usage is charged to the model that emitted the prose.
                        budgets["llm_tokens"] += e.usage["llm_tokens"]
                        budgets["llm_usd"] += e.usage["llm_usd"]
                        return done(failure="env", reason=f"driver rejected: {e}",
                                    final_url=page.url)
                    except Exception as e:
                        return done(failure="env", reason=f"driver failed: {e}",
                                    final_url=page.url)
                    budgets["llm_tokens"] += usage["llm_tokens"]
                    budgets["llm_usd"] += usage["llm_usd"]
                    note = None
                    if not isinstance(call, dict) or not call.get("action"):
                        return done(failure="env", final_url=page.url, reason=(
                            f"driver returned something that is not a tool call: {call!r}"))

                    rec, cls = await attempt(call)
                    if cls:
                        # Including the re-homed refusals, which arrive here as
                        # `task` failures raised by `execute` before anything
                        # touched the page: the call is recorded as refused, the
                        # reason goes back to the model, and the root read never
                        # happened (`loop-refuses-a-document-root-extract`).
                        # The failed attempt is superseded by whatever the
                        # model does next — the same pointer mode B's replan
                        # writes, and the same mechanism, because "this attempt
                        # was replaced by that one" is exactly what a loop
                        # recovery is. It is what keeps a recovered run from
                        # being graded on the attempt it recovered FROM (cold
                        # review 6) and what stops a refused `extract_all` from
                        # being read as the run's ranking declaration (cold
                        # review 2). `attempt` writes the pointer only once a
                        # replacement exists and never for `final_answer`, so a
                        # model that gives up right after a failure leaves it
                        # unsuperseded — and `verify`'s `no_abandoned_failure`
                        # is what makes that mean anything. The two halves have
                        # to ship together: this exclusion asserted the property
                        # for a round while the verifier could not see a
                        # `locate` or `extract` failure at all, so the run
                        # reported success with the failure in its own trace
                        # (PR #57 R6).
                        pending_supersede.append(rec)
                        # `page_changed` is THREE-valued and null means "never
                        # compared", not "nothing moved" — every failure raised
                        # inside `execute` leaves it null, because the before/
                        # after comparison is on the line after `execute`
                        # returns. Telling the model a page is unchanged when
                        # nobody looked is how a fill that already typed, or a
                        # click that already navigated, gets repeated (cold
                        # review 5).
                        moved = {True: "The page changed.", False: "The page did not change.",
                                 None: "Whether the page changed was never checked."}
                        note = (f"Your last call FAILED: {rec['note']}. "
                                f"{moved[rec['page_changed']]} Do not repeat it unchanged.")
                        observation = await look() or observation
                        continue
                    if call["action"] == "final_answer":
                        digest = (await page_text(page))[:500]
                        # ADR-018's aggregate single-read rule, re-homed to
                        # answer assembly (ADR-027 Decision 5). Mode B refuses
                        # such a plan before it runs; a loop has no plan to read
                        # ahead of time, so the same `plan_gap` is asked over
                        # what the run ACTUALLY did — one rule, two anchors,
                        # never a second copy of the judgement. Refused steps and
                        # superseded attempts are excluded: they are not what the
                        # answer would be assembled from.
                        executed = [{"action": s["action"], "target": s["target"],
                                     "rank": s["rank"]} for s in trace
                                    if not s["failure_class"] and not s["superseded_by"]]
                        if gap := plan_gap(task, executed):
                            return done(failure="task", final_url=page.url, digest=digest,
                                        reason=("the answer cannot be assembled from what this "
                                                "run actually did: " + gap))
                        return await finalize(page.url, digest)
                    # ADR-020's drill-down, in loop mode. `execute` has put the
                    # scoped observation in `drilled`; mode B pops it into a
                    # replan, and without this branch the loop would hand the
                    # model a fresh PAGE observation on the next turn — the
                    # drill-down a silent no-op while its tool description
                    # promises "you are shown that subtree alone". ADR-027
                    # Decision 5 rules that loop-mode `observe` spends the STEP
                    # budget like any other call and no replan budget, which is
                    # what this branch does by not touching `budgets["replans"]`.
                    if call["action"] == "observe" and drilled:
                        observation = drilled.pop()
                        # ...and SAY it is a subtree. `observe.render` prints the
                        # PAGE's url and title either way, so without this the
                        # model is handed a scoped observation that looks exactly
                        # like a full-page one — the tool description it was
                        # given says "you are shown that subtree alone", and the
                        # second half of that claim was not being delivered
                        # (spec-drift audit finding 10). Mode B's equivalent path
                        # has always passed this note.
                        note = (f"The observation above is the subtree of "
                                f"{call.get('target')} ONLY, not the whole page.")
                    else:
                        observation = await look() or observation

            if mode == "loop":
                return await drive_loop()

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
            def adopt(prefix: int, new_steps: list):
                """Splice a plan into the running one — the only place `steps`
                is rebound after the first plan arrives, and therefore the only
                place the lint can be enforced rather than remembered. (The
                first plan is not spliced into anything; it is linted where it
                lands, on the line below.)

                ADR-018 states the invariant as "lint at every adoption point,
                not at these two call sites", and named M32's drill-down as the
                next one. M32 then adopted its replan without a lint, and a
                mid-run drill-down could add a second enumeration: `success`,
                verdict PASS, an unranked list of lists as the answer to "which
                product has the most reviews" (PR #34 R16, the seventh
                occurrence of this class). The fix is not a third `plan_gap`
                call — hand-placing the third is how the second was forgotten —
                so all three adoption points come through here. A fourth
                cannot be added without one, and that is enforced rather than
                promised: `plan-adoption-is-the-only-steps-rebind` parses this
                file and reddens on any binding of `steps` after the first plan
                that is not adopt-derived (PR #34 R25 — the promise stood on
                convention for one round, which is exactly how ADR-018's
                version of it failed).

                Returns (steps, None) when the plan is adoptable, or
                (None, gap) when the lint refuses it. The CALLER decides what a
                refusal means: before execution it is a re-plan, mid-run it
                ends the run, because there is nothing left to re-plan with.
                """
                candidate = steps[:prefix] + new_steps
                gap = plan_gap(task, candidate)
                return (None, gap) if gap else (candidate, None)

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
                adopted, _ = adopt(0, new_steps)
                if not new_steps or new_steps == steps or adopted is None:
                    return done(failure="task",
                                reason=f"plan rejected before execution: {gap}; the replan "
                                       "did not close the gap")
                budgets["replans"] += 1
                lint_note = f"replanned before execution — plan lint: {gap}"
                steps = adopted

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
                # Same rule for the label: a strategy switch is worn by the
                # attempt that switches strategy, and an `observe` is not one —
                # it recovered nothing, and `recovery_rungs` publishes the count
                # (PR #34 R2; `specs/001-browser-contract.md`, ADR-020 §2 both
                # already said so). It waits for the first acting attempt.
                read_only = step["action"] == "observe"
                rec, cls = await attempt(step, note=pending,
                                         recovery=("recovery" if pending_recovery
                                                   and not read_only else None))
                pending = None
                if not read_only:
                    pending_recovery = False

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

                # --- Drill-down: observe a subtree -> replan against it -------
                # M32 (ADR-020). Not a recovery ladder: nothing failed. The
                # planner looked at a capped observation, saw the container the
                # answer is in and none of its contents, and asked for a closer
                # look — progressive disclosure of the PAGE, not of the tool set
                # (prompts/015). The scoped observation goes back through the
                # same observation+note argument a replan already uses, and
                # spends the same MAX_REPLANS budget, so a planner that keeps
                # asking to look instead of acting runs out exactly like one that
                # keeps failing (INV-3, budget_stop).
                if step["action"] == "observe" and cls is None and drilled:
                    scoped = drilled.pop()
                    if budgets["replans"] >= MAX_REPLANS:
                        # Loud, not a fall-through. `cls` is None here, so
                        # letting the loop continue ran whatever the plan put
                        # AFTER the observe — the run spent its whole planning
                        # budget asking for a closer look, never got one, and
                        # then answered from the observation the drill-down
                        # existed to replace, reporting `success` (M32 cold
                        # review, finding 1; case
                        # observe-refused-drilldown-stops-the-run). `env` for
                        # the same reason `budget_stop` uses it: a resource ran
                        # out. The class of a ladder that failed to help is the
                        # failure it was fixing (specs/000) — this ladder was
                        # fixing nothing, so the exhaustion is the failure.
                        return done(failure="env", reason=(
                            f"step {rec['i']} asked to observe {step.get('target')} and the "
                            f"replan budget is exhausted ({MAX_REPLANS}); the rest of this "
                            "plan was written against an observation it asked to replace"))
                    else:
                        try:
                            new_steps, usage = await planner(
                                task, page.url, scoped,
                                note=(f"step {rec['i']} asked to look closer at "
                                      f"{step.get('target')}. The observation above is THAT "
                                      "subtree only, not the whole page."))
                        except PlanError as e:  # same split as the first plan
                            budgets["llm_tokens"] += e.usage["llm_tokens"]
                            budgets["llm_usd"] += e.usage["llm_usd"]
                            return done(failure="env", reason=f"replanner rejected: {e}")
                        except Exception as e:
                            return done(failure="env", reason=f"replanner failed: {e}")
                        budgets["llm_tokens"] += usage["llm_tokens"]
                        budgets["llm_usd"] += usage["llm_usd"]
                        # The one no-progress shape this branch can produce: a
                        # plan that just asks to look at the same thing again.
                        # Family 2's other two guards are about laundering a
                        # FAILED action, and nothing failed here.
                        # The same evidence rule family 2 applies, because this
                        # is a second planner call and it can return the same
                        # laundering plan (PR #34 R1,
                        # `observe-drilldown-cannot-launder-noop-action`). The
                        # failed action is still outstanding here — an `observe`
                        # attempt does not consume it — so the run dies of what
                        # it actually died of: that action.
                        outstanding = pending_supersede[-1] if pending_supersede else None
                        if (outstanding is not None
                                and changed_nothing(outstanding)
                                and reads_without_acting(new_steps)):
                            return done(failure="act", reason=(
                                f"step {outstanding['i']} ({outstanding['action']}) failed and "
                                "changed nothing on the page; the plan after the drill-down at "
                                f"step {rec['i']} would read the page as if it had worked"))
                        if not new_steps or new_steps == steps[si:]:
                            return done(failure="env", reason=(
                                f"step {rec['i']} asked to observe {step.get('target')} and the "
                                "replan made no progress (identical or empty plan)"))
                        adopted, gap = adopt(si, new_steps)
                        if gap:
                            # Mid-run there is no re-plan left to try: the
                            # drill-down WAS the replan. specs/000's rule that a
                            # plan the executor cannot honour is `task` applies
                            # here exactly as it does before execution.
                            return done(failure="task", reason=(
                                f"the plan after the drill-down at step {rec['i']} was rejected "
                                f"by the plan lint: {gap}"))
                        if adopted is not None:
                            budgets["replans"] += 1
                            pending = (f"replan #{budgets['replans']} after the drill-down at "
                                       f"step {rec['i']}: {len(new_steps)} step(s) planned from "
                                       "the subtree observation")
                            # Same evolving prefix as family 2. The `observe`
                            # step itself is dropped, not superseded: it did what
                            # it was asked to do, and re-running it would be the
                            # loop this budget exists to bound.
                            steps = adopted
                            continue

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
                        # Every extraction verb (M31/PR #29 R1: `extract_all`
                        # laundered exactly like `extract` while this named only
                        # the literal string) AND transparent to a leading
                        # `observe` (M32/PR #34 R1: an observation changes
                        # nothing, so `[observe, extract]` dropped the failed
                        # action just as surely). Each parent fixed one half and
                        # neither is sufficient alone -- `reads_without_acting`
                        # is the union, and `observe-cannot-launder-extract-all`
                        # is the case the merge itself made necessary.
                        drops_action = reads_without_acting(new_steps)
                        if not new_steps or new_steps == steps[si:]:
                            rec["note"] += "; replan made no progress (identical or empty plan)"
                        elif new_steps[0] == steps[si]:
                            # Family 1 enforces "a rung must be a different tier";
                            # this is family 2's equivalent. Re-issuing the step
                            # that just failed is a retry, and specs/001 keeps
                            # retries out of the recovery metric by construction.
                            rec["note"] += "; replan re-issued the step that just failed"
                        elif drops_action and changed_nothing(rec):
                            rec["note"] += ("; replan would skip a failed action that changed "
                                            "nothing on the page")
                        # The lint runs at EVERY point the executor adopts a plan,
                        # not only the first one. `steps[:si] + new_steps` is the
                        # plan of record after this replan, executed prefix
                        # included, so a replan that adds a second enumeration is
                        # refused here exactly as the first plan would have been —
                        # the run then ends as the `act` failure it already was.
                        # Linting only the first plan let a mid-run replan produce
                        # the unranked list of lists ADR-018 names as the defect
                        # (PR #29 R3, case plan-lint-holds-across-a-midrun-replan).
                        elif lint := adopt(si, new_steps)[1]:
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
                            steps = adopt(si, new_steps)[0]
                            continue

                if cls:
                    return done(failure=cls,
                                reason=f"step {rec['i']} ({step['action']}): {rec['note']}")
                si += 1

            digest = (await page_text(page))[:500]
            final_url = page.url
        finally:
            await ctx.close()  # the run's own context; the browser may be shared

    return await finalize(final_url, digest)
