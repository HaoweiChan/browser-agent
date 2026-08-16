"""SemanticTarget -> Playwright locator, tier by tier, plus relocation.

Tiers (docs/evals/failure-taxonomy.md): role+name -> text/label -> stable attrs
-> structural. M1 ships role and text; attrs/structural land with the locator
cache at M4.

`relocation_candidates` is the self-maintenance half: given the target that
just failed and a FRESH accessibility snapshot, it proposes the same semantic
intent expressed at a *different* tier. Pure function — the agent owns the
re-observe and the retry, this owns the rule about which rungs are legitimate.
"""

from .verifier import normalize


class ResolveError(Exception):
    def __init__(self, kind: str, note: str):
        self.kind = kind  # "element-not-found" | "ambiguous-match"
        super().__init__(note)


async def resolve(page, target: dict):
    """Return (locator, tier). Raises ResolveError with a locate subclass.

    `index` (0-based) picks the k-th match instead of demanding uniqueness —
    "the first result" is a real browsing primitive (TC2/TC4), not site
    knowledge. Without it, ambiguity stays a loud locate failure.
    """
    tiers = []
    role, name, text = target.get("role"), target.get("name"), target.get("text")
    index = target.get("index")
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
        n = await loc.count()
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
    # `index` is part of the intent ("the first result"), not part of the tier.
    return [dict(r, index=target["index"]) if target.get("index") is not None else r
            for r in rungs]
