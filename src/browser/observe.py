"""Condensed page observation for the planner (docs/architecture, D7).

The planner must never plan blind: it references only roles/names that exist
in this observation. Kept compact — raw DOM dumps blow token budgets
(browser-domain skill).
"""

SKIP_ROLES = {"generic", "none", "InlineTextBox", "LineBreak", "StaticText", "text",
              "paragraph", "LabelText", "ListMarker"}
MAX_ELEMS = 60
TEXT_HEAD = 300

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


async def observe(page) -> dict:
    # interesting_only=False: Chromium prunes empty containers (e.g. a blank
    # <output role=status>) from the default tree; the planner must still see
    # them to target where content will appear.
    snap = await page.accessibility.snapshot(interesting_only=False)
    elems: list[dict] = []

    chrome = 0

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
            if in_chrome and chrome >= MAX_CHROME:
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
        "text_head": (await page.inner_text("body"))[:TEXT_HEAD],
    }


def render(obs: dict) -> str:
    lines = [f"URL: {obs['url']}", f"Title: {obs['title']}", "Elements (role — name):"]
    lines += [f"- {e['role']} — {e['name']!r}" for e in obs["elements"]]
    lines += ["Page text (head):", obs["text_head"]]
    return "\n".join(lines)
