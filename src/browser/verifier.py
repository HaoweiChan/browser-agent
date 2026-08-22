"""OutcomeVerifier — layered outcome verification (docs/evals/evaluation-methodology.md).

The executor never grades itself. `verify()` takes **raw evidence** — the
values that were extracted, the page text they were read from, the step trace,
and (eval-side) external ground truth — and never the executor's own status or
reason. Production code: the agent loop calls it at runtime, the eval adapter
calls it again with ground truth. One verifier, two callers, no parallel truths.

Layers actually implemented here:

- **L1 deterministic predicates** — trace non-empty, no failed postcondition,
  non-empty answer, extracted values grounded in the page they came from,
  extracted values not a dump of their own evidence window (`not_a_dump`,
  below), and **identity anchors**: a declared entity string must appear in
  the evidence, when the caller supplies `expect.anchors`.
- **L2 expected-output compare** — normalized compare of the answer against
  hand-labeled `expect.answer`, plus external ground truth (`expect.state` vs
  the fixture `/state` endpoint), when the caller supplies it.
- L3 (evidence-only LLM check) is SHOULD/out of B-floor scope; absent by design
  rather than stubbed, so no caller can mistake a stub for a verdict.

`not_a_dump` catches exactly one shape: an extracted value that reproduces
most of its own evidence window, e.g. a whole listing container returned as
"the answer" to a question that asked for one row of it (docs/analysis.md §8a
probe #5). It is NOT a semantic-responsiveness check — a short, plausible,
WRONG answer (the SKU instead of the price, the Pro variant instead of the
standard one) still sails through L1 untouched, because nothing here asks
whether the answer answers the question, only whether it looks like the
question was dodged by dumping the page. Only ground-truth L2 catches a wrong
but focused answer, and a live run has no ground truth.

`not_page_furniture` (M34, docs/support-matrix.md D24) is narrower than that
sentence makes it sound: it catches one specific way an answer can fail to be
responsive — the value is site chrome (nav, banner, footer), recognisable
because it is ALSO verbatim on a different page the same run visited — not
"does this answer the question" in general. A short, plausible, WRONG answer
that is unique to the page it was read from (the near-miss trap above) still
sails through this check exactly as it sails through `not_a_dump`; only
ground-truth L2 catches that shape. Numeric values are exempted outright
(docs/support-matrix.md D24 names why and what it costs).

`identity_anchors` here reads `expect["anchors"]`, and agent.py's runtime call
(agent.py:491) passes NO `expect` — so at runtime **this check is vacuous**;
it only does anything when a caller (the eval adapter) supplies
`expect.anchors`. The actual runtime identity gate is a different mechanism
entirely: an inline `anchor not in body` check in agent.py's extract step,
which raises a `semantic` StepError directly and never reaches this verifier.
Both are a substring test over the page the answer was read from, so both
share the same known limitations, stated rather than hidden:

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

# M7 phase 2: measured len(clean(value))/len(clean(page_text)) across the whole
# `fast` suite (every extraction, every case, not just the 24 hand-labeled
# runs). Real non-dump extractions top out at 0.18 (tc5-forms-submit-zh, a
# reference-number readback); the two known dumps sit at 0.45
# (probe5-books-travel-dump) and 0.52 (probe5-shop-listing-dump). 0.35 sits in
# the empty gap between them.
DUMP_RATIO = 0.35

# M34 (docs/analysis.md §8a-3, support-matrix D23): a THIRD demonstration that
# semantic responsiveness is not pattern-matchable over the task string, this
# time on a plain single-hop extraction with no aggregate/superlative shape
# for `aggregate_needs_comparison` to catch. The deployed build answered
# "tell me the price of the first book in the Travel category" with
# "Warning!" (books.toscrape.com's own demo-site disclaimer banner, present
# on every page) and, separately, "Travel" (the sidebar category link, also
# present on every page) -- both real, grounded, non-empty, not a dump, and
# answering nothing. Rejected as the fix: a fourth regex over the task
# string, same shape and ceiling as SCOPE_BLOCK and _AGGREGATE below (T-R31/
# T-R32) -- a keyword screen answers "does the TASK look like X", never
# "does THIS ANSWER respond to it", and a rephrasing walks around it exactly
# as the first three did. What actually distinguished both wrong answers from
# a real one, in the evidence the runtime already has: neither is specific to
# the page it was read from -- the same string sits verbatim on a DIFFERENT
# page this run also visited (the site's own home page, in both cases,
# confirmed live by curl against books.toscrape.com). A string identical
# across two distinct pages is a hallmark of site furniture (nav, banner,
# footer) -- something a page-specific question essentially never answers
# with, task text unread. `PAGE_INVARIANT_MIN_CHARS` guards the one cheap
# false-positive this invites: a short, generic value ("1", "OK", "Q4")
# recurring elsewhere by pure coincidence is unremarkable and carries no
# signal either way, so it is exempted rather than flagged.
PAGE_INVARIANT_MIN_CHARS = 4

# The other false positive this check invites, found by running it against the
# `fast` suite rather than guessed at: a price legitimately repeats between a
# catalogue row and that product's own detail page (tc2-shop-search-zh's
# "$18.00", trap-near-miss-entity's "$59.00" -- the SKU anchor that ties the
# detail page to its entity is not on the LISTING page, by design, so nothing
# else already in this function tells the two shapes apart). A number is not
# how site furniture speaks -- "Warning!" and "Travel" are not numbers, and no
# case anywhere in this repo has a banner/nav string that IS one -- so a value
# that parses via `_num_parts` is exempted from `not_page_furniture` outright.
# Declared ceiling, not a guess held in reserve: a marketing banner reading a
# generic price ("From $19.99") that recurs on every page and gets extracted
# in place of the real one would slip past this exemption. Nothing in this
# repo's evidence demonstrates that shape (docs/support-matrix.md), so it is
# named rather than pre-emptively guarded against, per CLAUDE.md rule 2.

# Restored at M7.2, this time with a case behind it. Phase 2 had a guard here
# (`MIN_EVIDENCE = 20`) and removed it (ADR-008 Decision 3) because nothing in
# the repo demonstrated the false FAIL it existed to prevent — a guard with no
# case behind it is speculative, and the removal was correct on the evidence
# available at the time. Main's `slow-asset.html` (added for its own
# navigation-timeout cases) then supplied that evidence inside the same PR:
# its correct answer is 23 clean chars on a 37-char page, ratio 0.62, which
# `not_a_dump` FAILed (case `verifier-sparse-page-not-a-dump`). 100 sits in
# the gap between that page (37 chars, 2.7x below the floor) and the
# smallest real dump in the suite, `probe5-shop-listing-dump` (195 chars,
# 1.95x above it) -- roughly their geometric mean, ~85. Swept every
# extraction the `fast` suite actually produces (115 observations): no page
# below this floor carries a ratio anywhere near DUMP_RATIO except the sparse
# fixture being fixed (next closest is 0.17, well clear), and no known real
# dump is smaller than 195 -- so the floor is not merely unopposed, it is
# never even close to being tested by anything else in the suite. Below this
# many clean characters, `not_a_dump` does not apply at all.
MIN_PAGE_CHARS = 100

# M10 probe #2 (docs/analysis.md, second held-out probe): "which author has
# the most quotes on this page?" against quotes.toscrape.com came back
# `status: success, verdict: PASS` twice, with two different WRONG answers
# ("Next →", a pager link; "Quotes to Scrape", the page <title>) —
# reproduced a third time independently. Every L1 check above is satisfied by
# construction here: whatever the planner grabs is real, grounded, non-empty
# and not a dump, because the check that is missing is not "is this real" but
# "does the plan vocabulary (navigate | click | fill | extract) even have a
# way to answer this question" — and for "which X has the most/least Y" it
# does not: there is no enumerate-and-count primitive, so any single-shot
# extraction is a guess wearing a PASS. Ground truth (L2) would catch a wrong
# guess; a live run has none, which is exactly probe #2's finding. Matches
# ONLY the superlative-over-a-set shape, not "cheapest"/"most expensive"
# (a price comparison, tracked separately — D14, `live-books-cheapest-travel`
# — and deliberately different wording so this does not collide with it).
# The other cost, undeclared until PR #25 R2: this fires on EVERY matching
# task with no ground truth, including one a single extraction answers
# correctly (a badge that states the superlative directly) — the same
# fail-closed shape as SCOPE_BLOCK's over-refusal, and just as deliberately
# accepted, but it went unwritten the first time this file shipped it.
# Declared now rather than left for a third probe to find (D22,
# docs/support-matrix.md). The ground-truth (L2) path below is untouched by
# this guard — pinned by verifier-aggregate-ground-truth-untouched, not just
# claimed in this comment.
#
# ponytail: a regex over English, same ceiling as SCOPE_BLOCK (agent.py) —
# it can be walked around by rephrasing, same as `log ?into` was. Widen when
# a probe finds the next phrasing, the way l5-refuse-login-contracted did.
_AGGREGATE = re.compile(
    r"\b(which|what|who)\b.{0,80}\b(most|least|fewest|highest|lowest|greatest)\b",
    re.IGNORECASE,
)


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


def verify(*, trace, extractions, answer, expect=None, state=None, task=None) -> dict:
    """Return {"verdict": PASS|FAIL|INCONCLUSIVE, "layer", "checks", "reason"}.

    `extractions` — [{"value", "page_text", "body_len"?}] captured at
                    extraction time. `body_len` (the real page length) is
                    optional and preferred by `not_a_dump` over `page_text`'s
                    own length when present; absent on records captured before
                    it existed (evals/labels/verifier-sample.jsonl).
    `state`       — external ground truth fetched by the caller (or None).
    `task`        — the task text, optional. Used ONLY by `aggregate_needs_comparison`
                    below; every other check still reads raw evidence exclusively.
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

    # A value that reproduces most of its own evidence window is a dump, not an
    # answer (probe #5: "which is cheapest" answered with the whole sorted
    # catalogue). Judged per extraction, never on the assembled answer, so a
    # genuine multi-row list stays green on every row even though the rows
    # together cover the whole page (case verifier-list-rows-not-a-dump).
    # ponytail: a dump LONGER than its own window is already caught by
    # `grounded` above (it can't be a substring of a window centred on
    # itself) — this only covers dumps up to roughly PAGE_TEXT_KEEP in size.
    # Below MIN_PAGE_CHARS the ratio does not apply at all (see its comment
    # above) — a correct answer that legitimately makes up most of a thin,
    # single-purpose page (case verifier-sparse-page-not-a-dump) is not a
    # dump, it is just a short page. `pt_len and ...` still separately guards
    # the zero-length case from a ZeroDivisionError.
    #
    # The denominator is the PAGE the value was read from, not the stored
    # window: `page_text` is agent.evidence_window()'s output, capped at
    # PAGE_TEXT_KEEP and doubled when a distant `anchor` forces a second window
    # onto it, so a ratio against it depends on storage, not the page (case
    # verifier-dump-ratio-anchor-flip). `body_len` — the real page length,
    # which agent.py already has in hand at extraction time — is preferred;
    # `page_text` is the fallback for the 25 frozen evals/labels/verifier-sample.jsonl
    # records, captured before this field existed, which must keep replaying.
    dumps = [e["value"] for e in extractions or []
             if (pt_len := e.get("body_len") or len(_clean(e.get("page_text", ""))))
             and pt_len >= MIN_PAGE_CHARS
             and len(_clean(e["value"])) / pt_len >= DUMP_RATIO]
    check("not_a_dump", not dumps, f"value reproduces most of its own evidence window: {dumps}")

    # M34: a value that is ALSO verbatim on a different page this run visited
    # is very likely site furniture (nav, banner, footer), not an answer to a
    # page-specific question -- the general shape behind "Warning!" and
    # "Travel" both passing every other L1 check on the deployed build
    # (docs/analysis.md §8a-3, support-matrix D23; see the comment above
    # PAGE_INVARIANT_MIN_CHARS for why this and not a keyword screen).
    # `other_page_text` is agent.py's running record of every OTHER distinct
    # URL's body text at extraction time -- "" (no signal, no flag) when this
    # run never visited a second page, or on the frozen labels/replay records
    # that predate this field, the same optional-field precedent `body_len`
    # already set above. Substring, not equality: the furniture string is
    # rarely the WHOLE other page, same reasoning `grounded` already uses.
    furniture = [e["value"] for e in extractions or []
                 if len(_clean(e["value"])) >= PAGE_INVARIANT_MIN_CHARS
                 and not _num_parts(_clean(e["value"]))
                 and _clean(e["value"]) in _clean(e.get("other_page_text", ""))]
    check("not_page_furniture", not furniture,
          f"value also appears verbatim on a different page this run visited, "
          f"which is page chrome, not a page-specific answer: {furniture}")

    # Page evidence ONLY. Including the answer would let an anchor equal to the
    # expected answer certify itself, which is a green check that cannot go red
    # (case verifier-anchor-not-self-satisfied).
    anchors = expect.get("anchors") or []
    evidence_text = " ".join(e.get("page_text", "") for e in extractions or [])
    missing = [a for a in anchors if a not in evidence_text]
    check("identity_anchors", not missing, f"identity anchor(s) absent from evidence: {missing}")

    # Runtime-only (no ground truth to fall back on): a superlative-over-a-set
    # question with no `expect.answer`/`expect.state` cannot be trusted from L1
    # evidence alone, because L1 has nothing that could tell a right guess from
    # a wrong one here — the plan vocabulary has no comparison primitive to
    # have gotten it right WITH. Ground-truth (L2) callers are untouched: if a
    # future case supplies `expect.answer` for this shape, answers_match still
    # decides it on its own merits — pinned by
    # verifier-aggregate-ground-truth-untouched, which is also the case that
    # proves a WRONG expect.answer still fails for the L2 reason, not because
    # this guard double-fires. The cost of failing closed with no ground truth
    # is declared, not just paid: D22, docs/support-matrix.md.
    has_ground_truth = "answer" in expect or "state" in expect
    if task and not has_ground_truth:
        check("aggregate_needs_comparison", not _AGGREGATE.search(task),
              "superlative/aggregate question over a set ('which X has the most/least Y') "
              "has no enumerate-and-count step in the plan vocabulary; a layer-1-only "
              "verdict cannot tell a right guess from a wrong one, so it fails loudly "
              "rather than passing on unverifiable evidence")

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
