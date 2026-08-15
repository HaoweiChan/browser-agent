"""Condensed page observation for the planner (docs/architecture, D7).

The planner must never plan blind: it references only roles/names that exist
in this observation. Kept compact — raw DOM dumps blow token budgets
(browser-domain skill).
"""

SKIP_ROLES = {"generic", "none", "InlineTextBox", "LineBreak", "StaticText", "text",
              "paragraph", "LabelText", "ListMarker"}
MAX_ELEMS = 60
TEXT_HEAD = 300

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

    def walk(node):
        if not node or len(elems) >= MAX_ELEMS:
            return
        role = node.get("role", "")
        name = (node.get("name") or "").strip()
        if role and role not in SKIP_ROLES:
            elems.append({"role": role, "name": "" if role in NAME_PROHIBITED else name})
        for child in node.get("children") or []:
            walk(child)

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
