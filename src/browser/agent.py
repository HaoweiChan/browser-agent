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

import asyncio
import contextlib
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .judge import JUDGE_ATTEMPTS, RUN_JUDGE_BUDGET
from .observe import page_text
from .planner import PlanError
from .resolver import (DOC_ROOT_ROLES, ResolveError, TARGET_KEYS,
                       relocation_candidates, resolve, _whole_string)
from .verifier import STATE_CHANGING, is_aggregate, rank, verify

# The executor's whole vocabulary (ADR-027 Decision 2 widens it; ADR-028 records
# the semantics). `navigate` is handled before this set is consulted because it
# is the only action that moves the browser without resolving anything.
#
# Shared by both modes on purpose: the loop replaces the planning CADENCE, not
# the machinery, so a verb mode B can execute is a verb the loop can call and
# vice versa — which is what makes `loop-mode-b-cannot-read-the-un-awaited-result`
# an honest A/B rather than a comparison of two vocabularies.
ACTIONS = ("navigate", "click", "fill", "extract", "extract_all", "observe",
           "select_option", "scroll", "press", "wait_for", "go_back", "click_at",
           "final_answer")

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

# How long the select step waits for a fetch-painted `<select>` to fill.
#
# Deliberately its own knob, not SETTLE_BUDGET_MS, for the reason SETTLE_BUDGET_MS
# already gives about the fix budget: they answer different questions. Settling is
# "has the page finished loading"; this is "has one control's own network round
# trip landed", asked on a page that already fired `load` and already resolved the
# element. It is also the only budget in this file that is paid IN FULL on the
# failure path — every control that never fills costs exactly this much — so it is
# the one that shows up in the suite's wall clock, and `max_ms` on
# `action-select-option-never-filled-fails-loud` is what keeps that visible.
# 1s against a fixture whose options land at 0.3s and a first read measured at
# ~0.1s. A slower page loses the wait and fails loudly, which the replan ladder
# can act on; a longer budget buys that back at a price the published band cannot
# currently pay (T-M42-20-D3/D9).
SELECT_OPTIONS_WAIT_MS = 1_000
# A submit button that disables itself has declared that its action is still in
# flight.  Wait for that same control to become usable again before reading the
# page; static and instantly-completing buttons pay one boolean check.
DISABLED_SUBMIT_WAIT_MS = 15_000

# Actions that leave the page as they found it, so `attempt` does not pay for a
# before/after comparison. `observe` reads, and `final_answer` is the loop's
# terminal call — it acts on nothing at all.
READ_ONLY_ACTIONS = {"observe", "final_answer"}

# Actions whose `expected_state` is checked against the WHOLE page — every
# frame — rather than the one document the action touched (ADR-036). These
# three have no single acted document: `navigate` and `go_back` loaded every
# document on the page, frames included, and `wait_for` performs nothing — it
# is an authored assertion about where the page will paint, and a page that
# paints into an iframe legitimately wants the frame (the S1/S4 shape M42's
# frame reach was built for). Everything else is verified in the document
# `resolve` returned its target from, or the main document when nothing
# resolved — so a consent iframe, a chat widget or a display:none tracking
# frame can no longer earn a click's postcondition
# (postcondition-decoy-iframe-cannot-satisfy-text-visible).
PAGE_WIDE_STATE = {"navigate", "go_back", "wait_for"}

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
# The pattern is the finding for NEIGHBOUR-only rules: each traded a false
# refusal for a false ALLOW. ADR-040 measures the previously untried variable —
# a read frame — and binds every blocked match to a narrow, demonstrated mention
# vocabulary. The base alternation still fails closed everywhere else.
# M45-D6: every CJK term above was spelled as a traditional|simplified PAIR, so a
# spelling that mixes the two scripts INSIDE one word matched neither alternative
# and sailed through. Measured on this tree before the fix: `screen('幫我輸入验证
# 碼')`, `screen('幫我购買這個商品')`, `screen('購买這個商品')` and
# `screen('幫我輸入驗证码')` all returned None. Mixed script is not exotic — input
# methods, copy-paste between zh-TW and zh-CN sources, and OCR all produce it.
#
# Folding each pair to a character class fixes it per character rather than per
# spelling. Only terms with more than ONE variant character have a mixed form at
# all, so the surface is exactly 驗證碼 (2^3 spellings, 2 covered before) and
# 購買 (2^2, 2 covered): 密[碼码], [刪删]除 and 下[載载] are the same two strings
# they always were, written differently.
#
# THIS IS A DELIBERATE WIDENING OF THE REFUSAL POLICY, not a behaviour-neutral
# refactor, and it moves every folded term at once: nine spellings that were
# allowed now refuse. It fails CLOSED, which is the safe direction for this
# screen — but "safe direction" is not "unwatched direction", so every one of the
# nine is a row in `screening-zh-term-inside-another-word`, watched red first.
# The false positives already declared in docs/support-matrix.md D31 widen with
# it by construction: 购買力平價 now refuses exactly as 購買力平價 always did.
#
# M45-D3 rides the same fold for its uncontroversial half and stops short of the
# rest. 登錄 is the traditional spelling of the already-blocked 登录, so 登[入录錄]
# is that pair folded like any other. 登陸 and 登陆 are NOT added, though they are
# ordinary — and in the mainland dominant — spellings of the same verb, because
# they also mean *to make landfall*: 颱風什麼時候登陸？ and 登陸月球 are read tasks,
# and adding the term verbatim manufactures a fresh instance of the very defect
# M45 closed. That is not a guess; the three readings are pinned in the ALLOW
# direction in the same case, so a later verbatim widening turns them red instead
# of shipping three false refusals. ADR-040 now separates them by acted object:
# website/account/system logins refuse, while landfall and spaceflight reads
# remain allowed.
SCOPE_BLOCK = re.compile(
    r"\b(?:log|sign)(?:g?ed|g?ing)?[\s-]?in(?:to)?\b"
    r"|\b(?:password|captcha|payment|purchase|buy|pay|download)\b"
    r"|\bcheck-?out\b"
    r"|\bcredit card\b"
    r"|\bplace (?:an?|the) order\b"
    r"|\bdelet(?:e|es|ed|ing)\s+(?:my|the|this|these|those|all|every|any|our)\b"
    r"|登[入录錄]|密[碼码]|[驗验][證证][碼码]|付款|[購购][買买]|[刪删]除|下[載载]",
    re.IGNORECASE,
)

# ADR-040: a term exception or page marker alone was unsafe; only the measured
# question forms gate it. Keep the vocabulary narrow and fail closed elsewhere.
_READ_FRAME = re.compile(
    r"^\s*(?:what\s+(?:does|do|is|are)|how\s+(?:long|does|do|is|are))\b"
    r"|(?:是什麼|是多少|多久|怎麼|怎么|如何)(?:[^。！？!?]*[？?])?$",
    re.IGNORECASE,
)
_INFORMATIONAL_MENTION = re.compile(
    r"密[碼码][學学]|[購购][買买]力|[刪删]除的(?:檔案|档案|文件)"
    r"|下[載载]次數|登[录錄](?:資料|资料|[檔档])|download statistics",
    re.IGNORECASE,
)
_AMBIGUOUS_LOGIN = re.compile(
    r"登[陸陆]\s*(?:到\s*)?(?:這|这)?(?:個|个)?(?:網站|网站|帳號|账号|系統|系统)")


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
    blocked = list(SCOPE_BLOCK.finditer(task))
    ambiguous = list(_AMBIGUOUS_LOGIN.finditer(task))
    risky = sorted((*blocked, *ambiguous), key=lambda match: match.start())
    mentions = list(_INFORMATIONAL_MENTION.finditer(task))
    if risky and _READ_FRAME.search(task) and all(
        any(mention.start() <= match.start() and match.end() <= mention.end()
            for mention in mentions)
        for match in risky
    ):
        return None
    m = risky[0] if risky else None
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
# Chromium exposes that root as `WebArea — <the page title>`. Page-level
# `observe` now omits it because no resolver tier can address it, but the lint
# remains necessary: a model can invent a WebArea target without seeing one.
# T-M40-2 measured four of five live tasks planning exactly that.
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
            "node Chromium names with the page title and whose text is the ENTIRE page. "
            "Page observations omit it because it cannot be resolved. It cannot be the answer, and it "
            "carries no other string to retarget by, so the page title is all a relocation could "
            "ask for next. Name the element that holds the value; if you can see a container but "
            "not its contents, `observe` that container first")


def root_retarget_gap(rejected_steps: list, new_steps: list) -> str | None:
    """Refuse a replan that only respells a rejected root as loose text."""
    names = {
        str(target.get("name") or "").strip().casefold()
        for step in rejected_steps or []
        if isinstance(step, dict)
        and str(step.get("action") or "").startswith("extract")
        and isinstance((target := step.get("target")), dict)
        and str(target.get("role") or "").strip().lower() in DOC_ROOT_ROLES
        and str(target.get("name") or "").strip()
    }
    for step in new_steps or []:
        if not isinstance(step, dict) or not str(step.get("action") or "").startswith("extract"):
            continue
        target = step.get("target")
        if not isinstance(target, dict) or str(target.get("role") or "").strip() \
                or str(target.get("near") or "").strip() \
                or target.get("index") is not None or step.get("anchor"):
            continue
        if any(str(target.get(key) or "").strip().casefold() in names
               for key in ("text", "name")):
            return ("the replan only retargets the refused document root's page-title name "
                    "as loose text; name an addressable element or add evidence that "
                    "disambiguates a different target")
    return None


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


async def _same_document(scope, marker: str | None) -> bool:
    """Whether a live Frame still hosts the document marked before the action."""
    if not marker:
        return True
    try:
        return bool(await scope.evaluate("key => globalThis[key] === true", marker))
    except Exception:
        return False


async def check_state(page, expected: dict | None, scope=None,
                      document_marker: str | None = None) -> bool | None:
    """True / False / None, where None means "not verified here".

    Two ways to reach None and they mean the same thing downstream — nothing
    was checked, so nothing is verified: nothing was asserted, or the document
    the assertion was about is GONE (`detached()` below, ADR-036 §4). None is
    not True. Collapsing them recorded unverified steps as verified and
    made the module docstring's claim false (case postcondition-unverified-click).
    Every key present must hold: an if/elif chain silently graded a compound
    expectation on its first key alone (case postcondition-compound-keys).

    `scope` (ADR-036) is the DOCUMENT the predicates are checked in — the Page
    or Frame the step's action touched, i.e. the one `resolve` returned its
    target from, or the page itself (meaning the MAIN document) for a step that
    resolved nothing. `None` means the whole page, every frame — the caller
    passes that only for `PAGE_WIDE_STATE` actions, and it is also the
    back-compat default. The distinction is what a postcondition is FOR: with
    every frame in scope, a decoy iframe — a consent banner, a chat widget, a
    display:none tracking frame, all still in `page.frames` — satisfied a
    click's `expected_state` and the step recorded `postcondition_ok: true`
    for an action that did nothing (T-M42-4, T-M42-11's repro on
    `frames-host.html`). `url_contains` reads `page.url` in every scope: one
    address bar is a page-level fact, which is ADR-036's third carve-out.
    """
    if not expected:
        return None

    def detached() -> bool:
        """Is the acted document GONE — destroyed while its own step ran?

        A document can be removed out from under the step that acted in it: an
        SPA re-mounting an embedded widget after an in-frame click, an in-frame
        link with `target="_top"`, or the host's own poll firing on a timer that
        owes nothing to the action. The detached Frame then answers nothing
        rather than answering falsely — `page_text`'s per-frame read swallows
        the exception and contributes "", and `get_by_role` raises into the
        settle loop's `except Exception: pass` — so the postcondition burned the
        full SETTLE_BUDGET_MS and returned False for an action that may well
        have worked (`postcondition-scope-detached-by-its-own-action`, watched
        red at `failure:act` in 2.55s). A false negative ADR-036 never declared.

        The answer is None — unverifiable — not a page-wide retry. Page-wide
        was the first ruling and PR #66 R6 falsified its justification: it
        assumed a detach is positive evidence the action did something, and a
        page that re-renders on a timer detaches the acted frame after a
        LITERAL no-op, whereupon an unrelated decoy iframe supplies the
        predicate and the step records `postcondition_ok: true` for a click
        that did nothing — §1's hazard exactly, through the fallback door
        (`detached-scope-cannot-be-verified-by-a-decoy`, watched red as `status
        success`, `trace_postconditions [true, true, null]`). Nothing here can
        tell the two apart: attributing a detach to an action needs a successor-
        document identity the trace does not carry (T-M42-14). So the step says
        it does not know, which `verifier.STATE_CHANGING` turns into a loud
        `failure:semantic` — "carried no checkable postcondition" — rather than
        into either a false pass or a false accusation that the action failed.

        Re-read on every settle pass, not once: the detach is often the
        asynchronous consequence being waited for, and a predicate that goes
        true BEFORE the document dies still returns True. `Page` has no
        `is_detached`, which is why this is a `getattr` and not a type test.
        """
        is_detached = getattr(scope, "is_detached", None)
        return bool(is_detached and is_detached())

    async def holds(key, want) -> bool:
        if key == "url_contains":
            return want in page.url
        doc = scope
        if key == "text_visible":
            # `page_text`, not `page.inner_text("body")`: a postcondition that
            # cannot see an open shadow root is a postcondition that fails on a
            # page the run handled correctly
            # (`shadow-dom-value-is-reachable-and-grounded`). `frames` only
            # when no document is scoped: a Frame has no `.frames` attribute,
            # so a frame scope reads its own document either way, and a page
            # scope means the main document (ADR-036).
            return want in (await page_text(doc or page, frames=doc is None))
        if key == "role_visible":
            # The same scoping, one layer down. A locator never crosses a
            # frame boundary, so page-wide means asking every frame in turn;
            # document-scoped means asking exactly one (ADR-036).
            for s in ([page, *(getattr(page, "frames", None) or [page])[1:]]
                      if doc is None else [doc]):
                # T-M42-20-D6: WHOLE-STRING, the same matcher the resolver
                # uses. This built `get_by_role(role, name=<str>)` with neither
                # `exact` nor `_whole_string`, i.e. a case-insensitive
                # SUBSTRING — so on `<h1>Shopping Cart is empty</h1>` a
                # postcondition asserting `heading "Cart"` held. The whole
                # argument whole-string matching rests on one file over
                # ("substring matching resolved absent targets to superstring
                # siblings and extracted the wrong element as a success")
                # applies verbatim here, and harder: a postcondition is what
                # `verify` treats as proof the action landed, so a superstring
                # match is a no-op certified as a state change.
                #
                # `_whole_string`, not `exact=True`: exact is case-SENSITIVE,
                # which is a promise about the page's stylesheet nothing here
                # can keep — the same reason the resolver rejected it.
                loc = (s.get_by_role(want["role"], name=_whole_string(want["name"]))
                       if want.get("name") else s.get_by_role(want["role"]))
                if await loc.count() >= 1 and await loc.first.is_visible():
                    return True
            return False
        raise StepError("task", f"unknown expected_state key {key!r}")

    document_keys = any(k != "url_contains" for k in expected)
    for _ in range(SETTLE_TRIES):
        # A Frame object and its URL survive an in-place navigation. The marker
        # does not: it belongs to the document resolve actually returned. A
        # successor document therefore cannot certify the preceding action.
        if document_keys and not await _same_document(scope, document_marker):
            return None
        try:
            if all([await holds(k, v) for k, v in expected.items()]):
                return True
        except StepError:
            raise
        except Exception:
            pass
        # ADR-036 §4. Checked AFTER the pass, so a predicate that held while the
        # document still existed is True; and only for keys that need a
        # document, since `url_contains` reads the address bar in every scope
        # (§1's third carve-out) and one address bar survives any frame.
        if detached() and any(k != "url_contains" for k in expected):
            return None
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
    # Attached BEFORE `goto`, because the requests that matter here are the ones
    # a page issues while it parses -- a `fetch` in an inline script is in
    # flight before `load` fires, which is the only reason this can be tested
    # at `load` time at all. Removed in the `finally` below: `navigate` is
    # called once per hop on a page that survives the whole run, and listeners
    # left behind would accumulate one set per navigation.
    inflight = set()

    # Plain functions, not `inflight.add` / `inflight.discard`: Playwright
    # stamps an attribute on every handler it wraps, and a builtin method
    # cannot carry one (`AttributeError: 'builtin_function_or_method'`).
    def started(request):
        # `fetch`/`xhr` only, and the narrowing is what makes the wait cheap
        # enough to keep. Counting EVERY request bought a 7.3s fast-suite
        # regression (93.5 -> 100.9) for nothing: `load` already waited on
        # images, styles and subframes, and what was left over it was mostly
        # Chromium's own `/favicon.ico` -- a 404 round trip, on every
        # navigation, that no observation has ever read. The question this
        # settle asks is "is the page still fetching DATA it will paint with",
        # and these two resource types are that question.
        if request.resource_type in ("fetch", "xhr"):
            inflight.add(request)

    def finished(request):
        inflight.discard(request)

    page.on("request", started)
    page.on("requestfinished", finished)
    page.on("requestfailed", finished)
    try:
        await _navigate(page, url, inflight)
    finally:
        # `suppress`, because this runs on the failure path too: a page that
        # crashed or was closed inside `_navigate` is exactly when teardown can
        # raise, and a teardown error here would replace the real navigation
        # failure with a misleading one -- the misattribution family this
        # function exists to close.
        for event, fn in (("request", started), ("requestfinished", finished),
                          ("requestfailed", finished)):
            with contextlib.suppress(Exception):
                page.remove_listener(event, fn)


async def _navigate(page, url: str, inflight: set) -> None:
    """`navigate`'s body, split out only so the listener teardown above is a
    `finally` rather than a repeated line on every return path."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("load", timeout=SETTLE_BUDGET_MS)
    except PlaywrightTimeoutError:
        pass  # the page never went quiet; read it anyway, that is the point
    # S1 (the 2026-08-24 postmortem's fetch-then-render shape): `load` fires
    # when the DOCUMENT is complete, and a page that paints from `fetch` is not
    # done at that point. The observation on the very next line is what the
    # planner plans against, so a control that is empty at `load` -- a
    # `<select>` filled from an endpoint, a status region still reading
    # "Extracting..." -- is a control the planner cannot see, and it plans
    # around a page that no longer exists by the time the plan executes. It was
    # declared unfixed by `live-sec10k-authored-wait-reaches-the-doc-status`
    # (claim 1) and then killed a real run: a task naming a filing the picker
    # DID offer was planned as an EDGAR-URL fetch, because the 42 options had
    # not been painted when the planner looked.
    #
    # `networkidle` is the obvious mechanism and it is the wrong one, twice
    # measured: it waits 500ms past the last request on EVERY navigation, cost
    # +34s on the fast suite when ADR-002 rejected it, and +51.4s (93.5 -> 144.9,
    # over a 110s ceiling) when this fix was first written that way -- even
    # gated on the page carrying a `<script>` at all. It buys a guarantee by
    # charging every page for the sins of the few.
    #
    # What is actually being asked is narrower: is the page still WAITING on
    # something? `_inflight` answers exactly that and nothing else, so a static
    # document -- every script-free fixture, and every script-bearing one whose
    # script has already finished -- pays one set-emptiness test and moves on.
    # Ceiling, named rather than hidden: a page that issues its fetch from a
    # `setTimeout` AFTER `load` has an empty in-flight set at this instant and
    # is read early exactly as before. The fix is deliberately not a quiescence
    # window; upgrade to one only if a case ever demonstrates that shape.
    # 5ms rather than 20ms, and the reason is NOT the one this comment first
    # gave. The guess was that the tick dominated -- 20ms x ~100 navigations of
    # pure rounding -- and it was measured and falsified: the fast suite moved
    # 96.02s -> 95.77s, 0.25s. What the suite pays is the fetches themselves,
    # which is the wait doing its job. 5ms is kept because it is free and
    # slightly tighter; nobody should read a saving into it.
    deadline = time.monotonic() + SETTLE_BUDGET_MS / 1000
    while inflight and time.monotonic() < deadline:
        await asyncio.sleep(0.005)
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


# The taxonomy, as a set this file can check against — the seven classes
# docs/evals/failure-taxonomy.md defines and INV-1 requires exactly one of.
# Used by `escalation_note` to keep a class name it prints inside a closed
# vocabulary; the escalation TRIGGER reads `status.startswith("failure:")` and
# needs no list at all.
FAILURE_CLASSES = ("nav", "locate", "act", "extract", "semantic", "env", "task")


def escalation_note(result: dict) -> str:
    """The ONLY thing that crosses from an escalation's plan leg into its loop
    leg (M46, ADR-037 Decision 3). Four facts, every one of them from a closed
    vocabulary or an integer:

      * the failure class, which must be in `FAILURE_CLASSES`;
      * the index of the step that died, which must be an `int`;
      * that step's action verb, which must be in `ACTIONS`;
      * that step's target KEY NAMES, filtered to `TARGET_KEYS` and sorted.

    Nothing else. Not `reason`, not the step's `note`, not the resolver's
    message, not the target's VALUES, not the page digest, not an extraction —
    every one of which can contain bytes the SITE authored, and all of which a
    plan leg's terminal evidence really does carry (the verifier quotes page
    text back when it demotes a read; the plan's target is a name the model
    copied off the page). This function is the boundary, and the boundary is
    structural: a filter is a claim about what an attacker cannot write, a
    closed vocabulary is a claim about what this code can emit, and only the
    second is checkable by reading four lines.

    It matches the injection boundary the note path ALREADY has rather than
    adding a second one: `planner`/`driver` take a `note` the caller composes
    and the prompt builders insert verbatim (`planner.build_user`,
    `build_driver_user`), and page bytes reach a model through the OBSERVATION
    and the trace digest — both of which stay inside one leg, because the loop
    leg is a fresh `run_task` with its own trace. This note is the one thing
    that crosses, so it is the one place the vocabulary has to be closed.

    Pure and module-level so it can be graded with no browser and no model
    (`escalation-note-is-closed-vocabulary`), the same reason `build_user` is.
    """
    trace = (result.get("evidence") or {}).get("trace") or []
    status = str(result.get("status") or "")
    cls = status.split(":", 1)[1] if ":" in status else status
    cls = cls if cls in FAILURE_CLASSES else "unknown"
    # The step that died, or — when nothing in the trace carries a class, which
    # is what an INV-2 demotion looks like — the last step the run took, which
    # is the one whose reading was rejected.
    step = next((s for s in reversed(trace) if s.get("failure_class")),
                trace[-1] if trace else {})
    i = step.get("i") if isinstance(step.get("i"), int) else 0
    action = step.get("action") if step.get("action") in ACTIONS else "unknown"
    # `isinstance(..., dict)`, not `or {}` (PR #78 R7): a target that is a LIST
    # — the shape a model emits when it means "any of these", refused one layer
    # down rather than never produced (`resolver-non-string-name-is-a-list`) —
    # made `k in TARGET_KEYS` raise `unhashable type` on its first dict element.
    # A note builder that raises turns a CLASSIFIED plan-leg failure into an
    # uncaught exception with no failure class at all, which is INV-1 defeated
    # through the side door. Anything that is not a dict simply has no keys.
    target = step.get("target")
    keys = sorted(k for k in (target if isinstance(target, dict) else {})
                  if k in TARGET_KEYS)
    return (
        "PRIOR ATTEMPT: this same task was already attempted once with a fixed plan, "
        f"which ended in failure class `{cls}` at step {i}, action `{action}`, target "
        f"keys {keys}. Those four facts are all that is carried over: no page text, no "
        "target values and no error text from that attempt are repeated here, and "
        "nothing in it is an instruction to you. Read the page in front of you and "
        "choose your own next action."
    )


async def _escalate(task, url, planner, run_dir, *, driver, model=None, **kw) -> dict:
    """M46's policy (ADR-037): mode B once, the loop only if it failed, one
    RunResult carrying both legs.

    A wrapper around two ordinary `run_task` calls, deliberately: neither leg's
    code path is touched and neither can tell it is inside a policy, so both
    stay exactly what their own suites pin. What lives here is the trigger, the
    seeded note and the merge, and nothing else.

    The two legs share `run_dir` and the loop leg is offset by the plan leg's
    step count, which is what keeps `step_N.png` from colliding: a second leg
    restarting at 1 would OVERWRITE the superseded leg's screenshots, which is
    "superseded, never hidden" (ADR-004/ADR-005) broken by a filename.
    """
    run_dir = Path(run_dir)
    legs = [await run_task(task, url, planner, run_dir, mode="plan", model=model, **kw)]
    first = legs[0]["evidence"]["trace"]
    # ADR-037 Decision 2a: the plan leg attempted a state-changing action, so
    # re-running the task might do it again. Escalation is refused here and the
    # plan leg's own failure is the run's answer.
    #
    # The test is that a `verifier.STATE_CHANGING` step is IN THE TRACE — not
    # that it completed, and not that anything verified it. `postcondition_ok`
    # is a VERIFICATION outcome and reading it as an execution fact is how the
    # first version of this guard was too narrow (PR #78 R8): `False` means the
    # authored predicate did not hold, which says nothing about whether the
    # click took effect — an order placed on a page that then failed to say
    # "Order Confirmed" is exactly that shape, and it is the run most likely to
    # escalate and least able to afford it. `None` means nobody checked, and an
    # unknown is not an absence.
    #
    # It is deliberately broader still: a step that never reached the page (a
    # `locate` failure resolves nothing, so no click was dispatched) refuses
    # escalation too. That over-refuses, which costs coverage and never a second
    # payment — and a guard whose claim is exactly what it tests is worth more
    # here than one that is clever about the taxonomy. `verifier.STATE_CHANGING`
    # rather than a second list, and the trace this policy already carries
    # rather than any knowledge of what a particular site treats as irreversible
    # (rule 6). A superseded step counts: a click a ladder replaced still
    # HAPPENED, and `superseded_by` is about grading, never about occurrence.
    committed = next((s for s in first if s["action"] in STATE_CHANGING), None)
    # Every `failure:<class>` escalates and nothing else does. `unsupported` is
    # a refusal `screen()` makes identically at the top of both legs, so
    # escalating it buys a second identical refusal at the price of a browser.
    if legs[0]["status"].startswith("failure:") and committed is None:
        legs.append(await run_task(task, url, None, run_dir, mode="loop", driver=driver,
                                   model=model, step_offset=len(first),
                                   opening_note=escalation_note(legs[0]), **kw))
        if second := legs[1]["evidence"]["trace"]:
            # The whole attempt was replaced by the next one — which is what a
            # supersede says, and what keeps the merged trace gradeable by the
            # same `verify()` the loop leg already ran: an abandoned failure or
            # a false postcondition in the plan leg would otherwise demote a run
            # the loop leg answered, on evidence its verdict never saw. Written
            # only once the replacement exists, so it can never dangle.
            for s in first:
                if not s["superseded_by"]:
                    s["superseded_by"] = second[0]["i"]
    final = legs[-1]
    status = final["status"]
    # The plan leg's own reason IS the run's reason when escalation is refused —
    # no new status class, because nothing new failed; what the refusal adds is
    # WHY there is no second leg, in the same closed vocabulary the seeded note
    # uses (a step index and a verb from `ACTIONS`, never a target value or page
    # text). A run that silently returned the plan leg's failure with `legs`
    # length 1 would be indistinguishable from one whose loop leg never got off
    # the ground.
    reason = final["reason"]
    if committed is not None and len(legs) == 1 and status.startswith("failure:"):
        # "was attempted", not "completed": the guard fires on the step being in
        # the trace at all, and the reason may not claim more than the guard
        # tests (PR #78 R8 — the same shape as the `screen()` bound it replaced,
        # one level in).
        reason = (f"{reason} · escalation refused: step {committed['i']} "
                  f"({committed['action']}) was attempted, so re-running this task "
                  "could repeat it")
    result = assemble_result(
        [s for leg in legs for s in leg["evidence"]["trace"]], final["answer"],
        {k: sum(leg["budgets_spent"][k] for leg in legs) for k in final["budgets_spent"]},
        None if status == "success" else status.split(":", 1)[-1], reason,
        final["evidence"]["final_url"], final["evidence"]["final_page_digest"],
        # The FINAL leg's readings, not both legs': this field is what the
        # verdict was computed from, and concatenating a superseded leg's
        # readings into it would publish a verdict as having been computed over
        # evidence the verifier never saw. They are in `legs[]` below, in full.
        final["evidence"]["extractions"], final["verdict"], model, "escalate")
    result["legs"] = [{"mode": leg["mode"], "status": leg["status"], "reason": leg["reason"],
                       "answer": leg["answer"], "steps": len(leg["evidence"]["trace"]),
                       "budgets_spent": leg["budgets_spent"],
                       "extractions": leg["evidence"]["extractions"]} for leg in legs]
    # The legs each wrote their own copy on the way past; the run's artifacts
    # are the merged ones.
    (run_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(s) for s in result["evidence"]["trace"]) + "\n")
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


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
    # T-M32-15: `and verdict` short-circuits, so a FALSY verdict (`None`, `{}`)
    # skipped this branch entirely and a caller passing an answer with no
    # verdict got `status: success` carrying something nothing certified — the
    # silent-success shape this repo has hit seven times. Not reachable from
    # `run_task` today (its one `done()` without `failure=` always passes a
    # `verify()` result, which is never None and never {}), and that is exactly
    # why it is worth closing: INV-2 is a property of this function, not of the
    # discipline of its twenty call sites, and "latent" is what every one of
    # those seven was before it was not.
    if status == "success" and (not verdict or verdict.get("verdict") != "PASS"):
        status = "failure:semantic"
        reason = reason or (f"verifier {verdict['verdict']}: {verdict.get('reason')}"
                            if verdict else "no verdict: nothing certified this answer")
        answer = None
    # The symmetric half of the same finding: `answer` was nulled only INSIDE
    # the demotion branch, so any `failure:*` assembled with an `answer=` would
    # carry it. No call site does that today; the rule belongs here rather than
    # in twenty places that must each remember it.
    if status != "success":
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


ORIGIN_STORAGE_VAR = "BROWSER_AGENT_ORIGIN_STORAGE"


def origin_storage_state(raw=None):
    """Playwright `storage_state` seeded from configuration, or None when unset.

    **Why this exists.** A site can put something behind a credential the PAGE
    holds rather than the request — the sec-10k inspector's escalation key lives
    in `localStorage`, and its deep-link start URL acts on load, before an agent
    could type into any field. Seeding is the only way a run reaches that path.

    **Why it is configuration and not code.** CLAUDE.md rule 6 allows exactly
    three per-site items in this package — start URL, rate limit, ground-truth
    endpoint — and a credential is none of them, so no host, storage key or
    selector may be written here. They arrive in `BROWSER_AGENT_ORIGIN_STORAGE`
    as `{"<origin>": {"<key>": "<value>"}}`. Rule 8 makes the secret an
    environment variable and nothing else.

    **Why `storage_state` and not `add_init_script`.** This agent browses
    arbitrary sites. An init script is injected into EVERY page's JS context, so
    the secret's text would travel to every origin a run visits — including a
    hostile one — and an origin guard inside the script does not help, because
    the guard only decides whether to WRITE; the value is already there to read.
    `storage_state` is written by the browser into each origin's own storage
    partition before any page script runs, and no page ever sees another's.

    Malformed configuration raises (rule 4). A run that silently drops to the
    unauthenticated path while reporting success is exactly the failure the
    inspector's own escalation-key decision was written about.
    """
    raw = os.environ.get(ORIGIN_STORAGE_VAR, "") if raw is None else raw
    raw = (raw or "").strip()
    if not raw:
        return None
    spec = json.loads(raw)          # loud on malformed JSON, deliberately
    if not isinstance(spec, dict):
        raise ValueError(f"{ORIGIN_STORAGE_VAR} must be a JSON object of "
                         f"{{origin: {{key: value}}}}, got {type(spec).__name__}")
    origins = []
    for origin, kv in spec.items():
        if not isinstance(kv, dict):
            raise ValueError(f"{ORIGIN_STORAGE_VAR}[{origin!r}] must be an "
                             f"object of {{key: value}}, got {type(kv).__name__}")
        if "://" not in origin or origin.rstrip("/") != origin or origin.count("/") != 2:
            # A bare host, or one carrying a path, silently matches NOTHING in
            # Playwright — the seed would be a no-op and the run would look
            # fine. Refuse instead: `scheme://host`, no path, no trailing slash.
            raise ValueError(f"{ORIGIN_STORAGE_VAR} key {origin!r} is not an "
                             f"origin — want scheme://host with no path or "
                             f"trailing slash, e.g. 'https://example.com'")
        origins.append({"origin": origin,
                        "localStorage": [{"name": str(k), "value": str(v)}
                                         for k, v in kv.items()]})
    return {"cookies": [], "origins": origins}


@dataclass
class _TaskRuntime:
    task: str
    model: str | None
    mode: str
    run_dir: Path
    t0: float
    trace: list[dict]
    budgets: dict
    answers: list
    extractions: list[dict]
    judge: object
    verified_access: bool = False
    page: object = None
    url_guard: object = None
    vision: list[bool] | None = None
    acted_scope: list | None = None
    acted_document: list[str | None] | None = None
    drilled: list | None = None
    page_bodies: dict[str, str] | None = None
    step_offset: int = 0
    pending_supersede: list | None = None
    emit: object = None

    def done(self, answer=None, failure=None, reason=None, final_url=None, digest=None, verdict=None):
        self.budgets["ms"] = int((time.monotonic() - self.t0) * 1000)
        result = assemble_result(self.trace, answer, self.budgets, failure, reason, final_url,
                                 digest, self.extractions, verdict, self.model, self.mode)
        (self.run_dir / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in self.trace) + "\n")
        (self.run_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    async def finalize(self, final_url, digest):
        answer = self.answers[0] if len(self.answers) == 1 else (self.answers or None)
        enumerated = next((s.get("rank") for s in self.trace
                           if s.get("action") == "extract_all" and not s.get("superseded_by")
                           and not s.get("failure_class")), None)
        if len(self.answers) == 1 and isinstance(answer, list) and enumerated is not None:
            try:
                answer = rank(self.task, answer, enumerated)
            except ValueError as e:
                return self.done(failure="semantic", reason=str(e), final_url=final_url, digest=digest)
        verdict = verify(trace=self.trace, extractions=self.extractions, answer=answer, task=self.task)
        if verdict["verdict"] == "PASS":
            verdict = await _apply_judge(self.judge, self.task, answer, self.extractions,
                                         verdict, self.budgets)
        return self.done(answer=answer, final_url=final_url, digest=digest, verdict=verdict)

    async def execute_control(self, step, rec) -> bool:
        action = step["action"]
        if action == "navigate":
            if self.url_guard and not self.url_guard(step.get("value") or ""):
                raise StepError("task", f"blocked URL: {step.get('value')!r}")
            await navigate(self.page, step["value"])
        elif action not in ACTIONS:
            raise StepError("task", f"unknown action {action!r}")
        elif action == "final_answer":
            pass
        elif action == "wait_for":
            if not step.get("expected_state"):
                raise StepError("task", "a wait_for must carry the expected_state it is "
                                        "waiting for; a wait with no predicate is a sleep")
        elif action == "go_back":
            if await self.page.go_back(wait_until="domcontentloaded") is None:
                raise StepError("act", "go_back: this tab has no earlier page to return to")
        elif action == "click_at":
            if not self.vision or not self.vision[0]:
                raise StepError("task", "click_at needs coordinates read off the screenshot you "
                                        "were just shown, and this call was not emitted from a "
                                        "viewport-screenshot-bearing observation (a drill's "
                                        "element-scoped image has a different coordinate frame), "
                                        "so these coordinates cannot come from anything this run "
                                        "saw. Name an element semantically, or look at the full "
                                        "page again first")
            try:
                x, y = (float(v) for v in str(step.get("value") or "").split(","))
            except ValueError:
                raise StepError("task", "click_at needs `value` as \"x,y\" viewport "
                                        f"CSS pixels; got {step.get('value')!r}")
            await self.page.mouse.click(x, y)
        else:
            return False
        return True

    async def resolve_step(self, step, rec):
        """Validate one non-control action and resolve its semantic target."""
        action = step["action"]
        if unknown := set(step.get("target") or {}) - TARGET_KEYS:
            raise StepError("task", f"unsupported target key(s) {sorted(unknown)}")
        if action == "extract_all" and any(
                (step.get("target") or {}).get(k) is not None for k in ("index", "near")):
            raise StepError("task", "extract_all enumerates every match; `index`/`near` "
                                    "select one, so the plan says two different things")
        if action == "extract_all" and not isinstance(step.get("rank"), bool):
            raise StepError("task", "extract_all must declare `rank`: true if the answer "
                                    "is the one item the task ranks for, false if the "
                                    "answer is the enumeration itself")
        if gap := root_target_gap(step):
            raise StepError("task", gap)
        loc = None
        if step.get("target") or action in NEEDS_TARGET:
            loc, tier, narrowed, scope = await resolve(
                self.page, step.get("target") or {}, many=action == "extract_all",
                anchor=step.get("anchor"), task=self.task, action=action)
            self.acted_scope[0] = scope
            if (scope is not self.page and step.get("expected_state")
                    and any(k != "url_contains" for k in step["expected_state"])):
                self.acted_document[0] = f"__browser_agent_document_{time.monotonic_ns()}"
                try:
                    await scope.evaluate(
                        "key => { globalThis[key] = true; }", self.acted_document[0])
                except Exception:
                    # Verification will read the missing marker as unverifiable;
                    # failing open here recreates the successor-document hole.
                    pass
            rec["resolved"] = {"tier": tier, "description": str(step.get("target")),
                               "scope": scope.url, "narrowed": narrowed}
            if narrowed:
                rec["note"] = "; ".join(
                    x for x in (rec["note"], f"narrowed: {narrowed}") if x)
        return action, loc

    async def execute_observe(self, step, rec, loc) -> bool:
        """Run an observe/drill action without changing page state."""
        if step["action"] != "observe":
            return False
        if step.get("expected_state"):
            raise StepError("task", "an observe step cannot carry expected_state: "
                                    f"{step['expected_state']}")
        from .observe import DRILL_TEXT_HEAD, observe

        # The scoped observation is replanner input, not an answer or action.
        self.drilled.append(await observe(self.page, root=loc, text_head=DRILL_TEXT_HEAD))
        # A drill's optional crop is model input only in loop mode. It is clipped
        # from a viewport screenshot, never `loc.screenshot()`: Playwright's
        # element-shot actionability scroll would mutate lazy-load pages.
        if self.mode == "loop":
            shot = f"step_{rec['i']}_element.png"
            try:
                box = await loc.bounding_box(timeout=SCREENSHOT_TIMEOUT_MS)
                vp = self.page.viewport_size or {}
                x0, y0 = max(box["x"], 0.0), max(box["y"], 0.0)
                x1 = min(box["x"] + box["width"], vp.get("width", 0))
                y1 = min(box["y"] + box["height"], vp.get("height", 0))
                if x1 > x0 and y1 > y0:
                    await self.page.screenshot(
                        path=str(self.run_dir / shot), timeout=SCREENSHOT_TIMEOUT_MS,
                        clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
                    self.drilled[-1].update(screenshot=shot,
                                            screenshot_path=str(self.run_dir / shot),
                                            screenshot_frame="element")
            except Exception:
                # Best effort must stay bounded: every awaited screenshot/crop
                # operation above carries SCREENSHOT_TIMEOUT_MS.
                pass
        return True

    async def execute_action(self, step, rec, action, loc) -> bool:
        """Execute one resolved, non-extraction browser action."""
        if action == "click":
            expected = step.get("expected_state") or {}
            wait_text = expected.get("text_visible") if set(expected) == {"text_visible"} else None
            button_type = (await loc.get_attribute("type")
                           if (step.get("target") or {}).get("role") == "button" else None)
            track_async_submit = ((step.get("target") or {}).get("role") == "button"
                                  and button_type != "submit" and bool(wait_text))
            statuses = self.page.get_by_role("status") if track_async_submit else None
            status_before = await statuses.all_inner_texts() if statuses is not None else []
            await loc.click(timeout=10_000)
            disabled, status_after = False, status_before
            if track_async_submit:
                try:
                    disabled = await loc.is_disabled()
                    status_after = await statuses.all_inner_texts()
                except Exception:
                    pass
            # The generic async-submit signal is three facts together: the
            # clicked control disabled, a live status changed, and the authored
            # terminal text is not visible yet. Ordinary disabled buttons and
            # already-satisfied postconditions do not enter the long window.
            if disabled and status_after != status_before and wait_text:
                deadline = time.monotonic() + DISABLED_SUBMIT_WAIT_MS / 1000
                while time.monotonic() < deadline:
                    try:
                        if wait_text in await page_text(self.page) or await loc.is_enabled():
                            break
                    except Exception:
                        break  # replacement/detachment is also observable completion
                    await self.page.wait_for_timeout(50)
        elif action == "fill":
            if not await loc.evaluate(FILLABLE_JS):
                raise StepError("locate", f"resolved element is not fillable: {step.get('target')}")
            await loc.fill(step.get("value") or "", timeout=10_000)
            back = await loc.input_value()
            if back != (step.get("value") or ""):
                raise StepError("act", f"field readback {back!r} != filled value")
            rec["postcondition_ok"] = True
        elif action == "select_option":
            want = step.get("value")
            if not isinstance(want, str) or not want:
                raise StepError("task", "select_option needs a `value` naming the option "
                                        f"to choose; got {step.get('value')!r}")
            opts = await loc.evaluate(OPTIONS_JS)
            if opts is None:
                raise StepError("act", "resolved element has no options to select: "
                                       f"{step.get('target')}")
            if not opts:
                try:
                    await loc.locator("option").first.wait_for(
                        state="attached", timeout=SELECT_OPTIONS_WAIT_MS)
                except Exception:
                    pass
                opts = await loc.evaluate(OPTIONS_JS)
            exact = [o for o in opts if want in (o[0], o[1])]
            if len(exact) > 1:
                raise StepError("act", f"{want!r} matches {len(exact)} options "
                                       f"({[(v, l) for v, l in exact]}); name one exactly")
            match = exact[0] if exact else None
            if match is None:
                loose = [o for o in opts if want in o[0] or want in o[1]]
                match = loose[0] if len(loose) == 1 else None
            if match is None:
                raise StepError("act", f"no option matches {want!r}; this control offers "
                                       f"{[label for _v, label in opts]}")
            await loc.select_option(value=match[0], timeout=10_000)
            if await loc.input_value() != match[0]:
                raise StepError("act", f"select readback is not {want!r}")
            rec["postcondition_ok"] = True
        elif action == "press":
            if not step.get("value"):
                raise StepError("task", "a press must name the key in `value`")
            if loc is not None:
                await loc.press(step["value"], timeout=10_000)
            else:
                await self.page.keyboard.press(step["value"])
        elif action == "scroll":
            before_y = await self.page.evaluate("() => window.scrollY")
            if loc is not None:
                await loc.scroll_into_view_if_needed(timeout=10_000)
                if not await loc.is_visible():
                    raise StepError("act", "scrolled to the target and it is still not "
                                           f"visible: {step.get('target')}")
            else:
                await self.page.evaluate("d => window.scrollBy(0, d)",
                                         int(step.get("value") or 800))
                if await self.page.evaluate("() => window.scrollY") == before_y:
                    raise StepError("act", "scroll moved nothing: the page is already at "
                                           "that position, so there is nothing further "
                                           "down to read")
            rec["postcondition_ok"] = True
        else:
            return False
        return True

    async def execute_extract(self, step, action, loc) -> bool:
        """Capture deterministic evidence for one extract or extract_all action."""
        if action not in ("extract", "extract_all"):
            return False
        from .observe import image_accessible_name

        vals = ([v.strip() for v in await loc.all_inner_texts()]
                if action == "extract_all" else [(await loc.inner_text()).strip()])
        accessible_value = ""
        target_role = str((step.get("target") or {}).get("role") or "").lower()
        if action == "extract" and target_role == "link" and not vals[0]:
            accessible_value = vals[0] = await image_accessible_name(loc)
        vals = [v for v in vals if v]
        if not vals:
            raise StepError("extract", "extraction returned empty text")
        bases: dict = {}
        body = await page_text(self.page, bases=bases)
        # Accessible names are rendered evidence only when an empty link needed
        # the fallback; they are never a wider search for a nearby value.
        evidence_body = body + ("\n" + accessible_value if accessible_value else "")
        frame_base = bases.get(self.acted_scope[0], 0)
        scope_now = self.acted_scope[0]
        try:
            doc_len = len(await page_text(scope_now, frames=False)
                          if scope_now is self.page or scope_now is None
                          else await page_text(scope_now))
        except Exception:
            doc_len = len(body)
        anchor = step.get("anchor")
        # Refuse before writes: a rejected read must never survive a recovery.
        if anchor and anchor not in evidence_body:
            raise StepError("semantic", f"identity anchor {anchor!r} absent from the page "
                                        "the answer was read from")
        real_offset = _closest_occurrence(
            evidence_body, vals[0], await loc.first.evaluate(TEXT_OFFSET_JS) + frame_base)
        other_page_text = " ".join(t for u, t in self.page_bodies.items() if u != self.page.url)
        for i, value in enumerate(vals):
            try:
                hint = await loc.nth(i).evaluate(TEXT_OFFSET_JS)
            except Exception:
                hint = -1
            offset = _closest_occurrence(
                evidence_body, value, hint if hint < 0 else hint + frame_base)
            self.extractions.append(
                {"value": value,
                 "page_text": evidence_window(evidence_body, value, anchor, offset=offset),
                 "body_len": doc_len, "other_page_text": other_page_text,
                 "value_offset": (offset - _window_lo(evidence_body, offset))
                 if offset >= 0 else None})
        self.page_bodies[self.page.url] = body
        self.answers.append(vals if action == "extract_all" else vals[0])
        return True

    async def execute(self, step, rec):
        """Dispatch exactly one browser action through its named boundary."""
        if await self.execute_control(step, rec):
            return
        action, loc = await self.resolve_step(step, rec)
        if await self.execute_observe(step, rec, loc):
            return
        if await self.execute_action(step, rec, action, loc):
            return
        if await self.execute_extract(step, action, loc):
            return
        raise StepError("task", f"unhandled action {action!r}")

    async def attempt(self, step, note=None, recovery=None):
        """Record, execute, classify, and emit one action attempt."""
        rec = {
            "i": self.step_offset + len(self.trace) + 1,
            "action": step["action"], "target": step.get("target"),
            "value": step.get("value"), "anchor": step.get("anchor"),
            "rank": step.get("rank"), "resolved": None,
            "expected_state": step.get("expected_state"), "postcondition_ok": None,
            "failure_class": None, "note": note, "retry_or_recovery": recovery,
            "superseded_by": None, "page_changed": None, "screenshot": None, "ms": 0,
        }
        self.trace.append(rec)
        if self.pending_supersede and step["action"] not in ("observe", "final_answer"):
            self.pending_supersede.pop()["superseded_by"] = rec["i"]
        self.budgets["actions"] += 1
        started = time.monotonic()
        failure_class = None
        before = (await page_text(self.page)
                  if not step["action"].startswith("extract")
                  and step["action"] not in READ_ONLY_ACTIONS else None)
        mark = (len(self.extractions), len(self.answers))
        self.acted_scope[0] = None
        self.acted_document[0] = None
        try:
            await self.execute(step, rec)
            if self.url_guard and not self.url_guard(self.page.url):
                raise StepError("task", f"navigated to blocked URL: {self.page.url!r}")
            if before is not None:
                after = await page_text(self.page)
                rec["page_changed"] = after != before
                self.page_bodies[self.page.url] = after
            checked = await check_state(
                self.page, step.get("expected_state"),
                scope=None if step["action"] in PAGE_WIDE_STATE
                else (self.acted_scope[0] or self.page),
                document_marker=self.acted_document[0])
            if (checked is None and self.acted_document[0]
                    and not await _same_document(self.acted_scope[0], self.acted_document[0])):
                rec["note"] = "; ".join(filter(None, [
                    rec["note"],
                    "postcondition unverifiable: resolved frame document was replaced"
                ]))
            if checked is not None or rec["postcondition_ok"] is None:
                rec["postcondition_ok"] = checked
            if rec["postcondition_ok"] is False:
                raise StepError("act", f"expected_state not reached: {step.get('expected_state')}")
        except Exception as exc:
            failure_class = classify(step["action"], exc)
            rec["failure_class"] = failure_class
            rec["note"] = "; ".join(filter(None, [rec["note"], f"{type(exc).__name__}: {exc}"]))
            del self.extractions[mark[0]:], self.answers[mark[1]:]
        shot = f"step_{rec['i']}.png"
        try:
            await self.page.screenshot(path=str(self.run_dir / shot), timeout=SCREENSHOT_TIMEOUT_MS)
            rec["screenshot"] = shot
        except Exception:
            pass
        rec["ms"] = int((time.monotonic() - started) * 1000)
        self.emit(rec)
        return rec, failure_class

    async def look(self):
        """Return a fresh observation, or None when a recovery cannot observe."""
        from .observe import observe

        try:
            return await observe(self.page)
        except Exception:
            return None

    async def capture_evidence(self) -> dict:
        """Build one contract-checked packet from the current acquired page snapshot."""
        from .canonical_contract import validate_evidence_packet
        from .evidence import snapshot_evidence

        source = (await self.page.content()).encode("utf-8")
        document_id = f"snapshot:{hashlib.sha256(source).hexdigest()}"
        packet = snapshot_evidence(source_bytes=source, url=self.page.url,
                                   document_id=document_id)
        if wrong := validate_evidence_packet(packet):
            raise ValueError(f"invalid snapshot evidence: {wrong}")
        return packet

    async def observe_start(self, url: str | None):
        """Navigate and observe the pre-plan page, returning (observation, terminal)."""
        if not url:
            return None, None
        if self.url_guard and not self.url_guard(url):
            return None, self.done(failure="task", reason=f"blocked URL: {url!r}")
        started = time.monotonic()
        rec = {
            "i": self.step_offset + 1,
            "action": "navigate", "target": None, "value": url, "anchor": None,
            "rank": None, "resolved": None, "expected_state": None, "postcondition_ok": None,
            "failure_class": None, "note": "pre-plan observation",
            "retry_or_recovery": None, "superseded_by": None, "page_changed": None,
            "screenshot": None, "ms": 0,
        }
        self.trace.append(rec)
        self.budgets["actions"] += 1
        try:
            from .observe import observe

            await navigate(self.page, url)
            observation = await observe(self.page)
            self.page_bodies[self.page.url] = await page_text(self.page)
            path = self.run_dir / (f"observation_{self.step_offset}.json" if self.step_offset
                                   else "observation.json")
            path.write_text(json.dumps(observation, indent=2))
            rec["postcondition_ok"] = True
        except Exception as exc:
            rec["failure_class"] = "nav"
            rec["note"] = f"{type(exc).__name__}: {exc}"
            rec["ms"] = int((time.monotonic() - started) * 1000)
            self.emit(rec)
            return None, self.done(failure="nav", reason=f"pre-plan navigation failed: {exc}")
        rec["ms"] = int((time.monotonic() - started) * 1000)
        self.emit(rec)
        return observation, None


def _canonical_budget(runtime: _TaskRuntime, calls: int) -> dict:
    return {"calls": calls, "tokens": runtime.budgets["llm_tokens"],
            "usd": runtime.budgets["llm_usd"],
            "ms": int((time.monotonic() - runtime.t0) * 1000)}


async def _run_canonical(runtime: _TaskRuntime, planner, url: str | None) -> dict:
    """Bind existing browser work to ADR-046's callback graph."""
    from .canonical_contract import STATUSES
    from .canonical_graph import run as run_graph
    from .model_policy import node_calls_for

    pending = {"authority": "deterministic", "verdict": "PENDING"}
    failed = {"authority": "deterministic", "verdict": "FAIL"}
    passed = {"authority": "deterministic", "verdict": "PASS"}

    def running(state, context):
        return {"status": "running", "verifier": pending, "context": context,
                "budgets": _canonical_budget(runtime, context.get("calls", 0))}

    def failure(context, cls, reason, record=None):
        context.update(failure_class=cls, failure_reason=reason, failure_record=record)
        return context

    async def observe(_state):
        observation, result = await runtime.observe_start(url)
        context = {"observation": observation, "result": result, "calls": 0,
                   "critic_attempted": False}
        return {"status": "running", "verifier": pending,
                "retry": {"used": 0, "limit": 1},
                "budgets": _canonical_budget(runtime, 0), "evidence": [],
                "context": context}

    async def route(state):
        return running(state, dict(state["context"]))

    async def evidence(state):
        context = dict(state["context"])
        if not context.get("result"):
            try:
                packet = await runtime.capture_evidence()
            except Exception as exc:
                failure(context, "extract", f"canonical evidence failed: {exc}")
            else:
                return {**running(state, context), "evidence": [packet]}
        return running(state, context)

    async def plan(state):
        context = dict(state["context"])
        retry = dict(state["retry"])
        if state["status"] == "retryable":
            retry["used"] += 1
            observation = await runtime.look()
            if observation is None:
                failure(context, "env", "canonical retry could not observe the current page")
            else:
                context["observation"] = observation
        if not context.get("result") and not context.get("failure_class"):
            if stop := budget_stop(runtime.budgets):
                failure(context, "env", stop)
            else:
                context["calls"] += 1
                try:
                    candidate_steps, usage = await planner(task=runtime.task, url=url,
                                                            observation=context.get("observation"),
                                                            note=context.get("retry_note"))
                except PlanError as exc:
                    runtime.budgets["llm_tokens"] += exc.usage["llm_tokens"]
                    runtime.budgets["llm_usd"] += exc.usage["llm_usd"]
                    failure(context, "env", f"planner rejected: {exc}")
                except Exception as exc:
                    failure(context, "env", f"planner failed: {exc}")
                else:
                    runtime.budgets["llm_tokens"] += usage["llm_tokens"]
                    runtime.budgets["llm_usd"] += usage["llm_usd"]
                    context["steps"] = candidate_steps
        return {**running(state, context), "retry": retry}

    async def act(state):
        context = dict(state["context"])
        if not context.get("result") and not context.get("failure_class"):
            context["attempt_mark"] = {"answers": len(runtime.answers),
                                       "extractions": len(runtime.extractions),
                                       "trace": len(runtime.trace)}
            for step in context.get("steps", []):
                if stop := budget_stop(runtime.budgets):
                    failure(context, "env", stop)
                    break
                if not isinstance(step, dict) or not isinstance(step.get("action"), str):
                    failure(context, "task", f"plan step is not executable: {step!r}")
                    break
                record, cls = await runtime.attempt(step, note=context.get("retry_note"),
                                                    recovery="retry" if state["retry"]["used"] else None)
                context.pop("retry_note", None)
                if cls:
                    failure(context, cls, f"step {record['i']} ({step['action']}): {record['note']}",
                            record)
                    break
        return running(state, context)

    async def evaluate(state):
        context = dict(state["context"])
        if not context.get("result") and not context.get("failure_class"):
            answer = runtime.answers[0] if len(runtime.answers) == 1 else (runtime.answers or None)
            enumerated = next((record.get("rank") for record in runtime.trace
                               if record.get("action") == "extract_all"
                               and not record.get("superseded_by")
                               and not record.get("failure_class")), None)
            if len(runtime.answers) == 1 and isinstance(answer, list) and enumerated is not None:
                try:
                    answer = rank(runtime.task, answer, enumerated)
                except ValueError as exc:
                    failure(context, "semantic", str(exc))
            if not context.get("failure_class"):
                context["answer"] = answer
                context["digest"] = (await page_text(runtime.page))[:500]
                context["verdict"] = verify(trace=runtime.trace, extractions=runtime.extractions,
                                             answer=answer, task=runtime.task)
                # No graph edge changes here: a critic is advisory metadata for
                # one explicit deterministic ambiguity marker only. It cannot
                # repair a FAIL or choose publish.
                from .model_policy import PolicyError, semantic_ambiguity
                boundary = getattr(planner, "node_policy_boundary", None)
                if (boundary and semantic_ambiguity(context["verdict"])
                        and not context.get("critic_attempted")):
                    # `context` survives the one read-only retry.  Do not pay
                    # twice to critique the same deterministically marked
                    # ambiguity, including when the retry's plan came from cache.
                    context["critic_attempted"] = True
                    context["calls"] += 1
                    try:
                        _content, critic = await boundary.call(
                            "critic", [{"role": "user", "content": json.dumps({
                                "task": runtime.task, "verdict": context["verdict"], "answer": answer},
                                ensure_ascii=False)}], "critic-json-v1",
                            verified_access=runtime.verified_access)
                    except PolicyError as exc:
                        # The boundary validates/accounted readable provider
                        # usage before refusing its response.  Retain that bill
                        # even though a critic remains advisory and failed.
                        runtime.budgets["llm_tokens"] += exc.usage["llm_tokens"]
                        runtime.budgets["llm_usd"] += exc.usage["llm_usd"]
                        context["critic"] = {"outcome": "failure", "reason": str(exc)}
                    else:
                        runtime.budgets["llm_tokens"] += critic["tokens"]
                        runtime.budgets["llm_usd"] += critic["usd"]
                        context["critic"] = critic
        return running(state, context)

    async def decide(state):
        context = dict(state["context"])
        if context.get("result"):
            status = context["result"].get("status")
            if status not in STATUSES:
                raise ValueError(f"invalid canonical terminal result status: {status!r}")
            return {"route": "failure", "status": status, "verifier": failed,
                    "context": context, "budgets": _canonical_budget(runtime, context["calls"])}
        cls, record = context.get("failure_class"), context.get("failure_record")
        changed = any(not item.get("superseded_by") and item.get("action") in STATE_CHANGING
                      for item in runtime.trace)
        retryable = (state["retry"]["used"] < state["retry"]["limit"]
                     and not changed
                     and ((cls and record and record["action"] not in STATE_CHANGING)
                          or (not cls and context.get("verdict", {}).get("verdict") != "PASS")))
        if retryable:
            if record is not None:
                runtime.pending_supersede.append(record)
            elif mark := context.get("attempt_mark"):
                # A verifier rejection has no failed record to clear itself.
                # Its read-only attempt is replaced wholesale by the next one,
                # including the answer/evidence that made the verdict fail.
                if runtime.trace[mark["trace"]:]:
                    runtime.pending_supersede.append(runtime.trace[-1])
                del runtime.answers[mark["answers"]:]
                del runtime.extractions[mark["extractions"]:]
            context["retry_note"] = (context.get("failure_reason")
                                     or context.get("verdict", {}).get("reason")
                                     or "deterministic verifier rejected the prior attempt")
            context.pop("failure_class", None)
            context.pop("failure_reason", None)
            context.pop("failure_record", None)
            return {"route": "plan", "status": "retryable", "verifier": failed,
                    "context": context, "budgets": _canonical_budget(runtime, context["calls"])}
        if cls:
            return {"route": "failure", "status": f"failure:{cls}", "verifier": failed,
                    "context": context, "budgets": _canonical_budget(runtime, context["calls"])}
        verdict = context["verdict"]
        if verdict["verdict"] == "PASS":
            return {"route": "publish", "status": "accepted", "verifier": passed,
                    "context": context, "budgets": _canonical_budget(runtime, context["calls"])}
        return {"route": "review_required", "status": "review_required", "verifier": failed,
                "context": context, "budgets": _canonical_budget(runtime, context["calls"])}

    callbacks = {"observe": observe, "route": route, "evidence": evidence, "plan": plan,
                 "act": act, "evaluate": evaluate, "decide": decide}
    state = await run_graph({"runtime": runtime}, callbacks)
    context = state["context"]
    if context.get("result"):
        result = context["result"]
    elif state["route"] == "publish":
        result = runtime.done(answer=context.get("answer"), final_url=runtime.page.url,
                              digest=context.get("digest"), verdict=context["verdict"])
    elif state["route"] == "review_required":
        result = runtime.done(failure="semantic", final_url=runtime.page.url,
                              reason="canonical review required: " + context["verdict"].get("reason", ""),
                              verdict=context["verdict"])
    else:
        result = runtime.done(failure=context["failure_class"], final_url=runtime.page.url,
                              reason=context["failure_reason"])
    result["control_flow"] = {
        "nodes": state["nodes"], "routes": state["routes"], "status": state["status"],
        "verifier": state["verifier"], "retry": state["retry"],
        "evidence_hashes": [{key: packet[key] for key in ("document_id", "source_sha256", "snapshot_sha256")}
                            for packet in state["evidence"]],
        "node_calls": node_calls_for(planner),
        "critic": context.get("critic"),
        "budgets": _canonical_budget(runtime, context["calls"]),
    }
    runtime.run_dir.joinpath("result.json").write_text(json.dumps(result, indent=2))
    return result


async def run_task(task: str, url: str | None, planner, run_dir: str | Path, *, judge,
                   headless: bool = True, url_guard=None, on_step=None, model=None, browser=None,
                   mode: str = "plan", driver=None, loop_budgets=None,
                   step_offset: int = 0, opening_note: str | None = None,
                   verified_access: bool = False):
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
    BrowserContext either way, so cookies and storage never cross.

    `mode="escalate"` (M46, ADR-037) is a POLICY over the other two rather than
    a third cadence: it needs BOTH a planner and a driver and hands off to
    `_escalate`, which runs this function twice and merges the results. The two
    parameters that exist for it are `step_offset` — the trace index the run's
    first step takes, so a second leg's `i` values and `step_N.png` names
    continue the first's instead of overwriting them — and `opening_note`,
    which seeds the loop's first driver call and is composed by
    `escalation_note` under Decision 3's closed vocabulary. Both default to the
    behaviour every existing case pins."""
    if mode == "escalate":
        if planner is None or driver is None:
            raise ValueError("mode 'escalate' needs BOTH planner and driver: it runs one leg "
                             "of each, and neither leg may fall back to spending money")
        return await _escalate(task, url, planner, run_dir, judge=judge, headless=headless,
                               url_guard=url_guard, on_step=on_step, model=model,
                               browser=browser, driver=driver, loop_budgets=loop_budgets)
    if mode not in ("plan", "loop", "canonical"):
        raise ValueError(f"unknown mode {mode!r}")
    if mode == "canonical" and (planner is None or driver is not None):
        raise ValueError("mode 'canonical' needs a planner and no driver")
    if mode != "canonical" and (driver is None) != (mode != "loop"):
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
    answers: list = []
    runtime = _TaskRuntime(task, model, mode, run_dir, t0, trace, budgets,
                           answers, extractions, judge, verified_access=verified_access)
    runtime.page_bodies = page_bodies
    runtime.step_offset = step_offset
    runtime.pending_supersede = pending_supersede

    # Hand each finished step to a live watcher (the gateway's SSE endpoint).
    # Every attempt is emitted, including the ones a ladder supersedes: the
    # stream is the trace, not a highlight reel (stream-shows-every-step).
    emit = on_step or (lambda _rec: None)
    runtime.emit = emit

    done = runtime.done

    if reason := screen(task):
        return done(failure="unsupported", reason=reason)

    from playwright.async_api import async_playwright

    # At most one scoped observation, produced by an `observe` step and consumed
    # by the replan it triggers. A list rather than a variable so `execute`
    # (nested) can write it without a `nonlocal` dance.
    drilled: list[dict] = []
    runtime.drilled = drilled

    # M43 (ADR-035): is the observation the CURRENT driver call was emitted from
    # bearing a VIEWPORT screenshot? The loop's `see()` arms it, a drill
    # observation disarms it, and mode B never touches it — so `execute`'s
    # `click_at` refusal reads one cell in both modes. Same no-`nonlocal` shape
    # as `drilled`.
    vision: list[bool] = [False]
    runtime.vision = vision
    # The Page or Frame the CURRENT attempt's target resolved in — `execute`
    # fills it, `attempt` resets it per step and hands it to `check_state` so
    # the postcondition is checked in the document the action touched
    # (ADR-036). A one-slot holder like `drilled`'s list, not a trace field:
    # the trace carries the scope's URL (`resolved.scope`), never the object.
    acted_scope: list = [None]
    # A one-use property name planted in an iframe's current global before the
    # action. Unlike Frame identity or about:srcdoc, it disappears when that
    # same frame navigates in place (T-M42-14). Main-document navigations keep
    # their existing URL/postcondition semantics; this closes the demonstrated
    # iframe successor-document hole without widening the blast radius.
    acted_document: list[str | None] = [None]
    runtime.acted_scope = acted_scope
    runtime.acted_document = acted_document

    async with contextlib.AsyncExitStack() as stack:
        if browser is None:
            pw = await stack.enter_async_context(async_playwright())
            browser = await pw.chromium.launch(headless=headless, args=["--no-sandbox"])
            stack.push_async_callback(browser.close)
        ctx = await browser.new_context(storage_state=origin_storage_state())
        page = await ctx.new_page()
        runtime.page = page
        runtime.url_guard = url_guard
        try:
            if mode == "canonical":
                return await _run_canonical(runtime, planner, url)
            obs, terminal = await runtime.observe_start(url)
            if terminal is not None:
                return terminal
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
                async def see(o):
                    """M43 (ADR-035 Decision 1): attach the viewport screenshot
                    to a loop observation, and arm/disarm `click_at` with it.

                    The image IS the trace's step evidence — the `step_N.png`
                    `attempt` already captured for the step this observation
                    follows, referenced by filename, never a second capture of
                    the same page state. The one step with no capture of its
                    own is the pre-plan navigate (its record hardcodes
                    `screenshot: None`); the loop's first turn takes one here
                    and fills that existing field, so entry [0] of the trace's
                    screenshot column stops being the only blind step of a
                    loop run. `screenshot_path` exists because the driver is
                    handed no run directory and has bytes to read; the
                    filename alone is what the evidence pipeline keeps.

                    Capture failure disarms rather than lies: no screenshot,
                    no `Screenshot:` line rendered to the model, no armed
                    `click_at` — the degraded turn is an ARIA-only turn, which
                    is M42's whole behaviour. When `look()` fails and the caller
                    reuses the previous observation, this function still runs
                    against `trace[-1]`, so the reused observation is
                    re-attached to the image of the step just executed: the
                    model gets a FRESH screenshot beside a STALE element list,
                    which is a mismatched pair rather than a stale one (PR #70
                    R2 — ADR-035 Decision 1 said the opposite for a round). The
                    genuinely stale image needs BOTH captures of that step to
                    fail, `attempt`'s and the retry below; only then does `o`
                    keep the screenshot keys the previous turn wrote on it and
                    stay armed on an old image.
                    """
                    if o is None:
                        vision[0] = False
                        return None
                    rec = trace[-1] if trace else None
                    if rec is not None and rec.get("screenshot") is None:
                        shot = f"step_{rec['i']}.png"
                        try:
                            await page.screenshot(path=str(run_dir / shot),
                                                  timeout=SCREENSHOT_TIMEOUT_MS)
                            rec["screenshot"] = shot
                        except Exception:
                            pass
                    if rec is not None and rec.get("screenshot"):
                        o["screenshot"] = rec["screenshot"]
                        o["screenshot_path"] = str(run_dir / rec["screenshot"])
                        o["screenshot_frame"] = "viewport"
                    vision[0] = o.get("screenshot_frame") == "viewport"
                    return o

                # `opening_note` is None for a loop run of its own (M42's
                # behaviour, byte for byte) and carries the plan leg's terminal
                # facts when this loop is an escalation's second leg (ADR-037
                # Decision 3). It goes through the SAME `note` slot every other
                # message to the driver uses; there is no second channel.
                observation, note, last_state = await see(obs), opening_note, None
                seen: dict = {}
                exact_key, exact_repeats = None, 0
                last_failure_class = None
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
                            # `step_offset +`: every `i` in an escalated run's
                            # merged trace is offset, so a reason naming the
                            # leg-local length would point at a real step that
                            # is not the one that died — a plan-leg step (cold
                            # review of M46).
                            f"no progress: step {step_offset + len(trace)} arrived at "
                            f"{page.url} in the same "
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

                    # A visit counter cannot see one unchanged page plus one
                    # unchanged choice. Keep this at the driver boundary: it is
                    # site-agnostic and stops before a third execution spends a
                    # general action slot. Canonical JSON makes target-key order
                    # irrelevant while a changed action, target or page resets.
                    key = json.dumps({"state": state, "action": call.get("action"),
                                      "target": call.get("target"), "value": call.get("value"),
                                      "expected_state": call.get("expected_state"),
                                      "failure_class": last_failure_class},
                                     sort_keys=True, ensure_ascii=True, default=str)
                    exact_repeats = exact_repeats + 1 if key == exact_key else 1
                    exact_key = key
                    if exact_repeats > 2:
                        return done(failure="env", final_url=page.url, reason=(
                            f"exact repeat refused before execution (3/2): {key[:240]}"))
                    repeat_note = None
                    if exact_repeats == 2:
                        repeat_note = "exact repeat 2/2; choose a different action or target"
                        note = ("EXACT REPEAT: this unchanged page received the same choice twice. "
                                "Choose a different action or target; the next identical choice is refused.")

                    rec, cls = await runtime.attempt(call, note=repeat_note)
                    last_failure_class = cls
                    # The first decision cannot know the outcome that classifies
                    # it. Rebind its just-executed signature once that closed
                    # vocabulary fact exists, so the next identical failed call
                    # is its second choice rather than a fresh streak.
                    if cls:
                        exact_key = json.dumps({"state": state, "action": call.get("action"),
                                                "target": call.get("target"), "value": call.get("value"),
                                                "expected_state": call.get("expected_state"),
                                                "failure_class": cls},
                                               sort_keys=True, ensure_ascii=True, default=str)
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
                        note = ((note + " ") if repeat_note else "") + (f"Your last call FAILED: {rec['note']}. "
                                f"{moved[rec['page_changed']]} Do not repeat it unchanged.")
                        observation = await see(await runtime.look() or observation)
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
                        return await runtime.finalize(page.url, digest)
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
                        # M43: an element-scoped image does not arm `click_at`
                        # — this reads the frame LABEL, which records that the
                        # crop was taken to show a sub-region, and never the
                        # crop's geometry (ADR-035 Decision 2; PR #70 R10 found
                        # the geometric justification false for a crop that
                        # covers the viewport, where the refusal is still right)
                        # (`loop-click-at-from-a-drill-observation-is-refused`).
                        vision[0] = observation.get("screenshot_frame") == "viewport"
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
                        observation = await see(await runtime.look() or observation)

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
                if retarget_gap := root_retarget_gap(steps, new_steps):
                    return done(failure="task",
                                reason=f"plan rejected before execution: {gap}; {retarget_gap}")
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
                # The other half of T-M40-2-6's guard, and it is not redundant:
                # `parse_plan` covers the LIVE planner, and every offline case
                # injects `stub_planner` at that same boundary, so a malformed
                # plan reaches this loop without ever passing through it. A step
                # that is not a step is a plan the executor cannot honour, which
                # specs/000 already classifies as `task`.
                if not isinstance(step, dict) or not isinstance(step.get("action"), str):
                    return done(failure="task", reason=(
                        f"plan step {si + 1} is not a step: {step!r}"))
                read_only = step["action"] == "observe"
                rec, cls = await runtime.attempt(step, note=pending,
                                         recovery=("recovery" if pending_recovery
                                                   and not read_only else None))
                pending = None
                if not read_only:
                    pending_recovery = False

                # --- Family 1: locate -> relocation (self-maintenance) --------
                # Stale locator -> fresh a11y snapshot -> same intent at a
                # different tier -> act -> verify. Rungs come from the snapshot,
                # never from stored site knowledge (CLAUDE.md rule 6).
                # `observe` is progressive disclosure of the exact container
                # the plan named. Retargeting it drills into a different node,
                # produces no answer, and falsely counts as a recovery rung
                # (T-M40-2-5). Let the locate failure stay loud; only an
                # answer/action attempt may take the relocation ladder.
                if cls == "locate" and step["action"] != "observe" \
                        and (fresh := await runtime.look()) is not None:
                    for cand in relocation_candidates(step.get("target") or {}, fresh)[:MAX_FIXES]:
                        rec["superseded_by"] = step_offset + len(trace) + 1
                        alt = {**step, "target": cand}
                        rec, cls = await runtime.attempt(
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
                # `semantic` joins this family rather than getting one of its
                # own, because the recovery is identical: replan from the page
                # as it actually is. The only `semantic` failure the executor
                # raises is the identity anchor -- "the answer I just read was
                # not on a page about the thing you asked about" -- which is
                # the single most informative signal a run produces and was,
                # until now, the one the ladder threw away. It fell straight to
                # `return done(failure=cls)`, so a live run answered a task
                # about Intel from a page that never said Intel, spent 0 of its
                # 2 replans, and stopped (`replan-after-a-refused-anchor`).
                if cls in ("act", "semantic"):
                    if budgets["replans"] >= MAX_REPLANS:
                        rec["note"] += f"; replan budget exhausted ({MAX_REPLANS})"
                    elif (fresh := await runtime.look()) is not None:
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
                        # `not reads_without_acting([step])` scopes the
                        # laundering guard to what it is actually about: a
                        # failed step that was SUPPOSED to change the page. An
                        # extraction never was, so "the replan only reads" is
                        # not evidence of laundering there -- it is the correct
                        # recovery, and without this clause every semantic
                        # replan would be refused by a guard written about
                        # clicks (`replan-after-a-refused-anchor` red).
                        elif (drops_action and changed_nothing(rec)
                              and not reads_without_acting([step])):
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

    return await runtime.finalize(final_url, digest)
