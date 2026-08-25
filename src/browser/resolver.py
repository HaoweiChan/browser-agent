"""SemanticTarget -> Playwright locator, tier by tier, plus relocation.

Tiers (docs/evals/failure-taxonomy.md): role+name -> text/label -> stable attrs
-> structural. M1 shipped role and text. `structural` landed at M6 as `near`
(proximity to a visible anchor) — with no locator cache, which the taxonomy had
assumed it would arrive with; `attrs` is still unimplemented.

The taxonomy also describes candidate ranking by "uniqueness × visibility ×
tier prior × cached history". None of that exists here: tiers are tried in
order, a tier wins by resolving to exactly one element (or by `index`/`near`
naming which one, or by a narrowing rung below), and nothing is scored, cached
or checked for visibility.

`relocation_candidates` is the self-maintenance half: given the target that
just failed and a FRESH accessibility snapshot, it proposes the same semantic
intent expressed at a *different* tier. Pure function — the agent owns the
re-observe and the retry, this owns the rule about which rungs are legitimate.

M38 adds NARROWING: N>1 matches is a question the page can often settle, and
six deployment runs died on ambiguity with the answer on screen. Three rungs,
tried only after every tier has been given its chance to resolve uniquely
(a clean single match at a later tier still beats any narrowing at an earlier
one), each one recorded in the trace by name:
  1. `anchor-proximity` — the plan's identity anchor reused as a `near`;
  2. `document-order` — the first match, and ONLY where the choice cannot
     change the answer (see INTERCHANGEABLE_JS);
  3. `near-normalised` / `near-prefix` — the anchor string matched through
     typographic variants, then by its prefix.
None of them is labelled `retry_or_recovery`: nothing failed and no ladder ran,
which is the same ruling the plan lint and M32's drill-down got (specs/001).
"""

import re

from .verifier import normalize

# The whole target schema (specs/001 §TraceStep). Anything else is a plan the
# executor cannot honour, and the executor says so — `near:` spent five
# milestones advertised-but-unimplemented and was dropped without a sound
# (case resolver-unknown-target-key).
TARGET_KEYS = {"role", "name", "text", "near", "index"}

# The accessibility document root, in the spellings a plan or a snapshot can name
# it with: Chromium calls it `WebArea`, `RootWebArea` in other builds. Stripped
# and case-folded, because one of the two writers is a model.
#
# It lives here rather than in agent.py because BOTH of its readers are about
# resolution: `agent.plan_gap` refuses a plan that extracts from it (ADR-024),
# and `relocation_candidates` below refuses to PROPOSE it. `document` is
# deliberately absent — that is an author-supplied role on an in-page container,
# and it resolves; see ADR-024 §1.
DOC_ROOT_ROLES = {"webarea", "rootwebarea"}

# Nearest candidate to an anchor, in DOCUMENT order rather than pixels. Layout
# distance ties on the shape that needs `near` most: a subline whose bounding
# box contains every link in it ("57 points by <a>pg</a>" — live-hn-item1-submitter)
# gives distance 0 to all of them. Document order separates them.
#
# Returns a candidate index, -1 for "no candidate", or AMBIGUOUS. Every rule
# below cost a case that reported a confident wrong answer without it.
NEAREST_JS = """([anchors, cands]) => {
  const all = [...document.querySelectorAll('*')];
  // get_by_text matches a container as well as the element inside it, so keep
  // only the deepest matches. That nesting is what makes a container anchor
  // like HN's <span class=subline> work at all; two matches that do NOT
  // contain one another are a different thing entirely — the anchor string
  // names two places on the page and the plan cannot say which
  // (near-anchor-substring: "Total" also matches "Subtotal").
  const deep = anchors.filter(a => !anchors.some(o => o !== a && a.contains(o)));
  if (deep.length !== 1) return -2;
  const anchor = deep[0], ai = all.indexOf(anchor);

  // A candidate that WRAPS the anchor is not beside it, it holds it — the row
  // or card the value sits in, which is nearer than any neighbour can be and
  // the commonest use of proximity on a listing (near-prefers-the-container).
  // Innermost wins. Only the anchor's own element is excluded outright.
  const holds = cands.map((c, i) => [c, i]).filter(([c]) => c !== anchor && c.contains(anchor));
  if (holds.length) {
    const inner = holds.filter(([c]) => !holds.some(([o]) => o !== c && c.contains(o)));
    return inner[0][1];
  }

  let best = -1, bestD = null, tied = false;
  cands.forEach((c, i) => {
    if (c === anchor || c.contains(anchor)) return;
    const d = Math.abs(all.indexOf(c) - ai);
    if (bestD === null || d < bestD) { best = i; bestD = d; tied = false; }
    else if (d === bestD) tied = true;
  });
  // No tie-break. A product link one element before the price and an "Add to
  // cart" link one element after are equally near, and any rule for choosing
  // between them is a guess the plan did not authorise
  // (near-equidistant-is-ambiguous). Ambiguity is loud everywhere else here.
  return tied ? -2 : best;
}"""
AMBIGUOUS = -2

# Are these candidates interchangeable — can the choice between them change the
# answer? Only if it cannot may the document-order rung pick one. Two halves,
# and each is the whole guard on one tier: a role-tier ambiguity has identical
# roles by construction and is separated by TEXT ({role: link, name: "user
# profile"} over two bylines — resolver-narrows-by-anchor-proximity), a
# text-tier ambiguity has identical text by construction (exact=True) and is
# separated by ROLE (the same "4.7" as a thread score and a footer median —
# resolver-refuses-mixed-roles).
#
# ponytail: `getAttribute('role') || tagName` is not the computed ARIA role —
# a scope-less <th> and a <td> read alike here (support-matrix D29). Upgrade
# path is a computed-role probe per candidate; no case asks for one yet.
INTERCHANGEABLE_JS = """cands => {
  const role = el => el.getAttribute('role') || el.tagName;
  const text = el => (el.innerText === undefined ? (el.textContent || '') : el.innerText)
                       .trim().replace(/\\s+/g, ' ');
  return cands.every(c => role(c) === role(cands[0]) && text(c) === text(cands[0]));
}"""

# Typographic variants of characters a model reliably normalises away when it
# quotes a page back at you. The page is matched, never rewritten: the pattern
# built from these accepts either form on either side (case
# resolver-near-normalises-typography).
_VARIANTS = {'"': '"“”', '“': '"“”', '”': '"“”',
             "'": "'‘’", '‘': "'‘’", '’': "'‘’",
             '-': '-–—', '–': '-–—', '—': '-–—'}
# How much of a long anchor has to survive for the prefix fallback to try it.
# Long enough that a prefix still names one place on a page (and when it does
# not, NEAREST_JS refuses the two matches loudly, as it does for any anchor).
NEAR_PREFIX = 40

# Actions that only READ the page. The narrowing rungs are theirs alone —
# reading one of several matches returns a value, acting on one of them presses
# a control nobody named. See the guard in `resolve` for the whole argument.
READS = {"extract"}

# Does the task ask for MORE THAN ONE thing? Then one of several matches is an
# answer by omission, and the plan should have used `extract_all`.
#
# Three shapes, because a quantifier is only one of the ways English asks for a
# set (PR #42 R4, which walked around the first version with three ordinary
# phrasings): a quantifier, an imperative or request naming a PLURAL NOUN
# ("name the authors", and not "name the author"), and the plural copula ("who
# are the authors"). A trailing `s` is not by itself what separates those two —
# `\w+s` read every singular noun ending in s as plural and refused to narrow
# for "show me the address / the business / the class" (PR #42 R8, case
# resolver-narrows-singular-noun-ending-in-s). The character BEFORE the final s
# carries what can be carried: an English plural of a word ending in `ss` is
# `-sses`, so no plural has `ss` immediately before its final s, and that one
# exclusion is correct in BOTH directions. `u` and `i` were excluded too for a
# round and are not: `the status` and `the menus` both end in `us`, `the
# analysis` and `the taxis` both in `is`, so excluding them stopped recognising
# a whole class of real plurals and answered them from one match (PR #42 R13,
# case resolver-refuses-plural-menus). Separating those needs a lexicon, and
# where no correct rule exists this milestone keeps the OVER-firing: an
# unrecognised plural is a confident wrong answer, a refused narrowing is a
# loud failure, and the two costs are not symmetric. So `the status`, `the
# genius`, `the analysis`, `the lens` and `the news` all read as plural and
# refuse to narrow — declared in docs/support-matrix.md D29. CJK alternatives
# carry NO `\b`: the boundary never matches inside a CJK run, so the whole
# English list was structurally inert on the six ZH cases this repo ships —
# the lesson agent.SCOPE_BLOCK already carries (case screening-word-boundary).
#
# ponytail: still a regex over natural language, the same ceiling as
# agent.SCOPE_BLOCK and verifier._AGGREGATE — widened on phrasings a probe
# actually found, never on synonyms nobody has seen (D21). What it still misses
# is declared in docs/support-matrix.md D29, not left to be discovered.
_PLURAL_ASK = re.compile(
    r"\b(all|every|each|both|list|how many|which ones|names of|who are|what are)\b"
    r"|\b(?:name|list|give|show)(?: me)? the \w*[^\Ws]s\b"
    r"|所有|全部|列出|哪些|每一?[個个]|各[個个]",
    re.IGNORECASE)


def _loose(s: str):
    """`near` string -> a regex that tolerates typography and whitespace."""
    out = []
    for ch in s.strip():
        if ch.isspace():
            out.append(r"\s+")
        elif ch in _VARIANTS:
            out.append("[" + re.escape(_VARIANTS[ch]) + "]")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out), re.IGNORECASE)


class ResolveError(Exception):
    def __init__(self, kind: str, note: str):
        self.kind = kind  # "element-not-found" | "ambiguous-match"
        super().__init__(note)


async def _nearest(page, loc, near: str, *, loose: bool) -> tuple[int | None, str | None]:
    """(index of the match closest to the text `near`, how the anchor matched).

    The index is None if there is no anchor or no candidate, or AMBIGUOUS.
    Proximity to a visible string is a browsing primitive ("the price next to
    this product"), not site knowledge: no selector, no DOM path, nothing the
    page could not tell any reader.

    Four passes, strictest first, and the looser two are M38's rung 3. Exact
    before substring, for the reason the role tier already uses exact=True
    (resolver-substring-name): a sloppy anchor lands on a superstring sibling
    and the run reports the neighbour of the wrong label as its answer. The
    substring fallback stays because a `near` anchor is usually a fragment of a
    longer line — "points by" inside "57 points by pg on Oct 9, 2006".

    Both of those are LITERAL matches, so an anchor the page holds in substance
    but not byte-for-byte misses entirely and reads as "this page does not have
    it" (run e6768ee0: typographic quotes, and a sentence quoted back longer
    than the page renders it). Hence `normalised` — quote/dash variants and
    whitespace runs — and then `prefix`, the head of a long anchor. Order is
    the honesty: the loosest match is only reached when every stricter one
    found nothing, and an ambiguous loose match is still refused by NEAREST_JS.

    `loose` is required and keyword-only, with no default (PR #42 R18). The
    defect R7 named was a narrowing path nobody remembered to gate, and a
    permissive default preserves exactly that failure mode for the next caller:
    it would silently restore the ungated rung 3. Now a call site that forgets
    it does not run. `resolver-narrowing-fails-closed` reads this signature and
    goes red if a default is added back.

    `loose=False` withholds the two M38 passes, leaving `near` exactly as M6
    shipped it. The caller sets it from the same two refusals that gate the
    narrowing rungs, because these passes ARE a narrowing: they resolve anchors
    that used to resolve to nothing, so they turn a loud `locate` failure into
    an element — and the element then answers a plural ask from one of several
    matches, or gets clicked (PR #42 R7, cases
    resolver-refuses-plural-on-a-loose-anchor and
    resolver-refuses-a-click-on-a-loose-anchor). Exact and substring stay
    available to every step: an anchor the page contains is the proximity the
    plan asked for, and Playwright normalises whitespace inside those two by
    itself, which is why an anchor that differs only in spacing is M6 behaviour
    and not this milestone's to gate.
    """
    passes = [("exact", lambda: page.get_by_text(near, exact=True)),
              ("substring", lambda: page.get_by_text(near))]
    if loose:
        passes.append(("normalised", lambda: page.get_by_text(_loose(near))))
        if len(near.strip()) > NEAR_PREFIX:
            passes.append(("prefix", lambda: page.get_by_text(_loose(near.strip()[:NEAR_PREFIX]))))
    cands = await loc.element_handles()
    if not cands:
        return None, None
    for how, build in passes:
        handles = await build().element_handles()
        if handles:
            return await page.evaluate(NEAREST_JS, [handles, cands]), how
    return None, None


async def resolve(page, target: dict, many: bool = False,
                  anchor: str | None = None, task: str = "", action: str = ""):
    """Return (locator, tier, narrowing rung or None). Raises ResolveError.

    `many` is `extract_all`'s resolution: the first tier with ANY match wins and
    the whole match set is returned, because "every author on this page" is a
    question ambiguity is the ANSWER to, not an error. Nothing else changes —
    same tiers, same order, same site-agnostic targets.

    `index` (0-based) picks the k-th match instead of demanding uniqueness —
    "the first result" is a real browsing primitive (TC2/TC4), not site
    knowledge. Without it, ambiguity stays a loud locate failure.

    `near` does the same job semantically: among the matches for a tier, take
    the one closest to a visible anchor string. It resolves the ambiguity a
    positional index resolves by counting, so tables and sublines — where the
    interesting element has no name of its own — stop needing an index.

    `anchor`, `task` and `action` are what the NARROWING rungs read (M38), and
    the policy that reads them lives here rather than in the caller so there is
    one place where "may this ambiguity be settled without asking?" is decided.
    """
    tiers = []
    role, name, text = target.get("role"), target.get("name"), target.get("text")
    index, near = target.get("index"), target.get("near")
    # Frame-scoped resolution (M42, ADR-028). A Playwright locator never
    # crosses a frame boundary, so before this every element inside an iframe
    # was unreachable at every tier -- `no tier resolved`, measured on
    # `fixtures/frames-host.html`, in both modes and regardless of vision. A
    # Frame exposes the same locator API a Page does, so the fix is to build
    # the SAME tiers in each scope rather than to add a tier.
    #
    # Main frame first, and its tiers before any child frame's, so a page with
    # no iframes resolves byte-identically to how it did before M42 and a page
    # with them prefers the document the task landed on. `page.frames[0]` IS
    # the main frame; `page` is used for it so nothing about the existing path
    # changes shape.
    scopes = [page, *(getattr(page, "frames", None) or [page])[1:]]
    # May this run settle an ambiguity the plan left open? Two refusals, and
    # they gate EVERY rung M38 added — the two below and the loosened anchor
    # passes inside `_nearest`, which sit above them in the `near` branch and
    # were ungated for a round (PR #42 R7). The argument for each is at the
    # `if ambiguous:` block below.
    may_narrow = action in READS and not _PLURAL_ASK.search(task or "")
    # exact=True: planner names come from the observation verbatim; substring
    # matching resolved absent targets to superstring siblings and extracted
    # the wrong element as a success (case resolver-substring-name).
    for scope in scopes:
        if role:
            loc = (scope.get_by_role(role, name=name, exact=True) if name
                   else scope.get_by_role(role))
            tiers.append(("role", loc, scope))
        if text:
            tiers.append(("text", scope.get_by_text(text, exact=True), scope))

    ambiguous = None
    for tier, loc, scope in tiers:
        if near is not None:
            # Proximity is a relation between elements, not a property of one,
            # so the winning tier is `structural` however the candidates were
            # gathered — the taxonomy's last-resort rung (failure-taxonomy.md),
            # and the first one any run has ever emitted.
            # `scope`, not `page`: proximity is measured among the anchors and
            # candidates of ONE document. Passing the page would search the main
            # frame for an anchor whose candidates live in a child frame, find
            # none, and report the frame's content as unreachable-by-proximity.
            i, how = await _nearest(scope, loc, near, loose=may_narrow)
            if i == AMBIGUOUS:
                raise ResolveError(
                    "ambiguous-match", f"proximity to {near!r} does not identify one element for {target}")
            if i is not None and i >= 0:
                # A `near` that matched literally is the plan working as
                # written; one that needed loosening is a narrowing and says so.
                return loc.nth(i), "structural", (f"near-{how}" if how in
                                                  ("normalised", "prefix") else None)
            continue
        n = await loc.count()
        if many:
            if n:
                return loc, tier, None
            continue
        if index is not None:
            if n > index:
                return loc.nth(index), tier, None
            continue
        if n == 1:
            return loc, tier, None
        if n > 1 and ambiguous is None:
            ambiguous = (tier, loc, n)

    # --- Narrowing (M38) ----------------------------------------------------
    # Only here, after EVERY tier has been given its chance: a clean single
    # match at a later tier is stronger evidence than a narrowed one at an
    # earlier tier, and narrowing inside the loop would pre-empt it.
    if ambiguous:
        tier, loc, n = ambiguous
        # Two refusals gate BOTH rungs, because both are about whether this
        # ambiguity may be settled at all — not about which candidate wins.
        #
        # 1. READING steps only. Narrowing turns a loud failure into an answer;
        #    on a click or a fill it would turn one into an ACT on a control the
        #    plan did not uniquely name, and every ruling this file carries says
        #    that stays loud (resolver-refuses-narrowing-a-click, and the act
        #    ladder rescues l4-shop-duplicate-labels instead). `near` is exempt
        #    above because the plan asked for proximity there; nothing here was
        #    asked for. `observe` is excluded with the acting verbs: drilling
        #    into the wrong container feeds the planner a subtree nobody asked
        #    about, and it has its own ladder (ADR-020).
        # 2. SINGULAR tasks only. One of several matches is not a worse answer
        #    to a plural ask, it is an answer to a different question — wrong by
        #    omission, and silently so. This test used to live inside rung 2,
        #    which meant a plural ask whose step carried an identity anchor was
        #    answered from the first rung with nothing checking the shape of the
        #    question at all (PR #42 R1, the milestone's own defect:
        #    resolver-refuses-plural-with-anchor). Both are computed once, as
        #    `may_narrow` above, because rung 3 needs them too.
        if not may_narrow:
            raise ResolveError("ambiguous-match", f"{n} matches at tier {tier} for {target}")
        # Rung 1. The identity anchor is a string from the part of the page the
        # task is about, so it is a proximity anchor the plan already carries
        # (runs 349e4839/e08b7627/bcae4fe7/63b9d944: two links named "pg", one
        # of them in the subline the anchor names). Unlike `near` it is not a
        # request for proximity, so an anchor that identifies no single place
        # (AMBIGUOUS) falls through to the next rung instead of raising —
        # loudness belongs to what the plan actually asked for.
        if anchor:
            i, _ = await _nearest(page, loc, anchor, loose=True)
            if i is not None and i >= 0:
                return loc.nth(i), "structural", "anchor-proximity"
        # Rung 2. The first match in document order, and ONLY where that choice
        # cannot change the answer. Four conjuncts, each with a case, because a
        # loose guard here is a silent-wrong-answer generator:
        #   - the plan carried no `index` — true by construction at this point
        #     (an `index` returns above, or moves to the next tier), so it is
        #     not re-tested here;
        #   - the task asks for ONE thing — the shared guard above
        #     (resolver-refuses-plural-wording and its phrasing family);
        #   - the step READS — the shared guard above
        #     (resolver-refuses-narrowing-a-click);
        #   - the matches are interchangeable: same role, same reading
        #     (resolver-refuses-mixed-roles for the role half,
        #     resolver-refuses-different-readings for the text half).
        # Interchangeability gates this rung ONLY. Rung 1 exists to choose
        # between candidates that differ, from evidence the plan carries; a rung
        # that may only pick between identical elements is not a proximity rung
        # at all (PR #42 R1's second half, declined for that reason).
        if await page.evaluate(INTERCHANGEABLE_JS, await loc.element_handles()):
            return loc.first, tier, "document-order"
        raise ResolveError("ambiguous-match", f"{n} matches at tier {tier} for {target}")
    raise ResolveError("element-not-found", f"no tier resolved {target}")


def relocation_candidates(target: dict, obs: dict) -> list[dict]:
    """Rungs for a `locate` failure: the same intent at a DIFFERENT tier.

    A rung that re-runs the strategy that just failed is a retry wearing a
    recovery label (docs/evals/failure-taxonomy.md), so each tier the failed
    target already used is excluded — even when the fresh snapshot would
    happily supply a candidate for it (case relocation-distinct-tier, row 4).

    The intent is carried by the strings the target names itself with. A target
    with neither `name` nor `text` — `{role: link, index: 0}` — has nothing to
    relocate *by*, and gets no rungs: guessing from a role alone is how the
    resolver picked wrong elements before (case resolver-substring-name).
    """
    wanted = [w for w in (target.get("name"), target.get("text")) if w]
    if not wanted:
        return []
    rungs = []
    if not (target.get("role") and target.get("name")):  # role+name tier untried
        seen = {normalize(w) for w in wanted}
        # ...and never the document root. `observe` emits it as element #1 of
        # every observation, named by the page <title>, so a target whose string
        # IS the title matches it first — a rung that resolves nowhere, spending
        # one of the two this ladder has (T-M40-2, relocation-distinct-tier
        # row 5). It is the same node `plan_gap` refuses when a planner names it
        # directly; refusing to invent it here is the other half.
        match = next((e for e in obs.get("elements", [])
                      if e.get("name") and normalize(e["name"]) in seen
                      and str(e.get("role") or "").strip().lower() not in DOC_ROOT_ROLES),
                     None)
        if match:
            rungs.append({"role": match["role"], "name": match["name"]})
    if not target.get("text"):  # text tier untried
        rungs += [{"text": w} for w in wanted]
    # `index` and `near` are part of the intent ("the first result", "the one
    # beside this string"), not part of the tier, so every rung carries them.
    # `near` was dropped here while `index` was kept, which let a rung answer an
    # easier question than the one that failed and report success for it
    # (case relocation-preserves-near).
    intent = {k: target[k] for k in ("index", "near") if target.get(k) is not None}
    return [dict(r, **intent) for r in rungs]
