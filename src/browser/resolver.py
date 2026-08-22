"""SemanticTarget -> Playwright locator, tier by tier, plus relocation.

Tiers (docs/evals/failure-taxonomy.md): role+name -> text/label -> stable attrs
-> structural. M1 shipped role and text. `structural` landed at M6 as `near`
(proximity to a visible anchor) — with no locator cache, which the taxonomy had
assumed it would arrive with; `attrs` is still unimplemented.

The taxonomy also describes candidate ranking by "uniqueness × visibility ×
tier prior × cached history". None of that exists here: tiers are tried in
order, a tier wins by resolving to exactly one element (or by `index`/`near`
naming which one), and nothing is scored, cached or checked for visibility.

`relocation_candidates` is the self-maintenance half: given the target that
just failed and a FRESH accessibility snapshot, it proposes the same semantic
intent expressed at a *different* tier. Pure function — the agent owns the
re-observe and the retry, this owns the rule about which rungs are legitimate.
"""

from .verifier import normalize

# The whole target schema (specs/001 §TraceStep). Anything else is a plan the
# executor cannot honour, and the executor says so — `near:` spent five
# milestones advertised-but-unimplemented and was dropped without a sound
# (case resolver-unknown-target-key).
TARGET_KEYS = {"role", "name", "text", "near", "index"}

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


class ResolveError(Exception):
    def __init__(self, kind: str, note: str):
        self.kind = kind  # "element-not-found" | "ambiguous-match"
        super().__init__(note)


async def _nearest(page, loc, near: str) -> int | None:
    """Index of the match closest to the text `near`, None if there is no anchor
    or no candidate, or AMBIGUOUS. Proximity to a visible string is a browsing
    primitive ("the price next to this product"), not site knowledge: no
    selector, no DOM path, nothing the page could not tell any reader.

    Exact before substring, for the reason the role tier already uses exact=True
    (resolver-substring-name): a sloppy anchor lands on a superstring sibling
    and the run reports the neighbour of the wrong label as its answer. The
    substring fallback stays because a `near` anchor is usually a fragment of a
    longer line — "points by" inside "57 points by pg on Oct 9, 2006".
    """
    anchors = page.get_by_text(near, exact=True)
    if not await anchors.count():
        anchors = page.get_by_text(near)
    handles = await anchors.element_handles()
    cands = await loc.element_handles()
    if not handles or not cands:
        return None
    return await page.evaluate(NEAREST_JS, [handles, cands])


async def resolve(page, target: dict, many: bool = False):
    """Return (locator, tier). Raises ResolveError with a locate subclass.

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
    """
    tiers = []
    role, name, text = target.get("role"), target.get("name"), target.get("text")
    index, near = target.get("index"), target.get("near")
    # exact=True: planner names come from the observation verbatim; substring
    # matching resolved absent targets to superstring siblings and extracted
    # the wrong element as a success (case resolver-substring-name).
    if role:
        loc = page.get_by_role(role, name=name, exact=True) if name else page.get_by_role(role)
        tiers.append(("role", loc))
    if text:
        tiers.append(("text", page.get_by_text(text, exact=True)))

    ambiguous = None
    for tier, loc in tiers:
        if near is not None:
            # Proximity is a relation between elements, not a property of one,
            # so the winning tier is `structural` however the candidates were
            # gathered — the taxonomy's last-resort rung (failure-taxonomy.md),
            # and the first one any run has ever emitted.
            i = await _nearest(page, loc, near)
            if i == AMBIGUOUS:
                raise ResolveError(
                    "ambiguous-match", f"proximity to {near!r} does not identify one element for {target}")
            if i is not None and i >= 0:
                return loc.nth(i), "structural"
            continue
        n = await loc.count()
        if many:
            if n:
                return loc, tier
            continue
        if index is not None:
            if n > index:
                return loc.nth(index), tier
            continue
        if n == 1:
            return loc, tier
        if n > 1 and ambiguous is None:
            ambiguous = (tier, n)

    if ambiguous:
        raise ResolveError(
            "ambiguous-match", f"{ambiguous[1]} matches at tier {ambiguous[0]} for {target}"
        )
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
        match = next((e for e in obs.get("elements", [])
                      if e.get("name") and normalize(e["name"]) in seen), None)
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
