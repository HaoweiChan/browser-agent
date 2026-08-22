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

`identity_anchors` here reads `expect["anchors"]`, and agent.py's runtime call
(`run_task`'s closing `verify(...)`) passes NO `expect` — so at runtime **this check is vacuous**;
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
from collections import Counter
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
# way to answer this question" — and at M10, for "which X has the most/least Y",
# it did not: there was no enumerate-and-count primitive, so any single-shot
# extraction was a guess wearing a PASS. (M31 added one, `extract_all`, which is
# what the relaxation further down reads for; the guard below is unchanged for
# every plan that still does not use it.) Ground truth (L2) would catch a wrong
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

# Which END of the order the task asked for. Deliberately NOT `_AGGREGATE`'s
# vocabulary, because the two answer different questions: `_AGGREGATE` decides
# "is this an aggregate-shaped task", and it is the shared ceiling of the
# verifier guard above and agent.py's plan lint (one regex, two callers);
# this one only decides direction, once a plan has ALREADY enumerated, and it
# has to cover the price comparisons `_AGGREGATE` excludes on purpose
# (`live-books-cheapest-travel`, D14 — "cheapest" is not a superlative over a
# set of counts). Widening one does not widen the other, which is the point.
#
# ponytail: only wording this repo has actually seen in a task is listed —
# D21's lesson, that widening to synonyms nobody probed is the unwatched
# expansion CLAUDE.md rule 2 exists to prevent. "most expensive" precedes
# "most" so the alternation prefers the longer phrase at the same position.
_RANK = re.compile(
    r"\b(most expensive|cheapest|most|greatest|highest|least|fewest|lowest)\b",
    re.IGNORECASE,
)
_RANK_MAX = {"most expensive", "most", "greatest", "highest"}

# Does the task ask for the ENUMERATION, or for one item out of it? This is the
# only question that separates "list every product ... cheapest first" (all four
# rows) from "find the cheapest product" (one row) — both contain a `_RANK`
# word, both are answered by the same `extract_all`, and nothing about the plan
# or the page tells them apart. Gating the reduction on `is_aggregate` instead
# was tried and over-corrected: it dropped the reduction for every cheapest
# wording and published the raw enumeration as a successful answer (PR #29 R9,
# case extract-all-cheapest-wording-still-reduces).
#
# ponytail: three words, all of them wording this repo has actually shipped in a
# task ("List every product in the catalogue with its price, cheapest first").
# `\blist\b` deliberately does not match "listed", which is how probe #3's own
# question ("which author has the most quotes listed on this page") stays a
# single-answer ranking. "all" is NOT here: "of all the products, which is
# cheapest" is a comparison frame, not a request for all of them, and including
# it would put that shape back on the wrong side. The ceiling is the ceiling of
# a regex over English, same as SCOPE_BLOCK's: an unseen enumerate phrasing
# ("show me the prices, cheapest first") reduces to one value instead of
# listing. Widen when a probe demonstrates one — T-CHEAPEST-WORDING.
_ENUMERATE_REQUEST = re.compile(r"\b(list|every|each)\b", re.IGNORECASE)


def rank(task: str, values: list):
    """Reduce an `extract_all` enumeration to the one item the task asked for.

    This is the "rank/compare/count stays in code" half of M31: `extract_all`
    gathers every candidate, and the comparison over them is arithmetic here,
    never a judgement the model was asked to make. Two rules, picked by what the
    values ARE rather than by what the task says they are:

    - EVERY value parses as a number -> compare the numbers (prices, counts
      already rendered on the page);
    - NONE of them does -> count occurrences, because "which author has the
      most quotes" is a question about how often a name appears;
    - some but not all -> refuse (see the comment on that branch).

    A task with no ranking word — or one that asks for the enumeration itself
    (`_ENUMERATE_REQUEST`) — gets its list back untouched: a multi-row list is a
    legitimate answer shape (contract: answer string|list, cases
    `verifier-list-rows-not-a-dump`, `extract-all-list-task-keeps-every-row`).

    A tie RAISES rather than picking one. The same ruling the resolver already
    makes for proximity (`near-equidistant-is-ambiguous`): two winners mean the
    page does not identify one, and choosing between them is a confident wrong
    answer — the exact defect family this milestone exists to close.

    ponytail: inside the numeric branch the comparison is on the Decimal alone,
    so a column mixing CURRENCIES or units ("£23.21" beside "$18.00") ranks as
    if they were commensurable — distinct from the partly-numeric case below,
    which does refuse. No enumeration in this repo produces one: every
    `extract_all` reads one column of one page. Upgrade path and repro:
    tasks/TODO.md T-RANK-UNITS.
    """
    if _ENUMERATE_REQUEST.search(task or ""):
        return values  # the task asked for the enumeration, not for one of it
    m = _RANK.search(task or "")
    if not m or not values:
        return values
    want_max = m.group(1).casefold() in _RANK_MAX
    nums = [_num_parts(_clean(v)) for v in values]
    # A column that is only PARTLY numeric refuses. Falling through to the
    # counting branch is the dangerous default: one "Out of stock" or "Price on
    # request" in a price list demotes a comparison into a mode, so the repeated
    # price wins "highest" and the junk cell — unique, count 1 — wins "cheapest",
    # both as a confident `success`. Ties and mixed columns are the same fact:
    # the enumeration does not identify one answer (cold review, M31).
    if any(nums) and not all(nums):
        raise ValueError(
            "enumerated values are only partly numeric "
            f"({sum(n is None for n in nums)} of {len(values)} do not parse as numbers), "
            "so they cannot be compared as numbers or counted as labels")
    if all(nums):
        keyed = [(n[0], v) for n, v in zip(nums, values)]
    else:
        counts = Counter(_clean(v) for v in values)
        keyed = [(counts[_clean(v)], v) for v in values]
    best = (max if want_max else min)(k for k, _ in keyed)
    winners = [v for k, v in keyed if k == best]
    if len({_clean(v) for v in winners}) > 1:
        raise ValueError(
            f"{len(winners)} values tie for {m.group(1)!r} ({sorted(set(winners))}): "
            "the enumeration does not identify one answer")
    return winners[0]


def is_aggregate(task: str) -> bool:
    """Does this task ask which item of a set ranks highest/lowest?

    One regex, two callers: `aggregate_needs_comparison` below (does this
    verdict rest on a comparison that was never made?) and agent.py's
    `plan_gap` (does this plan even contain the comparison?). The second exists
    so the first stops being the only line of defence — a plan caught here never
    runs, so the guard's declared false-refusal cost (D22) is paid on far fewer
    runs than it was.
    """
    return bool(_AGGREGATE.search(task or ""))


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
    #
    # M31 relaxes it in exactly one direction: a trace that CONTAINS an
    # `extract_all` step did enumerate the candidate set, and the comparison
    # over that set was arithmetic (`rank`, above), not a guess — which is the
    # primitive the comment above says the plan vocabulary was missing. The
    # guard stands for every plan that still tries to answer a superlative with
    # a single `extract` — which agent.py's `plan_gap` now rejects before the
    # browser moves, so `verifier-aggregate-superlative-fails-loud` no longer
    # reaches this check at all; what still reaches it is a mid-run replan that
    # dropped the enumeration (`verifier-aggregate-ground-truth-untouched` row 5).
    has_ground_truth = "answer" in expect or "state" in expect
    enumerated = any(s.get("action") == "extract_all" for s in graded)
    if task and not has_ground_truth:
        check("aggregate_needs_comparison", enumerated or not is_aggregate(task),
              "superlative/aggregate question over a set ('which X has the most/least Y') "
              "answered without an `extract_all` step, so nothing enumerated the set the "
              "question ranks over; a layer-1-only verdict cannot tell a right guess from "
              "a wrong one, so it fails loudly rather than passing on unverifiable evidence")

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
