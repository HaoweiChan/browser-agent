"""Planner: NL task -> typed steps (docs/architecture/task1-overview.md, D9).

A planner is `async (task, url) -> (steps, usage)`; usage always carries
`llm_tokens`/`llm_usd`, and a successful live call also carries `cached`. The eval fast suite injects
`stub_planner` at this boundary — zero LLM calls (cost-discipline rule 4);
the live OpenRouter planner is exercised by the CLI, the gateway, and the
`full` suite.
"""

import asyncio
import hashlib
import json
import os
import urllib.request
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5.6-luna"

# Bump when the prompt, request parameters or cached response shape changes.
# The complete payload is also hashed; the version makes an intentional cache
# break explicit instead of relying on a textual prompt diff to do it by luck.
PLAN_CACHE_VERSION = "plan-v1"

# --- M9 cost/model ablation (specs/decisions/ADR-010-m9-model-ablation.md) ----
#
# Two lists, because they answer two different questions and conflating them cost
# the default its own endpoint once already (owner spec change, 2026-08-20):
#   ABLATION_MODELS — what the ablation RUNS. Owner-selected: popular on
#     OpenRouter and within a price ceiling the owner set.
#   ALLOWED_MODELS  — what `POST /tasks` ACCEPTS. The ablation set plus the
#     incumbent default, which must stay reachable by explicit name even though
#     it is priced out of the comparison.
#
# Selection is the owner's, on two stated criteria: entries from OpenRouter's
# usage leaderboard (which measures adoption, not quality — the page says so, and
# ADR-010 Decision 2 quotes it), capped at what `CEILING_MODEL` lists for.
# Every id was read from https://openrouter.ai/api/v1/models (no key needed) and
# frozen with its prices in evals/labels/openrouter-models-20260820.json; the
# allowlist is pinned against that snapshot, and the ceiling is enforced from it,
# by gateway-model-reaches-planner. A typo'd id is a run that fails at spend time.
# The ceiling is the MODEL, not a number (owner ruling, 2026-08-20). No price
# literal lives here, and that is a fix rather than a style choice: the previous
# version hard-coded this model's list price and it drifted 11% inside one working
# session, leaving code, an ADR, a support-matrix row and §9 all quoting a figure
# the provider had stopped charging (PR #15, R16). The effective ceiling is
# derived from the frozen snapshot's entry for this id — one source of truth, and
# nothing to hand-raise. (The snapshot cannot be read from here: `evals/` is
# .dockerignored, so a production import of it would break the image.)
CEILING_MODEL = "deepseek/deepseek-v4-pro"

# The default until 2026-08-21, replaced by the ablation's own pick. Named here
# rather than deleted because ADR-010 Decision 6 excluded it on price, and an
# exclusion whose subject has no name cannot be re-checked when prices move.
SUPERSEDED_INCUMBENT = "anthropic/claude-sonnet-4.5"

ABLATION_MODELS = [
    CEILING_MODEL,                        # the ceiling itself
    "openai/gpt-5.6-luna",
    "tencent/hy3",
    "deepseek/deepseek-v4-flash-0731",    # cheapest, and most-used model on OpenRouter
]

# The default is now one the ablation MEASURED, which is the whole point of M9
# and reverses the arrangement this file shipped with. Until 2026-08-21 the
# default was `anthropic/claude-sonnet-4.5`: over CEILING_MODEL on both prompt and
# completion, therefore ablated by no cell, therefore unable to stay the default
# on cost grounds alone whatever the numbers said (ADR-010 Decision 6). The
# numbers are now in (ADR-010 Decision 16, `docs/analysis.md` §9) and the
# pre-committed rule in Decision 5 picked the replacement: every candidate scored
# the same correctness, so the tie fell to cost, and this is the cheapest cell.
#
# No figures here — the comment above says why, and the multiples an earlier draft
# quoted went stale inside a session (PR #15, R23). The snapshot carries the
# numbers; gateway-model-reaches-planner derives the comparison from it.
#
# The superseded incumbent stays in the frozen snapshot on purpose: it is the
# evidence for Decision 6's exclusion, and dropping it would delete the reason
# the default moved. It is NOT in the allowlist any more — a public endpoint
# should not accept a model this system deliberately stopped paying for.
#
# --- M42 loop mode (ADR-027 Decision 4, ADR-028) -----------------------------
#
# The declared amendment to ADR-010's price ceiling, and the whole of it. ADR-027
# rules that the ceiling STAYS for the ablation arms and for mode B's default,
# and is lifted only for loop-mode additions, each allowlisted by explicit id
# with its price recorded. So this is a THIRD list, not a widening of either
# existing one:
#   * it is NOT in ABLATION_MODELS, so `gateway-model-reaches-planner`'s ceiling
#     sweep — which runs over the ablation set — is untouched and still refuses
#     any ablated model priced above CEILING_MODEL;
#   * it IS in ALLOWED_MODELS, so `POST /tasks` accepts it by name, and the same
#     case's containment check therefore requires it to be frozen evidence like
#     every other accepted id (evals/labels/openrouter-models-20260820.json,
#     amended 2026-08-26 with this entry read from the live endpoint that day).
# `gateway-model-reaches-planner` grades exactly that split: an id that leaks
# into the ablation set, or that is allowlisted without frozen evidence, is red.
#
# Why a frontier model at all: loop mode calls the model once per STEP with a
# fresh observation, and M43 will hand it screenshots. The two capabilities that
# buys are native tool-calling and vision. No price literal here for the reason
# CEILING_MODEL carries none — the snapshot holds the numbers, and a figure
# re-typed into code drifted 11% inside one working session once already.
LOOP_MODELS = ["anthropic/claude-opus-5"]

# The loop driver's default. Named separately from DEFAULT_MODEL because the two
# answer different questions: DEFAULT_MODEL is what mode B plans with and is the
# ablation's own pick under a ceiling this model is deliberately above.
DEFAULT_LOOP_MODEL = LOOP_MODELS[0]

# dict.fromkeys, not a set: the default is also an ablated model now, so the two
# lists overlap, and order is the display order §9 and the ADR both use. The loop
# additions come last so that order stays the one ADR-010 published.
ALLOWED_MODELS = list(dict.fromkeys([DEFAULT_MODEL, *ABLATION_MODELS, *LOOP_MODELS]))

SYSTEM = """You are a browser-automation planner. Emit ONLY a JSON array of steps.
Each step: {"action": "navigate|click|fill|extract|extract_all|observe|select_option|scroll|press|wait_for|go_back",
 "target": {"role": str|null, "name": str|null, "text": str|null, "near": str|null, "index": int|null} | null,
 "value": str|null,
 "anchor": str|null,
 "rank": bool|null,
 "expected_state": {"url_contains": str} | {"text_visible": str} | {"role_visible": {"role": str, "name": str|null}} | null}
Rules: `navigate` puts the URL in `value`. `extract` reads the target element's
text as the answer. `observe` asks for a closer look: an observation is capped
and a long page is cut off mid-way, so when the answer is inside a container you
can see but whose contents you cannot, target that container with `observe` and
you are re-planned against that subtree alone — all of its elements, more of its
text. It costs one planning call out of a small budget: ask once, then extract.
`extract_all` reads EVERY match of its target and returns
them as a list — use it whenever the task compares, ranks or counts across many
items ("which X has the most/least Y", "the cheapest one"): extract the values
to be compared, one per item, and never the answer itself. The comparison is
done in code, not by you, so a plan that guesses the winner with a single
`extract` is rejected before it runs. Every `extract_all` MUST set `rank`, and
the run fails without it: `rank: true` when the task wants ONE item out of the
set ("which is cheapest", "the most-quoted author"), `rank: false` when the
task wants the set itself ("list every product with its price"). You are
saying which the user asked for, not which item wins — code decides that. Targets are semantic (ARIA role + accessible name) — never
CSS selectors. `index` (0-based) picks the k-th match when several elements
share a role, e.g. the first search result. `near` picks the match closest to a
visible string instead of counting: use it when the element you want has no name
of its own but sits beside one that does — a price beside a product, a value
beside its table label, an author beside a byline. Prefer `near` over `index`
when such a string exists; only these five target keys exist, and any other key
fails the run. Neither `index` nor `near` may appear on an `extract_all`: both
pick one match and that step wants them all, so the run fails if you send both. On an `extract` step, `anchor` is
the distinguishing name of the entity the task is about; the run fails if that
string is absent from the page the answer was read from — use it whenever the
task names a specific entity. Prefer few steps.
Every `click` MUST carry an expected_state — a click that changes nothing you
can check is a click nobody can verify, and the run will be failed for it.
Pick the cheapest checkable consequence: a URL fragment, or a role+name that
becomes visible. All keys you give must hold, so assert one thing you are sure
of rather than two you are hoping for. `fill` verifies itself by readback and
needs no expected_state. If a click's consequence genuinely cannot be known
from the observation, prefer a different plan over a guess — never invent
expected text.
`select_option` chooses the option named by `value` and verifies the selection by
readback. `scroll` either targets an element to bring it into view or uses
`value` as a pixel distance; it verifies that the element is visible or the
page moved. `press` sends the key in `value` to its target, or to the page when
target is null, and MUST carry `expected_state`. `wait_for` MUST carry an
`expected_state`: that predicate is the wait, so never emit a predicate-free
sleep. `go_back` returns one history entry and MUST carry `expected_state`.
When a page observation is provided: the browser is ALREADY on that page — do
not re-navigate unless the task needs a different page, and target ONLY roles/
names present in the observation. Output the raw JSON array only — no markdown fences, no commentary."""


class PlanError(Exception):
    """The MODEL did not produce a plan — as distinct from the call failing.

    This type is the only thing in the system that means "the response arrived
    and was not a plan", so it is the discriminator every layer above uses
    instead of pattern-matching an error message (PR #15, R9).

    It carries `usage` because the provider bills a completion whether or not it
    parses. A model that answers with prose is charged for the prose, and a cost
    table that drops those calls under-reports exactly the runs it exists to
    find (PR #15, R10)."""

    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage or {"llm_tokens": 0, "llm_usd": 0.0}


def parse_plan(content: str) -> list:
    """Model output -> list of steps. Raises PlanError on non-plan output.

    Tolerates markdown code fences (real production variance: adversarial case
    planner-fenced-json, run 5a52f0aa)."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        steps = json.loads(text)
        assert isinstance(steps, list)
        # T-M40-2-6: the list was the only thing checked, so `[None]` and
        # `["extract WebArea"]` were plans as far as every layer below is
        # concerned -- and the step loop then read `step["action"]` off a string
        # and raised a bare TypeError out of `run_task`, with no status and no
        # failure class. "Is this object a step" belongs HERE, one layer above
        # the lint, whose own question is "is this plan answerable".
        assert all(isinstance(x, dict) and isinstance(x.get("action"), str)
                   for x in steps), "a step must be an object with a string action"
        return steps
    except Exception as e:
        raise PlanError(f"planner returned non-plan output: {e}: {content[:200]}")


def stub_planner(plans: list):
    """Deterministic planner for the fast suite: one plan per call, in order.

    A sequence rather than a single plan because M3 replans: a case that injects
    a bad first plan has to be able to say what the replanner comes back with.
    The last plan repeats, so a case that never replans still just gets its one
    plan — and a replan that returns the same steps is caught by the agent's
    no-progress guard rather than looping.
    """
    calls = [0]

    async def plan(task: str, url: str | None, observation: dict | None = None, note: str | None = None):
        plan.notes.append(note)
        steps = plans[min(calls[0], len(plans) - 1)]
        calls[0] += 1
        return steps, {"llm_tokens": 0, "llm_usd": 0.0}

    # Every note this planner was handed, in call order (None for the first
    # plan). The stub discards the note when choosing what to return — that is
    # what makes it deterministic — so without this record nothing could grade
    # the message a real planner would have been sent (PR #29 R5).
    plan.notes = []
    return plan


def build_user(task: str, url: str | None, observation: dict | None = None,
               note: str | None = None) -> str:
    """The user message a real planner is sent. Module-level and pure so it can
    be graded without a key, a network call or a token.

    The CALLER owns a replan's framing. The two callers are in different
    situations — an `act` failure mid-run (plan the REMAINING work; the executed
    prefix is not re-issued) and a plan the lint rejected before anything ran
    (plan the WHOLE task; nothing has executed and the page is untouched) — and
    one shared sentence here told a real model "A previous attempt failed" when
    nothing had, then asked it to plan only what was still needed of a task none
    of which had been done (PR #29 R5). So this function adds no framing of its
    own: the note goes in verbatim.

    That was the half of R5 nothing graded, because every offline case uses
    `stub_planner` and never reaches this line (PR #29 R11). It is now a pure
    function with a case over it (`planner-prompt-carries-the-note`); the
    `expect.planner_note_contains` key grades the other half, what the call
    sites pass. M32's cold review reached the same conclusion from the other
    caller: a drill-down is a SUCCESSFUL request for a closer look, and a shared
    "A previous attempt failed" wrapper told the model the step that asked for
    it had failed (`planner-note-is-not-always-a-failure`).
    """
    user = f"Task: {task}\nStart URL: {url or 'none — choose one via navigate'}"
    if observation:
        from .observe import render

        user += "\n\nCurrent page observation:\n" + render(observation)
    if note:
        user += "\n\n" + note
    return user


def _openrouter(key: str, payload: dict) -> dict:
    """One POST to OpenRouter. Shared by the planner and the loop driver so a
    header, a timeout or an endpoint change lands in both — there is no version
    of this system where one of the two callers should be sending something
    different."""
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _plan_cache_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "runs" / "planner_cache.json"


def _plan_cache_key(payload: dict) -> str:
    blob = json.dumps([PLAN_CACHE_VERSION, payload], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _plan_cache_load() -> dict:
    path = _plan_cache_path()
    if not path.exists():
        return {}
    try:
        cache = json.loads(path.read_text())
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}  # a corrupt cache costs one paid call, never a run failure


def _plan_cache_save(cache: dict) -> None:
    # ponytail: the gateway serializes runs; add a file lock if multi-process
    # writers become a supported deployment shape.
    path = _plan_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache))


def live_planner(model: str = DEFAULT_MODEL):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise PlanError("OPENROUTER_API_KEY is not set")

    async def plan(task: str, url: str | None, observation: dict | None = None, note: str | None = None):
        user = build_user(task, url, observation, note)
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "usage": {"include": True},
        }
        cache_key = _plan_cache_key(payload)
        cache = _plan_cache_load()
        try:
            steps = parse_plan(json.dumps(cache[cache_key]["steps"]))
        except (KeyError, TypeError, PlanError):
            pass
        else:
            return steps, {"llm_tokens": 0, "llm_usd": 0.0, "cached": True}
        data = await asyncio.to_thread(_openrouter, key, payload)
        # Usage first: this completion is billed whatever it contains, and
        # building it after `parse_plan` meant a prose answer threw its own cost
        # away (PR #15, R10).
        u = data.get("usage", {})
        usage = {
            "llm_tokens": u.get("total_tokens", 0),
            "llm_usd": float(u.get("cost", 0.0)),
        }
        # Default-deny at the response boundary. Round 3 guarded the whole
        # response handling with `except Exception -> PlanError`, which classified
        # everything it did NOT recognise as the model's fault — the same
        # catch-all shape as the defect before it, with the polarity flipped
        # (PR #15, R18). Only a response positively recognised as "the model
        # answered, and the answer is not a plan" is the model's; an envelope this
        # code cannot read is the provider, and stays an ordinary exception so
        # callers abort instead of scoring it.
        #
        # Any truthy `error` is a provider error, not a string-vs-dict question:
        # an `isinstance(..., dict)` test missed `{"error": "rate limited"}`.
        if data.get("error"):
            raise RuntimeError(f"provider error: {data['error']}")
        try:
            choice = data["choices"][0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError(f"message is {type(message).__name__}, not an object")
        except Exception as e:
            raise RuntimeError(
                f"unreadable planner response envelope: {type(e).__name__}: {e}") from e
        # From here the model demonstrably answered, so everything is its own
        # doing and carries the usage the provider billed for it.
        content = message.get("content")
        if not content:
            # `content: null` is what a reasoning model returns on
            # `finish_reason: length`, and the ceiling model defaults to high
            # reasoning effort. It answered; the answer contains no plan.
            raise PlanError(
                "model returned no plan content "
                f"(finish_reason={choice.get('finish_reason') or 'unknown'})", usage)
        try:
            steps = parse_plan(content)
        except PlanError as e:
            e.usage = usage
            raise
        cache[cache_key] = {"steps": steps}
        _plan_cache_save(cache)
        usage["cached"] = False
        return steps, usage

    return plan


# --- Loop mode: the model chooses every step (ADR-027, ADR-028) --------------
#
# A driver is `async (task, url, observation, trace, found, note) -> (call, usage)`,
# the same injection-boundary shape a planner has and stubbed the same way. It
# differs from a planner in cadence and in nothing else: one call, one action,
# then a fresh observation. The executor's action implementations, the resolver,
# the trace schema, the verifier and the judge are shared with mode B.
#
# `found` is what the run has extracted so far. It is passed rather than read
# out of the trace because the trace records what was ATTEMPTED, not what came
# back, and a loop that cannot see its own readings cannot compare two of them.
# The alternative — writing extracted values into the trace `note` — would move
# mode B's evidence shape for a loop-mode need, which is the change no case asks
# for.

STEP_KEYS = {"target", "value", "anchor", "rank", "expected_state"}

_TARGET_SCHEMA = {
    "type": "object",
    "description": "A SEMANTIC target: ARIA role plus accessible name, exactly as they appear "
                   "in the observation. Never a CSS selector, an id, or a DOM path.",
    "properties": {
        "role": {"type": "string"}, "name": {"type": "string"}, "text": {"type": "string"},
        "near": {"type": "string", "description": "a visible string the element sits beside"},
        "index": {"type": "integer", "description": "0-based, picks the k-th match"},
    },
}
_EXPECTED_SCHEMA = {
    "type": "object",
    "description": "The machine-checkable consequence. Every key given must hold; assert one "
                   "thing you are sure of rather than two you are hoping for.",
    "properties": {
        "url_contains": {"type": "string"},
        "text_visible": {"type": "string"},
        "role_visible": {"type": "object",
                         "properties": {"role": {"type": "string"}, "name": {"type": "string"}}},
    },
}
_PARAM = {
    "target": _TARGET_SCHEMA,
    "expected_state": _EXPECTED_SCHEMA,
    "value": {"type": "string"},
    "anchor": {"type": "string",
               "description": "the distinguishing name of the entity the task is about; the run "
                              "fails if it is absent from the page the answer was read from"},
    "rank": {"type": "boolean",
             "description": "true when the task wants ONE item out of the set, false when it "
                            "wants the set itself. Code does the comparison, not you."},
}

# action -> (description, parameter names, required parameter names). One entry
# per executor action, so the vocabulary the model is offered cannot drift from
# the vocabulary the executor implements — `driver-tools-match-the-executor`
# reads both, in both directions, and reddens if they disagree.
TOOL_TABLE = {
    "navigate": ("Load a URL. Put the URL in `value`.", ["value"], ["value"]),
    "click": ("Click one element. MUST carry an expected_state — a click whose consequence "
              "nobody can check is a click nobody can verify.", ["target", "expected_state"],
              ["target", "expected_state"]),
    "fill": ("Type `value` into a field. Verifies itself by readback; no expected_state needed.",
             ["target", "value"], ["target", "value"]),
    "select_option": ("Choose an option of a <select> by its visible label (or its value). "
                      "Verifies itself by reading back what ended up selected.",
                      ["target", "value"], ["target", "value"]),
    "scroll": ("Scroll. With a `target`, bring that element into view — this fails only if the "
               "element is still not visible afterwards, so it is safe on an element already in "
               "view. Without a target, scroll the window by `value` pixels (negative scrolls "
               "up); that form fails if the position did not move.",
               ["target", "value"], []),
    "press": ("Send one key (e.g. \"Enter\") to `target`, or to the page when no target is "
              "given. Changes state like a click, so it MUST carry an expected_state.",
              ["target", "value", "expected_state"], ["value", "expected_state"]),
    "wait_for": ("Wait until an expected_state holds. Use it when an action's result is painted "
                 "later than the action returns. Fails loudly if it never holds.",
                 ["expected_state"], ["expected_state"]),
    "go_back": ("Go back one entry in this tab's history. Carries an expected_state like any "
                "state-changing step.", ["expected_state"], ["expected_state"]),
    "click_at": ("Click at pixel coordinates read off the CURRENT viewport screenshot: `value` "
                 "is \"x,y\" in CSS pixels, origin top-left. ONLY for an element the "
                 "observation cannot name — a semantic target is always better when one "
                 "exists. Refused unless your current observation carries a viewport "
                 "screenshot (a drill's element-scoped image does not count: its pixels are "
                 "in a different frame). Changes state like a click, so it MUST carry an "
                 "expected_state.", ["value", "expected_state"], ["value", "expected_state"]),
    "extract": ("Read one element's text as the answer. Never target the accessibility document "
                "root (WebArea): its text is the whole page and it answers nothing.",
                ["target", "anchor"], ["target"]),
    "extract_all": ("Read EVERY match and return them as a list — use it whenever the task "
                    "compares, ranks or counts across many items. MUST declare `rank`.",
                    ["target", "rank"], ["target", "rank"]),
    "observe": ("Look closer at one container: you are shown that subtree alone, all of its "
                "elements and more of its text. Costs a step like anything else.",
                ["target"], ["target"]),
    "final_answer": ("Stop: what the task asked for has been extracted. The answer is assembled "
                     "in code from what you extracted, so extract it before calling this — a "
                     "final_answer with nothing read is a failed run.", [], []),
}

TOOLS = [{"type": "function",
          "function": {"name": action, "description": desc,
                       "parameters": {"type": "object",
                                      "properties": {p: _PARAM[p] for p in params},
                                      "required": list(required)}}}
         for action, (desc, params, required) in TOOL_TABLE.items()]

DRIVER_SYSTEM = """You are driving a real browser, one action at a time. After every action you
are shown the page as it is NOW, plus everything you have done so far. Call exactly one tool per
turn; do not narrate.
Targets are semantic (ARIA role + accessible name) and must name something in the observation you
were just given — never a CSS selector and never a role you did not see. The observation is capped,
so when the answer is inside a container you can see but whose contents you cannot, `observe` that
container.
The answer is assembled in code from what you `extract`, never from what you say: read the element
that HOLDS the value, then call `final_answer`. Never extract the accessibility document root
(WebArea) — its text is the whole page, and that read is refused as you emit it. For a task that
asks which item of a set ranks highest or lowest, read the page exactly once with `extract_all` and
declare `rank: true`; the comparison is done in code.
A page painted after an action is the normal case, not an error: if what you expect is not there
yet, `wait_for` it rather than reading an empty element. If the same page keeps coming back
unchanged, change strategy — repeating an action that changed nothing will end the run.
When the observation says a screenshot is attached, LOOK at it: a page can hold values and
controls that have no role and no accessible name, and the screenshot is the only place they
appear. For a control nothing can name, `click_at` its pixel coordinates from the CURRENT
viewport screenshot; for a value you can see but not target, find its exact text in the image
and `extract` it with a `text` target so the answer is still read from the page."""


def build_driver_user(task: str, url: str | None, observation: dict | None = None,
                      trace: list | None = None, found: list | None = None,
                      note: str | None = None) -> str:
    """The user message a real driver is sent. Module-level and pure, so it can
    be graded without a key, a network call or a token — the half of the mode B
    prompt that went ungraded for two milestones (PR #29 R11).

    The note goes in verbatim, for the same reason `build_user` adds no framing
    of its own: the CALLER knows whether this is a refusal, a failed step or a
    no-progress stop, and one shared sentence here would misdescribe two of the
    three."""
    from .observe import render

    out = [f"Task: {task}", f"Start URL: {url or 'none — choose one via navigate'}"]
    out.append("\nWhat you have done so far:\n" + trace_digest(trace))
    if found:
        out.append("\nWhat you have extracted so far:\n"
                   + "\n".join(f"- {v!r}" for v in found))
    if observation:
        out.append("\nThe page RIGHT NOW:\n" + render(observation))
    if note:
        out.append("\n" + note)
    return "\n".join(out)


def trace_digest(trace: list | None, keep: int = 12) -> str:
    """The executed trace as the driver sees it: what ran, and how it went.

    Bounded like every other thing sent to a model. The tail rather than the
    head, because a loop that has run long is deciding what to do NEXT, and the
    first navigation is the least useful line in the list."""
    lines = []
    for s in (trace or [])[-keep:]:
        bits = [f"{s['i']}. {s['action']}"]
        if s.get("target"):
            bits.append(str(s["target"]))
        if s.get("value") is not None:
            bits.append(f"value={s['value']!r}")
        bits.append(f"FAILED ({s['failure_class']}): {s.get('note') or ''}"
                    if s.get("failure_class") else
                    f"ok, postcondition={s.get('postcondition_ok')}")
        lines.append(" — ".join(bits))
    return "\n".join(lines) or "(nothing has run yet)"


def parse_tool_call(message: dict) -> dict:
    """One provider message -> one executor step. Raises PlanError when the
    MODEL did not produce a call, which is the same discriminator every layer
    above already uses for "the response arrived and was not a plan".

    Closed-world about arguments, the ruling `resolver-unknown-target-key`
    already made one level down: an argument this executor does not implement
    stops the step loudly instead of being dropped, because a dropped argument
    is a plan quietly reinterpreted and a run that reports on the weaker task it
    actually did."""
    calls = message.get("tool_calls") or []
    if not calls:
        raise PlanError("driver returned no tool call: "
                        f"{str(message.get('content'))[:200]}")
    fn = calls[0].get("function") or {}
    name = fn.get("name")
    if name not in TOOL_TABLE:
        raise PlanError(f"driver called unknown tool {name!r}")
    try:
        args = json.loads(fn.get("arguments") or "{}")
        assert isinstance(args, dict)
    except Exception as e:
        raise PlanError(f"driver tool arguments are not a JSON object: {e}")
    if unknown := set(args) - STEP_KEYS:
        raise PlanError(f"driver sent unsupported argument(s) {sorted(unknown)} to {name!r}")
    return {"action": name, **args}


def stub_driver(calls: list):
    """Deterministic driver for the fast suite: one scripted tool call per turn.

    The same shape as `stub_planner` and `stub_judge`, injected at the same
    boundary, so the loop driver, every new action, budget exhaustion and the
    trace shape are all graded at $0.00 in `fast` (ADR-027's Invariants: this
    IS the eval-first cost of loop mode). The last entry repeats, so a script
    that runs past its end keeps offering the same call — which is what the
    no-progress harness is supposed to notice.

    `_usage` on a scripted call is what that turn cost. It exists so a case can
    exhaust a token or USD ceiling without making 400,000 tokens of real calls,
    which is the only way to grade runaway protection offline.
    """
    i = [0]

    async def drive(task, url, observation=None, trace=None, found=None, note=None):
        drive.notes.append(note)
        drive.observations.append(observation)
        call = dict(calls[min(i[0], len(calls) - 1)])
        i[0] += 1
        usage = call.pop("_usage", None) or {"llm_tokens": 0, "llm_usd": 0.0}
        return call, usage

    # Everything the driver was handed, in call order — the stub discards it
    # when choosing what to return (that is what makes it deterministic), so
    # without this record nothing could grade the message a real driver gets.
    drive.notes, drive.observations = [], []
    return drive


def live_driver(model: str = DEFAULT_LOOP_MODEL):
    """OpenRouter native tool-calling, one call per step.

    Stateless by construction: every turn is rebuilt from (task, observation,
    trace, extractions, note) rather than from an accumulated message list.
    That costs prompt tokens — accepted by ADR-027's mandate, and recorded per
    run like everything else — and buys the property ADR-027 asks for by name:
    the trace IS the state, so nothing about a loop run lives in a place the
    reviewer UI, the verifier and the judge cannot read.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise PlanError("OPENROUTER_API_KEY is not set")

    async def drive(task, url, observation=None, trace=None, found=None, note=None):
        content = build_driver_user(task, url, observation, trace, found, note)
        # M43 (ADR-035 Decision 5): when the observation carries a screenshot,
        # the image rides beside the unchanged text as a data-URL content part.
        # Reading the file is NOT guarded: an observation that names an image
        # the driver cannot read is a run lying about what the model saw, and
        # the raise ends it `failure:env` through the loop's ordinary driver
        # error path (rule 4 — fail loudly, never degrade silently while the
        # `click_at` gate stays armed). One image per call, the current view
        # only: the driver is stateless (ADR-028 §7) and keeps no image history.
        if shot := (observation or {}).get("screenshot_path"):
            import base64
            with open(shot, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content = [{"type": "text", "text": content},
                       {"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}}]
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": DRIVER_SYSTEM},
                {"role": "user", "content": content},
            ],
            "tools": TOOLS,
            "tool_choice": "required",
            "usage": {"include": True},
        }
        data = await asyncio.to_thread(_openrouter, key, payload)
        # Usage first, for the reason `live_planner` takes it first: the
        # provider bills this completion whatever it contains.
        u = data.get("usage", {})
        usage = {"llm_tokens": u.get("total_tokens", 0),
                 "llm_usd": float(u.get("cost", 0.0))}
        if data.get("error"):
            raise RuntimeError(f"provider error: {data['error']}")
        try:
            message = data["choices"][0]["message"]
            assert isinstance(message, dict)
        except Exception as e:
            raise RuntimeError(
                f"unreadable driver response envelope: {type(e).__name__}: {e}") from e
        try:
            return parse_tool_call(message), usage
        except PlanError as e:
            e.usage = usage
            raise

    return drive
