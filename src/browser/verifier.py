"""OutcomeVerifier — layered outcome verification (docs/evals/evaluation-methodology.md).

The executor never grades itself. `verify()` takes **raw evidence** — the
values that were extracted, the page text they were read from, the step trace,
and (eval-side) external ground truth — and never the executor's own status or
reason. Production code: the agent loop calls it at runtime, the eval adapter
calls it again with ground truth. One verifier, two callers, no parallel truths.

Layers actually implemented here:

- **L1 deterministic predicates** — trace non-empty, no failed postcondition,
  non-empty answer, extracted values grounded in the page they came from, and
  **identity anchors**: a declared entity string must appear in the evidence.
- **L2 expected-output compare** — normalized compare of the answer against
  hand-labeled `expect.answer`, plus external ground truth (`expect.state` vs
  the fixture `/state` endpoint), when the caller supplies it.
- L3 (evidence-only LLM check) is SHOULD/out of B-floor scope; absent by design
  rather than stubbed, so no caller can mistake a stub for a verdict.

Known limitations of the runtime anchor, both stated rather than hidden — it is
a substring test over the page the answer was read from, so:

1. a near-miss entity whose name *contains* the target's name (any
   "<product> Pro" next to "<product>") passes;
2. on an **aggregate page** — a listing, a search-results page — every
   candidate entity appears in the page text, so the anchor is satisfied by the
   wrong answer just as readily as the right one. This is the larger of the two
   holes and it is where TC2/TC4 tasks live.

Only ground-truth L2 catches either, and a live run has no ground truth. The
trap cases in evals/adversarial/ hold both shapes open on purpose.
"""

import re
from decimal import Decimal, InvalidOperation

                        # sign        digits           trailing unit (%, etc.)
_NUM = re.compile(r"^(?P<lead>\D*?)(?P<sign>[-+]?)(?P<num>\d[\d,]*\.?\d*)(?P<unit>\D*)$")
# Symbols that mean "this is money" and carry no value of their own, so "$39.00"
# and "39" are the same answer. `%` is NOT here: it is a unit, and 2.5% is not
# 2.50. Two DIFFERENT symbols are never interchangeable either (€18 != $18).
_CURRENCY = "$€£¥₩₹"


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold().strip(".,;:!")


def _num_parts(s: str):
    """`(Decimal, currency|None, unit|None)`, or None when s is not a number.

    Sign and unit survive here. The previous pattern opened with a greedy
    Unicode `[^\\w]*`, which swallowed the sign before the group's own `[-+]?`
    could take it and erased every currency symbol to nothing — so -39 == 39,
    €18 == $18 and 2.5% == $2.50 all compared equal, at the only layer that
    decides correctness (case verifier-sign-currency-percent).
    """
    m = _NUM.match(s)
    if not m:
        return None
    lead, unit = m["lead"].strip(), m["unit"].strip()
    # Accounting negative: (39.00) is -39.00, not 39.00.
    paren = lead.endswith("(") and unit.startswith(")")
    lead, unit = lead.rstrip("("), unit.lstrip(")")
    sign = "-" if (m["sign"] == "-") ^ paren else ""
    try:
        val = Decimal(sign + m["num"].replace(",", "")).normalize()
    except InvalidOperation:
        return None
    # `t and` is load-bearing: "" is a substring of every string, so without it
    # an absent symbol reads as a currency and "$39.00" stops equalling "39".
    cur = next((t for t in (lead, unit) if t and t in _CURRENCY), None)
    # Anything left that is not a bare currency symbol is a real unit.
    other = [t for t in (lead, unit) if t and t not in _CURRENCY]
    if len(other) > 1:
        return None  # decorated on both sides and not money — compare as text
    return val, cur, (other[0] if other else None)


def normalize(value) -> str:
    """Casefold + collapse whitespace, with numbers canonicalized.

    Decimal, never float formatting: `%g` rounds to 6 significant digits, which
    made the grader call $12,345.67 and $12,345.74 the same number — a wrong
    answer scored PASS at the only layer that decides correctness (case
    verifier-numeric-precision).

    This is a string key, so it is the right tool for name/text matching (the
    resolver's relocation rungs use it) and the wrong one for comparing two
    answers — see answers_match.
    """
    s = _clean(value)
    parts = _num_parts(s)
    if not parts:
        return s
    val, cur, unit = parts
    return " ".join(filter(None, [format(val, "f"), unit, cur]))


def answers_match(got, want) -> bool:
    """Numbers compare structurally, not as normalized strings.

    A single canonical string cannot express what is actually true here,
    because the relation is not transitive: "$39.00" and "39" are the same
    answer, "€18.00" and "18" are the same answer, and yet "€18.00" and
    "$18.00" are NOT. So value, unit and currency are compared as three
    separate facts — a currency symbol may be absent on one side, but two
    different symbols never match, and a unit like % must match exactly.
    """
    if isinstance(want, list) != isinstance(got, list):
        return False
    if isinstance(want, list):
        return len(got) == len(want) and all(answers_match(g, w) for g, w in zip(got, want))
    g, w = _num_parts(_clean(got)), _num_parts(_clean(want))
    if g and w:
        return (g[0] == w[0] and g[2] == w[2]
                and (g[1] is None or w[1] is None or g[1] == w[1]))
    return normalize(got) == normalize(want)


def verify(*, trace, extractions, answer, expect=None, state=None) -> dict:
    """Return {"verdict": PASS|FAIL|INCONCLUSIVE, "layer", "checks", "reason"}.

    `extractions` — [{"value", "page_text"}] captured at extraction time.
    `state`       — external ground truth fetched by the caller (or None).
    """
    expect = expect or {}
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    def check(name, ok, why):
        checks[name] = bool(ok)
        if not ok:
            reasons.append(why)

    # --- L1: deterministic predicates over the evidence itself ---------------
    check("trace_nonempty", bool(trace), "no trace: nothing was attempted")

    # A recovery ladder only means something if the attempt it replaced stops
    # failing the run — otherwise no recovered run could ever be graded PASS.
    # That exemption is a hole by construction, so it is gated: a supersede is
    # honored only when the attempt it points at is really in the trace, and the
    # last attempt in a chain is never superseded, so its failure always counts
    # (case verifier-superseded-not-a-loophole). The failed attempts stay in the
    # trace either way — they are hidden from grading, not from the reader.
    present = {s.get("i") for s in trace or []}
    dangling = [s.get("i") for s in trace or []
                if s.get("superseded_by") and s["superseded_by"] not in present]
    check("supersedes_resolve", not dangling,
          f"step(s) {dangling} claim a later attempt that is not in the trace")
    graded = [s for s in trace or [] if not s.get("superseded_by")]

    check(
        "no_failed_postcondition",
        not any(s.get("postcondition_ok") is False for s in graded),
        "a step's postcondition was not reached",
    )
    check("answer_nonempty", bool(answer), "answer is empty")

    # A click changes state; an unverified state change is not a verified one.
    # `postcondition_ok is None` means "nothing was checked" — distinct from
    # False, and it must not read as success (case postcondition-unverified-click).
    unverified = [s["i"] for s in graded
                  if s.get("action") == "click" and s.get("postcondition_ok") is None]
    check(
        "actions_verified",
        not unverified,
        f"state-changing step(s) {unverified} carried no checkable postcondition",
    )

    ungrounded = [e["value"] for e in extractions or [] if e["value"] not in e.get("page_text", "")]
    check(
        "grounded",
        not ungrounded,
        f"extracted values absent from the page they were read from: {ungrounded}",
    )

    # Page evidence ONLY. Including the answer would let an anchor equal to the
    # expected answer certify itself, which is a green check that cannot go red
    # (case verifier-anchor-not-self-satisfied).
    anchors = expect.get("anchors") or []
    evidence_text = " ".join(e.get("page_text", "") for e in extractions or [])
    missing = [a for a in anchors if a not in evidence_text]
    check("identity_anchors", not missing, f"identity anchor(s) absent from evidence: {missing}")

    layer = 1

    # --- L2: compare against hand-labeled / external ground truth ------------
    if "answer" in expect:
        layer = 2
        check(
            "answer_matches",
            answers_match(answer, expect["answer"]),
            f"answer {answer!r} != expected {expect['answer']!r}",
        )
    if "state" in expect:
        layer = 2
        want = expect["state"]
        got = {k: (state or {}).get(k) for k in want} if want else (state or {})
        check(
            "ground_truth_state",
            got == want,
            f"ground-truth state {got!r} != expected {want!r}",
        )

    verdict = "PASS" if all(checks.values()) else "FAIL"
    return {
        "verdict": verdict,
        "layer": layer,
        "ground_truth": layer == 2,
        "checks": checks,
        "reason": "; ".join(reasons) or None,
    }
