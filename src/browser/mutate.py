"""Mutation catalog — deterministic HTML transforms selected by `?mut=<name>`.

Controlled, reproducible UI breakage instead of waiting for real sites to
change (docs/evals/evaluation-methodology.md). Each B-floor mutation is built
to break **exactly one** locator tier, so an L4 pass is evidence that the
agent relocated via a *different* tier — not that it got lucky.

| mutation             | breaks tier   | leaves intact                          |
|----------------------|---------------|----------------------------------------|
| ids-renamed          | stable attrs  | roles, accessible names, visible text  |
| button-text-renamed  | text/label    | role + accessible name (kept as aria-label) |
| wrapper-nesting      | structural    | roles, names, text                     |

This module is fixture/eval machinery: it may know the fixtures' own DOM
(CLAUDE.md rule 6) because it is fault injection, never executor input.
"""

import re

# Stable-attr tier only. `name=` is deliberately excluded — renaming form field
# names would break the POST payload, i.e. the fixture rather than the locator.
_ATTRS = re.compile(r'\b(id|for|data-testid)="([^"]*)"')
_BUTTON = re.compile(r"(<button\b[^>]*)>([^<]*)</button>")
_LI = re.compile(r"(<li\b[^>]*>)")
_BLOCK = re.compile(r"(<(?:ul|ol|form)\b[^>]*>)")

# The visible copy changes; the accessible name does not. Real relabelling
# usually moves both, but then no tier survives and the case would only prove
# the agent gives up — this variant isolates the text tier, which is the point.
RELABEL = {
    "Search": "Find",
    "Sort by price (low to high)": "Cheapest first",
    "Submit enquiry": "Send message",
    "Reveal": "Show",
}

# Relative links drop the query string, so a mutated run would silently fall
# back to unmutated detail pages. Injected only when a mutation is active.
_KEEP_QUERY = (
    "<script>document.addEventListener('DOMContentLoaded',function(){"
    "for(const a of document.querySelectorAll('a[href]'))"
    "if(!a.href.includes('?'))a.href+=location.search;});</script>"
)


def ids_renamed(html: str) -> str:
    return _ATTRS.sub(lambda m: f'{m.group(1)}="{m.group(2)}-x7"', html)


def button_text_renamed(html: str) -> str:
    def sub(m):
        head, text = m.group(1), m.group(2).strip()
        new = RELABEL.get(text)
        if not new:
            return m.group(0)
        return f'{head} aria-label="{text}">{new}</button>'

    return _BUTTON.sub(sub, html)


def wrapper_nesting(html: str) -> str:
    html = _LI.sub(r'\1<div class="w-a"><div class="w-b">', html).replace(
        "</li>", "</div></div></li>"
    )
    return _BLOCK.sub(r'<div class="w-outer">\1', html).replace(
        "</ul>", "</ul></div>").replace("</ol>", "</ol></div>").replace(
        "</form>", "</form></div>")


MUTATIONS = {
    "ids-renamed": ids_renamed,
    "button-text-renamed": button_text_renamed,
    "wrapper-nesting": wrapper_nesting,
}


def apply_mutation(html: str, mut: str | None) -> str:
    """Unknown names are a loud error — a silently ignored `?mut=` would turn
    an L4 case into an unmutated pass (CLAUDE.md rule 4)."""
    if not mut:
        return html
    if mut not in MUTATIONS:
        raise KeyError(f"unknown mutation {mut!r}; known: {sorted(MUTATIONS)}")
    return MUTATIONS[mut](html) + _KEEP_QUERY
