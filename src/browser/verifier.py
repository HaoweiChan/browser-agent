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

_NUM = re.compile(r"^[^\w]*([-+]?\d[\d,]*\.?\d*)\s*[^\w]*$")


def normalize(value) -> str:
    """Casefold + collapse whitespace; pure numeric/currency values compare
    numerically so "$39.00" and "39" are the same answer.

    Decimal, never float formatting: `%g` rounds to 6 significant digits, which
    made the grader call $12,345.67 and $12,345.74 the same number — a wrong
    answer scored PASS at the only layer that decides correctness (case
    verifier-numeric-precision).
    """
    s = re.sub(r"\s+", " ", str(value)).strip().casefold().strip(".,;:!")
    m = _NUM.match(s)
    if m:
        try:
            return format(Decimal(m.group(1).replace(",", "")).normalize(), "f")
        except InvalidOperation:
            pass
    return s


def answers_match(got, want) -> bool:
    if isinstance(want, list) != isinstance(got, list):
        return False
    if isinstance(want, list):
        return len(got) == len(want) and all(
            normalize(g) == normalize(w) for g, w in zip(got, want)
        )
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
    check(
        "no_failed_postcondition",
        not any(s.get("postcondition_ok") is False for s in trace or []),
        "a step's postcondition was not reached",
    )
    check("answer_nonempty", bool(answer), "answer is empty")

    # A click changes state; an unverified state change is not a verified one.
    # `postcondition_ok is None` means "nothing was checked" — distinct from
    # False, and it must not read as success (case postcondition-unverified-click).
    unverified = [s["i"] for s in trace or []
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
