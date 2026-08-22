"""Condensed page observation for the planner (docs/architecture, D7).

The planner must never plan blind: it references only roles/names that exist
in this observation. Kept compact — raw DOM dumps blow token budgets
(browser-domain skill).
"""

SKIP_ROLES = {"generic", "none", "InlineTextBox", "LineBreak", "StaticText", "text",
              "paragraph", "LabelText", "ListMarker"}
MAX_ELEMS = 60
TEXT_HEAD = 300

# The drill-down's text head (M32, ADR-019). Bigger than TEXT_HEAD because the
# whole point of a scoped observation is to disclose what the capped page-level
# one could not: probe #4/#5/#7 (docs/analysis.md §8a-2) each had the answer
# verbatim in page text the planner was never shown. Bounded, not unbounded:
# 1,500 characters is ~375 tokens against a measured ~1,440-token planning call
# (`cd7121fc`, `734d3d1f`), and it is a SUBTREE's text, not the page's.
# Held by `observe-drill-text-head-reaches-past-300`: reverting this to 300
# turns that case red, because the string it grades sits at character 585 of the
# drilled subtree's text and in no observation's element list at any budget.
DRILL_TEXT_HEAD = 1_500

# Chrome gets a sub-budget of the total. A real site opens with a banner and a
# category sidebar large enough to spend the WHOLE budget before any content is
# reached: books.toscrape.com's Travel listing observed as 60 elements of
# navigation, ending mid-sidebar, with none of its twenty products included —
# the planner blind about the only part of the page the task was about (case
# observe-content-survives-chrome, found by adding the first live domain).
# Raising MAX_ELEMS is not the fix: it moves the cliff to the next larger site
# and spends planner tokens on navigation nobody asked about.
CHROME_ROLES = {"banner", "navigation", "complementary", "contentinfo", "search"}
MAX_CHROME = 20

# ARIA forbids an author-supplied accessible name on these roles, so Playwright
# computes "" for them however loudly the DOM shouts aria-label. Chromium's
# snapshot is more permissive and reports a name anyway — advertising it would
# hand the planner a target the resolver can never match (case
# observe-name-prohibited-roles). Show the element, hide the unusable name.
NAME_PROHIBITED = {"definition", "term", "code", "emphasis", "strong", "caption",
                   "deletion", "insertion", "mark", "subscript", "superscript", "time"}


async def observe(page, root=None, text_head: int = TEXT_HEAD) -> dict:
    """The page as the planner sees it, or — with `root` — one subtree of it.

    `root` is a resolved Locator (M32): the drill-down re-runs this walk scoped
    to that element with the WHOLE MAX_ELEMS budget spent inside it and a longer
    text head, which is the only difference between the two calls. There is no
    second observation format and no second channel to the planner: the scoped
    result travels the same observation+note path a replan already uses, so
    every downstream consumer (render, the replanner, relocation candidates)
    reads it unchanged.
    """
    # interesting_only=False: Chromium prunes empty containers (e.g. a blank
    # <output role=status>) from the default tree; the planner must still see
    # them to target where content will appear.
    handle = await root.element_handle() if root is not None else None
    snap = await page.accessibility.snapshot(interesting_only=False, root=handle)
    elems: list[dict] = []

    chrome = 0
    # The chrome sub-budget answers "did anyone ask for this navigation?", and a
    # drill-down answers it: the planner named this container. Left at
    # MAX_CHROME, a drill into a landmark — a mega-nav, a footer, a category
    # sidebar, the commonest "container I can see but whose contents I cannot"
    # there is — silently returned 20 elements while the replan note told the
    # planner it had the subtree entire (M32 cold review, finding 2; case
    # observe-drill-into-chrome-gets-the-page-budget). A page-level observation
    # is unchanged: nobody asked for that navigation, and
    # observe-content-survives-chrome still holds it at 20.
    max_chrome = MAX_CHROME if root is None else MAX_ELEMS

    def walk(node, in_chrome=False):
        nonlocal chrome
        if not node or len(elems) >= MAX_ELEMS:
            return
        role = node.get("role", "")
        name = (node.get("name") or "").strip()
        in_chrome = in_chrome or role in CHROME_ROLES
        if role and role not in SKIP_ROLES:
            # Document order is preserved — only chrome past its sub-budget is
            # dropped, so relocation candidate order is unchanged.
            if in_chrome and chrome >= max_chrome:
                return  # this whole subtree is more navigation; skip it
            elems.append({"role": role, "name": "" if role in NAME_PROHIBITED else name})
            chrome += in_chrome
        for child in node.get("children") or []:
            walk(child, in_chrome)

    walk(snap)
    return {
        "url": page.url,
        "title": await page.title(),
        "elements": elems,
        "text_head": (await (root.inner_text() if root is not None
                             else page.inner_text("body")))[:text_head],
    }


def render(obs: dict) -> str:
    lines = [f"URL: {obs['url']}", f"Title: {obs['title']}", "Elements (role — name):"]
    lines += [f"- {e['role']} — {e['name']!r}" for e in obs["elements"]]
    lines += ["Page text (head):", obs["text_head"]]
    return "\n".join(lines)
