"""Condensed page observation for the planner (docs/architecture, D7).

The planner must never plan blind: it references only roles/names that exist
in this observation. Kept compact — raw DOM dumps blow token budgets
(browser-domain skill).

M42 widens the REACH of that observation, in the two directions measured blind
on `fixtures/frames-host.html` before the change (ADR-028):

  * an IFRAME's contents were absent entirely. `page.accessibility.snapshot()`
    reports the frame as one node (`Iframe — Source pane`) and stops at its
    boundary, so a value inside it was in no observation at any budget and
    `resolve` raised `no tier resolved` for it in both modes, vision or not.
    Our own sec-10k inspector renders its source pane as an iframe.
  * an open SHADOW ROOT was already in the accessibility tree and already
    resolvable — that half needed no fix and the milestone's premise was wrong
    about it. What was blind was the EVIDENCE: `page.inner_text("body")` does
    not traverse shadow roots, so a correctly read shadow value was failed as
    ungrounded by the verifier, a `text_visible` postcondition over shadow
    content could never hold, and `page_changed` could not see a shadow-only
    mutation. `page_text` below is the one place that is fixed.
"""

import re

SKIP_ROLES = {"generic", "none", "InlineTextBox", "LineBreak", "StaticText", "text",
              "paragraph", "LabelText", "ListMarker"}
MAX_ELEMS = 60
TEXT_HEAD = 300

# The drill-down's text head (M32, ADR-020). Bigger than TEXT_HEAD because the
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
# T-A39-3: an observation is charged PER CONTROL, not per element. 49 sibling
# `option`s under one `combobox` are ONE control, and before this they each took
# a slot out of MAX_ELEMS -- so once ADR-039's settle let the sec-10k
# inspector's committed-fixture select actually PAINT, the page-level
# observation filled several elements before `status — 'doc_status'`, which a
# planner could see the day before.
#
# Options therefore sit in `elements` in document order like everything else,
# but are charged to their own per-control budget rather than to the page's.
# Raising MAX_ELEMS is the fix this repo has refused three times: it moves the
# cliff to the next larger page.
#
# MAX_OPTIONS is a runaway bound, NOT a summary. The first version of this made
# it 8 and still charged options to the page, and that broke the one case here
# that matters most: `intc-2002` is the 20th of 42 options on the live
# inspector, so truncating to 8 made the user's own task unplannable in order to
# buy back a status line. A budget must not hide the thing the task is about.
OPTION_PARENT_ROLES = {"combobox", "listbox", "menu"}
MAX_OPTIONS = 60

# ARIA forbids an author-supplied accessible name on these roles, so Playwright
# computes "" for them however loudly the DOM shouts aria-label. Chromium's
# snapshot is more permissive and reports a name anyway — advertising it would
# hand the planner a target the resolver can never match (case
# observe-name-prohibited-roles). Show the element, hide the unusable name.
NAME_PROHIBITED = {"definition", "term", "code", "emphasis", "strong", "caption",
                   "deletion", "insertion", "mark", "subscript", "superscript", "time"}

# One evaluate per FRAME: the frame's own rendered body text, plus the text of
# every open shadow root inside it. Two things, one round trip, because this
# runs on the hot path -- `attempt` reads the page before and after every
# acting step, so a second evaluate per read is ~1000 extra round trips across
# the `fast` suite (ADR-028, measured before it was merged into one).
#
# `innerText` is deliberately the base: it is what every existing evidence
# window, dump ratio and `text_visible` postcondition was calibrated against
# (ADR-008's ratio, agent.PAGE_TEXT_KEEP), and a switch to `textContent` would
# move all of them at once. The shadow half cannot use it -- a shadow host's
# own `innerText` is "" (measured) and `document.body.innerText` stops at the
# shadow boundary -- so it walks each root's DIRECT children and takes their
# text, skipping the ones the page is not rendering (`checkVisibility`), which
# is what keeps a `hidden` shadow subtree from grounding an answer nobody can
# see. On a page with no shadow root this returns exactly `body.innerText`, so
# every case written before M42 reads the same string it always did.
#
# ponytail: a nested shadow host's text is counted twice (once inside its
# parent root's child, once by the recursion). Harmless for grounding, which
# asks whether a value is present; fix by skipping hosts in the child scan if a
# case ever cares.
PAGE_TEXT_JS = """() => {
  const parts = [document.body ? document.body.innerText : ''];
  // Depth-first over the shadow subtree, skipping any element the page is not
  // rendering AND everything under it. Checking only the root's direct children
  // was the first version and it was structurally inert on the shape shadow DOM
  // actually takes in the wild — one wrapper <div> with hidden panels inside —
  // so hidden text grounded answers, satisfied `text_visible` postconditions
  // and inflated `not_a_dump`'s denominator (cold review 4). Text nodes are
  // read per element rather than via textContent so a hidden descendant cannot
  // ride in on a visible ancestor's text.
  const text = (root, out) => {
    for (const el of root.children) {
      if (el.checkVisibility && !el.checkVisibility()) continue;
      for (const n of el.childNodes) {
        if (n.nodeType === 3 && n.textContent.trim()) out.push(n.textContent.trim());
      }
      text(el, out);
    }
  };
  const walk = (r) => {
    for (const el of r.querySelectorAll('*')) {
      if (!el.shadowRoot) continue;
      const out = [];
      text(el.shadowRoot, out);
      if (out.length) parts.push(out.join(' '));
      walk(el.shadowRoot);
    }
  };
  walk(document);
  return parts.filter(Boolean).join('\\n');
}"""

# One line of Playwright's ARIA snapshot: `- button "Reload source"`,
# `- status "Inventory turnover": 4.82`, `- text: "Document ID:"`.
_ARIA_LINE = re.compile(r'^\s*-\s+([A-Za-z][\w-]*)(?:\s+"((?:[^"\\]|\\.)*)")?')


async def page_text(page, frames: bool = True, bases: dict | None = None) -> str:
    """Everything on the page a reader can read, main frame first.

    The ONE place the system asks what the page says: the evidence window an
    extraction is judged in, `check_state`'s `text_visible`, the before/after
    comparison behind `page_changed`, and the final digest all come through
    here. That is the point -- `page.inner_text("body")` was called from five
    places, each of them blind to iframes and shadow roots in the same way, and
    fixing the one a bug report names leaves the other four broken (the lesson
    `reads_without_acting` already carries).

    Main frame first and in frame order, because `evidence_window` centres on a
    character offset into this string. Frames are read best-effort: one that
    detaches mid-read contributes nothing rather than killing the step, since
    this is evidence capture and the postcondition is the gate.

    `frames=False` reads the main document (and its shadow roots) only. It is
    LOAD-BEARING as of ADR-036: `agent.check_state` calls
    `page_text(scope or page, frames=scope is None)`, so every postcondition on a
    step whose target resolved in the MAIN document — every non-`PAGE_WIDE_STATE`
    step with no acted frame — is read through this branch. A frame scope needs
    no flag (a Frame has no `.frames`), which is why the argument's one caller is
    the main-document half of that ruling. It was written for the before/after
    comparison behind `page_changed`, which as of PR #57 R13 reads every frame
    instead; both hazards below are still true of THAT pipeline, which is what
    keeps them here:

      * frames-BLIND misses a step whose only effect is inside an iframe. That
        is an inspector's source pane, the shape M42 leg (a) exists for, and it
        made the anti-laundering guard refuse a legitimate replan and kill the
        run with a reason asserting as fact that the step changed nothing
        (`replan-after-an-iframe-only-change-is-not-laundering`).
      * frames-AWARE — what `page_changed` now uses — can be flipped true by a
        frame nobody acted on: a third-party iframe with a ticking clock, a
        rotating ad, a chat bubble. That unlatches the same guard in the other
        direction, letting a replan drop a failed action and read the page as
        though it had worked.

    Both costs are declared, which is the part that was missing: the false
    positive was documented and the false negative was not. The second hazard
    has never been reproduced in this repo and the first was, so the evidence
    picks the direction (T-M42-14 carries the repro that would reopen it —
    a fixture with a frame that mutates on its own).

    ponytail: NOT deletable, and no longer deletable-if-T-M42-14-closes-the-
    other-way either. Whichever way T-M42-14 rules on the EVIDENCE pipeline,
    ADR-036 keeps a main-document-only read in `check_state`, so removing the
    argument removes a postcondition's scope. T-M42-14 may take the hazards
    above; it may not take the parameter."""
    parts = []
    sources = getattr(page, "frames", None) or [page]
    for frame in (sources if frames else sources[:1]):
        try:
            parts.append((frame, await frame.evaluate(PAGE_TEXT_JS)))
        except Exception:
            continue
    kept = [(f, t) for f, t in parts if t]
    if bases is None:
        return "\n".join(t for _, t in kept)
    # T-M42-3: where each document STARTS in the string above. `TEXT_OFFSET_JS`
    # walks up to its own frame's `<body>`, so for an element inside an iframe
    # its hint is short by everything concatenated before that frame, and
    # `_closest_occurrence` then picks among duplicate occurrences using an
    # offset that means something else. Returned rather than recomputed by a
    # second pass, because the pass is the expensive part and the caller
    # already needs the text.
    at, out = 0, {}
    for f, t in kept:
        out[f] = at
        at += len(t) + 1  # the "\n" the join inserts
    bases.update(out)
    return "\n".join(t for _, t in kept)


async def _frame_elements(frame, budget: int) -> list[dict]:
    """A CHILD frame's elements, in document order, as this module's {role, name}.

    Playwright's own ARIA snapshot rather than a hand-rolled walker: the roles
    and names are computed by the same engine `get_by_role` matches with, so
    what the observation advertises is what the resolver can reach.

    **The MAIN frame does not get that guarantee, and T-M42-20 is what it cost.**
    Its elements come from `page.accessibility.snapshot()` below, which is
    Chromium's own tree and APPLIES CSS `text-transform` to an accessible name
    where the locator engine does not — so a `<label>` under
    `text-transform: uppercase` is advertised in a form `get_by_role(name=...)`
    could not match at all, until the resolver's name tiers stopped being
    case-sensitive (`resolver._whole_string`). Do not "fix" that by folding the
    case HERE: the observation is what the planner reads and what the page
    renders, and lowering it would hand the model a string the page does not
    show. Two engines, one contract, enforced at the matcher — and pinned by
    `observe-uppercase-label-name-resolves`, which feeds this function's own
    output back into `resolve`.

    This function is used ONLY for child frames -- `page.accessibility.snapshot()`
    cannot reach them
    (it returns None for a cross-frame root, measured) while it remains the
    main frame's observation unchanged, so no case written before M42 sees a
    different element list.
    """
    try:
        snap = await frame.locator("body").aria_snapshot()
    except Exception:
        return []  # a frame can detach, or refuse; it is not this page's failure
    out: list[dict] = []
    for line in snap.splitlines():
        if len(out) >= budget:
            break
        m = _ARIA_LINE.match(line)
        if not m:
            continue
        role, name = m.group(1), (m.group(2) or "").strip()
        if role in SKIP_ROLES:
            continue
        out.append({"role": role, "name": "" if role in NAME_PROHIBITED else name})
    return out


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
    # Drilling INTO the select is the planner asking for its options by name,
    # so it gets the page budget — the same exemption, and the same sentence,
    # as the chrome one above.
    max_options = MAX_OPTIONS if root is None else MAX_ELEMS

    # Elements CHARGED to the page budget. Options sit in `elems` in document
    # order like everything else but are charged to their own control instead,
    # so `len(elems)` and the budget are no longer the same number.
    charged = 0

    def walk(node, in_chrome=False, opts=None):
        nonlocal chrome, charged
        if not node or charged >= MAX_ELEMS:
            return
        role = node.get("role", "")
        name = (node.get("name") or "").strip()
        in_chrome = in_chrome or role in CHROME_ROLES
        if role and role not in SKIP_ROLES:
            # Document order is preserved — only chrome past its sub-budget is
            # dropped, so relocation candidate order is unchanged.
            if in_chrome and chrome >= max_chrome:
                return  # this whole subtree is more navigation; skip it
            if role == "option" and opts is not None:
                if opts[0] >= max_options:
                    return  # this control has already shown what it is
                opts[0] += 1
                elems.append({"role": role, "name": name})
                return  # charged to the control above, not to the page
            elems.append({"role": role, "name": "" if role in NAME_PROHIBITED else name})
            charged += 1
            chrome += in_chrome
        # A one-cell list, not a counter per level: the options are SIBLINGS, so
        # the budget has to be shared across them and reset for the next
        # control — a per-page counter would let one long select silence the
        # second one on the same page.
        if role in OPTION_PARENT_ROLES:
            opts = [0]
        for child in node.get("children") or []:
            walk(child, in_chrome, opts)

    walk(snap)
    # Frame-piercing (M42): a page-level observation continues into every child
    # frame, with whatever is left of the SAME element budget -- an iframe does
    # not buy the page a second one, which is the D7 lesson applied to reach
    # instead of depth. A drill-down (`root is not None`) is scoped to one
    # subtree by construction and is not widened here.
    if root is None:
        for frame in page.frames[1:]:
            if charged >= MAX_ELEMS:
                break
            got = await _frame_elements(frame, MAX_ELEMS - charged)
            elems += got
            charged += len(got)
    return {
        "url": page.url,
        "title": await page.title(),
        "elements": elems,
        "text_head": (await (root.inner_text() if root is not None
                             else page_text(page)))[:text_head],
    }


def render(obs: dict) -> str:
    lines = [f"URL: {obs['url']}", f"Title: {obs['title']}", "Elements (role — name):"]
    lines += [f"- {e['role']} — {e['name']!r}" for e in obs["elements"]]
    lines += ["Page text (head):", obs["text_head"]]
    # M43 (ADR-035): the text and the image must agree about what was provided.
    # Only loop-mode observations ever carry the key, so mode B's rendered
    # prompt is byte-identical to before; the frame matters because only a
    # viewport frame arms `click_at`, and the model is told which it has.
    if obs.get("screenshot"):
        lines.append(f"Screenshot: a {obs.get('screenshot_frame', 'viewport')} screenshot "
                     "of this view is attached as an image.")
    return "\n".join(lines)
