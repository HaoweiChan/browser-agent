"""Mutation catalog — deterministic HTML transforms selected by `?mut=<name>`.

Controlled, reproducible UI breakage instead of waiting for real sites to
change (docs/evals/evaluation-methodology.md).

| mutation             | breaks                | leaves intact                        |
|----------------------|-----------------------|--------------------------------------|
| ids-renamed          | stable-attr tier      | roles, accessible names, visible text |
| button-text-renamed  | text/label tier       | role + accessible name (kept as aria-label) |
| wrapper-nesting      | structural tier       | roles, names, text                   |
| duplicate-labels     | role+name UNIQUENESS  | visible text (each control keeps its own) |
| a11y-stripped        | role tier (controls)  | visible text, ids, list/link roles   |
| element-reordered    | positional `index`    | roles, names, text, `near` proximity |
| render-delayed       | the instant at which the resolver looks | every tier, 3s later |
| overlay-modal        | actionability (click) | every tier — the element resolves fine |

The first three are the B-floor set (M2): each breaks exactly one locator tier,
so an L4 pass is evidence the agent relocated via a *different* tier rather
than got lucky. The last five are M8's B-strong set, and two of them are not
tier breaks at all: `render-delayed` breaks *when* the resolver looks and
`overlay-modal` breaks what it can do once it has looked. They are here because
the test for admission is "does it break a capability a plan stands on", not
"is it a tier" — see ADR-009. `classes-scrambled` fails that test and is
deliberately absent: the resolver has no class tier, so scrambling classes
would change nothing any locator reads.

This module is fixture/eval machinery: it may know the fixtures' own DOM
(CLAUDE.md rule 6) because it is fault injection, never executor input.

**A mutation must break the agent, never the fixture.** `ids-renamed` learned
this the hard way (l4-shop-ids-renamed went red because the fixture's own
script resolved elements by id); `a11y-stripped` inherits it — turning a submit
button into a div would silently disable the fixture's search form, so the
mutation ships a click shim that restores the behaviour a mouse user still has
on a real div-soup site. Every claim in the table above is pinned by
`evals/adversarial/mutation-catalog-integrity.json`.
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


# --- M8 (B-strong) ---------------------------------------------------------
# Admission test for every one of these: does it break a capability a PLAN
# stands on? A mutation that breaks nothing a locator reads is decoration
# (ADR-009), which is why `classes-scrambled` is not in this file.

_BUTTON_OPEN = re.compile(r"<button\b([^>]*)>")
# Flat lists only — non-greedy, so a nested <li> would split at the inner close.
# No fixture nests list items, and the integrity case's order needles would go
# red on the first one that did.
_LI_ROW = re.compile(r"<li\b.*?</li>", re.S)


def duplicate_labels(html: str) -> str:
    """Every button answers to the FIRST button's accessible name.

    Kills uniqueness at the role+name tier without killing the tier: the name
    still resolves, it just resolves to two elements, which is the
    `ambiguous-match` half of the locate class (the half `element-not-found`
    never exercises). Visible text is untouched on purpose — each control keeps
    its own copy, so the text tier is the rung relocation can climb to.
    Real-world shape: a duplicated aria-label on a repeated widget.
    """
    first = _BUTTON.search(html)
    if not first:
        return html
    name = first.group(2).strip()
    return _BUTTON.sub(lambda m: f'{m.group(1)} aria-label="{name}">{m.group(2)}</button>', html)


# A div that was a submit button still submits for a mouse user on a real
# div-soup site, because such sites wire the handler by hand. Without this the
# mutation would break the fixture's forms rather than the agent's role
# dependency — the `ids-renamed` lesson (see the module docstring).
#
# `requestSubmit()`, NOT `dispatchEvent(new Event('submit'))`. The dispatched
# event fires an inline `onsubmit` handler, so it looks correct against
# shop.html's JS-handled search form — and submits nothing at all against
# forms.html's real POST, which was watched red before this line changed
# (case l4-forms-a11y-stripped; l4-shop-a11y-stripped stayed green throughout).
_SUBMIT_SHIM = (
    "<script>document.addEventListener('DOMContentLoaded',function(){"
    "for(const d of document.querySelectorAll('div[type=\"submit\"]'))"
    "d.addEventListener('click',function(){const f=d.closest('form');"
    "if(f)f.requestSubmit();});});</script>"
)


def a11y_stripped(html: str) -> str:
    """Div soup: controls lose their roles, keep their pixels.

    `<button>` -> `<div>`, attributes and visible text intact, so role+name
    finds nothing while the text tier still matches exactly what a human reads.
    Inputs are deliberately NOT stripped: a div can only hold typed text if it
    is contenteditable, which changes what the fixture DOES rather than what it
    exposes, and a mutation that changes behaviour is measuring the fixture.

    This is the fixture twin of a real hostility: quotes.toscrape.com/js
    renders its entire content as span/div, and the accessibility tree the
    planner observes contains none of it (case live-quotes-js-role-tier-blind).
    Cases: l4-shop-a11y-stripped (JS-handled form), l4-forms-a11y-stripped
    (native POST — the one that keeps the shim below honest).
    """
    html = _BUTTON_OPEN.sub(r"<div\1>", html).replace("</button>", "</div>")
    return html + _SUBMIT_SHIM


def element_reordered(html: str) -> str:
    """List rows in reverse document order.

    Breaks `index`, which is not a tier but is load-bearing: two of the three
    live domains reach their answer by counting (`index: 5`, `index: 11`), and
    a positional target has no relocation rung by construction — it names no
    string to relocate *by* (resolver.relocation_candidates). So this mutation
    is the one that does not end in a recovery: it ends in a different,
    confidently-reported element (case l4-shop-element-reordered). `near:`
    survives it, which is the whole argument for `near:` existing
    (l4-shop-element-reordered-near).
    """
    rows = _LI_ROW.findall(html)
    if len(rows) < 2:
        return html
    it = iter(rows[::-1])
    return _LI_ROW.sub(lambda m: next(it), html)


# 3s: long enough that no rung of the relocation ladder can outlast it (the
# whole locate->re-observe->retarget cycle runs in ~0.4s against a loopback
# fixture), short enough that a human watching the page sees it fill in. The
# live twin, quotes.toscrape.com/js-delayed, uses 10s.
_RENDER_DELAY_MS = 3000
_RENDER_DELAY = (
    "<script id='mut-render-delay'>document.addEventListener('DOMContentLoaded',function(){"
    "const el=document.querySelector('ul,ol,table');if(!el)return;"
    "const p=el.parentNode,next=el.nextSibling;el.remove();"
    f"setTimeout(function(){{p.insertBefore(el,next);}},{_RENDER_DELAY_MS});}});</script>"
)


def render_delayed(html: str) -> str:
    """The content list arrives 3s after DOMContentLoaded.

    Breaks no tier — it breaks the *instant* the resolver looks. `resolve()`
    counts matches once, with no wait of any kind, so an element that is merely
    late is indistinguishable from an element that is absent, and the ladder
    re-observes into the same empty page. Kept because "the page was not ready"
    is the commonest real cause of a locate failure on a JS-rendered site, and
    the eval set had no instance of it (case l4-shop-render-delayed).
    """
    return html + _RENDER_DELAY


# `this.parentNode.parentNode` rather than getElementById: the fixture rule
# applies to the mutation's own markup too. Dismissing leaves a checkable trace
# behind, because a click with no checkable consequence is a click the verifier
# fails the run for (verifier.actions_verified) — real cookie/newsletter modals
# usually do leave one (a toast, a preference note).
_OVERLAY = """\
<div id="mut-overlay" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:99">
<div role="dialog" aria-label="Newsletter" style="background:#fff;margin:2em;padding:1em">
<p>Subscribe to our newsletter</p>
<button onclick="var o=this.parentNode.parentNode,n=document.createElement('p');\
n.textContent='Newsletter closed';o.parentNode.insertBefore(n,o);o.remove();">Close</button>
</div></div>"""


def overlay_modal(html: str) -> str:
    """A modal covers the page; every locator still resolves.

    The only mutation here that is not a locate problem at all: the target is
    found, at its usual tier, and then cannot be clicked. Playwright spends the
    full click timeout retrying the hit test and the failure classifies as
    `act` — so this is the mutation that exercises the OTHER recovery family
    (re-observe -> replan), and the one that pins the browser-domain skill's
    claim that overlay interception must not be diagnosed as `locate`
    (case l4-shop-overlay-modal).
    """
    return html + _OVERLAY


MUTATIONS = {
    "ids-renamed": ids_renamed,
    "button-text-renamed": button_text_renamed,
    "wrapper-nesting": wrapper_nesting,
    "duplicate-labels": duplicate_labels,
    "a11y-stripped": a11y_stripped,
    "element-reordered": element_reordered,
    "render-delayed": render_delayed,
    "overlay-modal": overlay_modal,
}


def apply_mutation(html: str, mut: str | None) -> str:
    """Unknown names are a loud error — a silently ignored `?mut=` would turn
    an L4 case into an unmutated pass (CLAUDE.md rule 4)."""
    if not mut:
        return html
    if mut not in MUTATIONS:
        raise KeyError(f"unknown mutation {mut!r}; known: {sorted(MUTATIONS)}")
    return MUTATIONS[mut](html) + _KEEP_QUERY
