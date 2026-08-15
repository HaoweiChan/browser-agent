"""SemanticTarget -> Playwright locator, tier by tier.

Tiers (docs/evals/failure-taxonomy.md): role+name -> text/label -> stable attrs
-> structural. M1 ships role and text; attrs/structural land with the locator
cache at M4.
"""


class ResolveError(Exception):
    def __init__(self, kind: str, note: str):
        self.kind = kind  # "element-not-found" | "ambiguous-match"
        super().__init__(note)


async def resolve(page, target: dict):
    """Return (locator, tier). Raises ResolveError with a locate subclass."""
    tiers = []
    role, name, text = target.get("role"), target.get("name"), target.get("text")
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
        if n == 1:
            return loc, tier
        if n > 1 and ambiguous is None:
            ambiguous = (tier, n)

    if ambiguous:
        raise ResolveError(
            "ambiguous-match", f"{ambiguous[1]} matches at tier {ambiguous[0]} for {target}"
        )
    raise ResolveError("element-not-found", f"no tier resolved {target}")
