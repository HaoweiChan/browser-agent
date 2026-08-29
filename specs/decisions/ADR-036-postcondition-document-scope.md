# ADR-036: a postcondition is checked in the document its action touched

Date: 2026-08-28
Status: accepted

**Ruling**: `check_state`'s scoped predicates — `text_visible` and `role_visible` — are evaluated in exactly ONE **document**: the one `resolve` returned the step's target from. The trace records its frame URL as `resolved.scope`; for iframe actions the executor also plants a one-use marker in that document before acting. A same-frame navigation destroys the marker even when the `Frame` object remains attached and its URL remains `about:srcdoc`, so the successor returns a null, unverifiable postcondition rather than certifying the earlier action (T-M42-14 amendment, 2026-08-29). A step whose action resolved no target is scoped to the main document. Three postcondition sites stay page-wide by nature: `url_contains`, and the whole `expected_state` of `navigate`/`go_back` and `wait_for`. ADR-028 §7 is amended in place to admit `resolved.scope`; the exact marker remains internal because it is ephemeral verification state, not durable evidence.
**Because**: `text_visible` reading `observe.page_text(page)` (every frame, every open shadow root) and `role_visible` iterating `[page, *frames[1:]]` are what made an iframe'd page verifiable at all (ADR-028 item 4) — and both meant a click's `expected_state` could be earned by an element in a completely unrelated document: a consent iframe, a chat widget, a `display:none` tracking iframe (still in `page.frames`, still evaluable). The step then recorded `postcondition_ok: true` for an action that did nothing, which is the one thing a postcondition exists to make impossible — measured, not imagined: the T-M42-11 repro on the committed `frames-host.html` ran `press "Shift"` (touches only the main document) asserting a string that exists only inside the iframe, and got `postcondition_ok: true`, `status success`, answer delivered on the strength of a no-op's "verified" state change.
**T-M42-14 enforcement**: `successor-document-cannot-verify-a-noop` was watched red as `status success` with `trace_postconditions [true, true, null]` and an answer delivered from the replacement document. It now records the click postcondition as null, notes that the resolved frame document was replaced, and ends `failure:semantic` with no answer. The detached-frame, legitimate iframe-effect, main-document and page-wide-wait cases remain controls.
**Enforced by**: `postcondition-decoy-iframe-cannot-satisfy-text-visible` and `postcondition-decoy-iframe-cannot-satisfy-role-visible` (one per predicate, because the two keys are separate code paths and a half-fix would leave one standing — both watched red as `status success`, `trace_postconditions [true, true, null]`), `resolved-scope-names-the-acted-document` (the positive twin: a frame-scoped click verifies in its OWN document, and the trace field is asserted per step), `main-document-click-cannot-verify-a-frame-only-effect` (the ruling's PRICE, on `frames-swap.html`: the main-document click's postcondition goes false while `page_changed` is true, and the `wait_for` carve-out is the recovery — red on the pre-ADR-036 mechanism, which reports plain success) , `postcondition-scope-detached-by-its-own-action` (§4: the acted frame removed by its own click, watched red at `failure:act`, and re-expected in round 2 — the shape now ends `failure:semantic` because a detached scope is UNVERIFIABLE) and `detached-scope-cannot-be-verified-by-a-decoy` (§4's own hazard, the round-1 fallback's falsification: a no-op click in a widget the PAGE re-mounts on a timer, watched red as `status success`, `trace_postconditions [true, true, null]`, answer delivered) — with `shadow-dom-value-is-reachable-and-grounded`, `replan-after-an-iframe-only-change-is-not-laundering` and the `live-sec10k-authored-wait-*` pair pinning that the main document's shadow roots, the frame-effect replan path and page-wide `navigate` waits are all untouched.

---

## Context

M42 (ADR-028 item 4) pierced iframes in observation, resolution and evidence,
because before it an iframe's contents were structurally invisible and
unresolvable in both modes. Two of the widened reads sit under `check_state`:

* `text_visible` — `want in page_text(page)`, every frame plus every open
  shadow root;
* `role_visible` — a `get_by_role` probe over `[page, *frames[1:]]`.

M42's own cold review (finding 4, HIGH) named the cost and T-M42-4 accepted it
deliberately: an `expected_state` can now be satisfied by a document the action
never touched. It was logged rather than fixed because the fix is a scoping
decision with two defensible answers — a `wait_for` on a page that paints into
an iframe *legitimately* wants the frame, and `url_contains` is page-level by
nature — and because the mechanism needs a trace field ADR-028 §7 forbade.

T-M42-11 (PR #57 R10) then falsified the block's "nothing offline can see it"
sentence: the hazard is demonstrable on `frames-host.html` as committed, with a
two-line stub plan. That repro is this ADR's red-first case, verbatim.

## Decision

### 1. Scope, per postcondition site

| site | scope | why |
|---|---|---|
| `text_visible` / `role_visible` on a step whose target resolved | the DOCUMENT `resolve` returned from | the frame scopes the read; for an iframe action a one-use marker proves the same document is still loaded, otherwise the postcondition is null (T-M42-14, §4) |
| `text_visible` / `role_visible` on a step with no resolved target | the main document | an un-focused key press or window scroll lands on the top-level document; nothing named a frame |
| any predicate on `wait_for` | the whole page, every frame | a wait performs nothing, so there is no acted document — it is an authored assertion about where the page will paint, and frames are a place pages paint (the carve-out T-M42-4 itself names) |
| any predicate on `navigate` / `go_back` | the whole page, every frame | the action loaded every document on the page, frames included; `live-sec10k-authored-wait-reaches-the-doc-status` authors exactly this shape |
| `url_contains`, on anything | `page.url` | one address bar; a frame's URL is not what a plan means by "the URL" |
| any predicate whose acted document has DETACHED by the time it is read | nothing — the postcondition is **null**, unverifiable | the document the assertion was about is gone, so there is nothing left to ask and nothing else may answer in its place; §4 |

The evidence pipeline is deliberately untouched: `page_text(page)` remains the
single all-frames evidence read behind extraction windows, `grounded`,
`page_changed` and the digest. This ADR scopes what a postcondition *asserts*,
not what the run can *see* — narrowing evidence was T-M42-14's rejected
direction and stays rejected there.

### 2. The trace records the resolving document: `resolved.scope`

`resolve` now returns the scope (Page or Frame) it resolved in, and the
executor records its URL as `resolved.scope`, beside `tier`. Two consumers:

* `check_state`, this ADR's mechanism — the scoped predicates are evaluated in
  that frame (`page_text(scope, frames=False)`; a `get_by_role` probe on that
  scope alone). For an iframe action with a document-scoped expectation, the
  executor also plants a unique global marker before acting and requires it on
  every settle pass. This supplies exact document identity where Frame identity
  and URL cannot (T-M42-14).
* `resolved.scope` remains reader-facing provenance, not exact identity. The
  one-use marker is intentionally internal; replacement is disclosed in the
  trace note.

A URL, not a frame index: frames attach and detach, and the URL is the only
identity the trace can carry that a reader can resolve later. Two same-URL
documents are indistinguishable in the trace, so exact identity is enforced by
the internal marker; nothing selects a frame *by* the recorded scope.

### 3. ADR-028 §7 amendment

§7 ruled "the trace gains no fields" so that loop mode could not grow a second
evidence pipeline. `resolved.scope` is not a loop-only key and not a second
pipeline: it is written by the one resolver both modes share, inside the
existing `resolved` object, for every step that resolves in either mode.
`contract-trace-schema` / `contract-trace-schema-loop-mode` grade the
TraceStep's top-level keys and stay byte-identical in what they assert. The
amendment is recorded in ADR-028 §7 itself, dated 2026-08-28, scoped to this
one key inside `resolved`.

### 4. A scope that is GONE makes the postcondition unverifiable, not page-wide

*Amended 2026-08-28 (PR #66 R6). The first ruling — fall back to page-wide —
is struck below with the argument that carried it, because that argument was
false.*

An acted document can be removed while its own step runs: an SPA re-mounting an
embedded widget after an in-frame click, an in-frame link with `target="_top"`,
or a host that re-renders that panel on a poll of its own. The first cut of §1
read that case silently wrong — `page_text`'s per-frame read is
`except Exception: continue`, so a detached Frame contributes `""` and
`text_visible` is false; `role_visible` raises on the detached Frame and
`check_state`'s `except Exception: pass` swallows it — so the postcondition
burned the full settle budget and returned False for an action that may well
have WORKED. A false negative this ADR never declared, and the shape M44's live
target has (PR #66 R3, `postcondition-scope-detached-by-its-own-action`,
watched red at `failure:act` in 2.55s).

`check_state` therefore re-reads `Frame.is_detached()` on every settle pass —
after evaluating the predicates, so an assertion that went true while the
document still existed still returns True — and returns **None** once it is
true: the postcondition was not checked, because the thing it was about is
gone. `verifier.STATE_CHANGING` already rules on what that means for a click,
a press or a `go_back`: a null postcondition on a state-changing verb is not a
pass, it fails the run `failure:semantic` with *state-changing step(s) [N]
carried no checkable postcondition*, and INV-2 drops the answer. Loud, and
accurate — the run neither claims the action worked nor accuses it of failing.

~~`check_state` falls back to page-wide once it is true. Fallback rather than a
loud failure, and the reason is what the decoy hazard actually is: a NO-OP
scoring true off an unrelated document. A detach is positive evidence the
action did something — a `press "Shift"` detaches nothing — so the case this
ADR exists to refuse cannot arrive through this door.~~ Struck 2026-08-28.
The middle sentence is the false one: a detach is evidence that SOMETHING
re-rendered, not that the action did anything, and pages re-render on timers.
PR #66 R6 built the counter-example on this tree —
`frames-decoy-detach.html`: a decoy iframe reading `Filing loaded`, a widget
iframe whose `Refresh` button is bound to an empty handler, and a `setTimeout`
scheduled at LOAD that empties the widget's container. A literal no-op click
resolved in the widget, the page's own timer detached it, the fallback read
every frame, and the decoy earned `postcondition_ok: true` — §1's hazard,
verbatim, through the door §4 opened (`detached-scope-cannot-be-verified-by-a-decoy`,
watched red as `status success`, `trace_postconditions [true, true, null]`,
answer delivered).

**Successor-document amendment (T-M42-14, 2026-08-29).** `is_detached()` tests
the Frame object, not its document. `successor-document-cannot-verify-a-noop`
demonstrated the gap on `frames-renav-decoy.html`: a page-owned timer replaced
the iframe document after a literal no-op click, the successor supplied
`Filing loaded`, and the run returned `NIMBUS-10K-2025` as success. The executor
now plants a one-use marker before an iframe action and checks it before every
document predicate. Replacement returns null and adds `postcondition
unverifiable: resolved frame document was replaced` to the trace. The verifier
then fails a state-changing step loudly and INV-2 removes the answer.

The safety rule has a declared price: a legitimate iframe action that itself
navigates the same frame cannot verify that action using successor-document
text. It must author the page-wide `wait_for` carve-out after the action. Main
document navigation semantics are unchanged.

One residual remains unrelated to document identity:
* **A null is loud only on a state-changing verb** (PR #66 R14).
  `verifier.STATE_CHANGING` is `{click, press, go_back}`, so those three fail
  the run `failure:semantic` on a null. `fill`, `select_option` and `scroll`
  never reach it — they set `postcondition_ok` True by readback before the
  check. Everything else — `extract`, `extract_all`, `observe` — records the
  null and the run CONTINUES: a step that authored an `expected_state` whose
  acted frame then died is recorded unverified rather than failed, and
  `no_failed_postcondition` does not see a null. That is the pre-existing
  meaning of null (INV: "None is not True"), not something this amendment
  introduced, but §4 asserted "loud" without the qualifier for one round and
  the qualifier is the honest half.

The same conservative price applies to detach and replacement: a legitimate
re-mount cannot verify itself with a document-scoped predicate, and the honest
plan authors the page-wide `wait_for` carve-out. The
`postcondition-scope-detached-by-its-own-action` and successor-document cases
measure each branch instead of guessing which actor caused the lifecycle event.

One marker guard in `check_state`, not one per predicate: both keys and both
modes route through it, and a guard on only the path a report names would leave
its sibling broken.

## Alternatives rejected

* **Scope everything, `wait_for` included** — kills the S1/S4 shape M42 exists
  for: a page that paints its result into an iframe could never be waited on,
  and mode B's only wait primitive would be blind exactly where the milestone
  bought sight.
* **Scope nothing, log the hazard** — was T-M42-4's interim position, and
  T-M42-11 demonstrated the wrong-success on a committed fixture. A
  postcondition that a decoy document can satisfy is not a postcondition.
* **Scope the evidence reads too** — reopens PR #57 R13's false negative
  (`replan-after-an-iframe-only-change-is-not-laundering`) and is T-M42-14's
  question, which closes on its own repro or not at all.

## Consequences

* A click in the main document whose only effect is inside a frame can no
  longer verify itself with `text_visible` naming the frame's text — the
  honest plan authors a `wait_for` for that (the carve-out exists precisely so
  this stays expressible). **Measured, not asserted**:
  `main-document-click-cannot-verify-a-frame-only-effect` authors exactly that
  shape on `frames-swap.html` and pins the whole ruling in one trace — the
  click resolves in the main document, `page_changed` is true because the frame
  really did change, `postcondition_ok` is **false** anyway, and the replan's
  page-wide `wait_for` then verifies the frame and the `extract` resolves in
  `about:srcdoc`. Run against the pre-ADR-036 mechanism the same case is red on
  `recovery`, `replans`, `trace_postconditions` and `resolved_scopes` at once,
  with `status success` and the right answer — page-wide, the click's
  postcondition is satisfied by the frame and there is no failure at all. So
  the price of this ruling is one extra replan on a legitimate frame-effect
  click, and that price is now a number in the ledger rather than a sentence
  here. (This bullet used to say "No committed case authored that shape";
  PR #66 R2 authored it — the sentence was a declared limitation nothing could
  go red on, and this repo's history with those is three-for-three.)
* An acted document that is gone makes its step's postcondition null (§4), so a
  page that re-mounts what the step acted in cannot verify that step with a
  document-scoped predicate at all — it fails `failure:semantic` unless the
  plan authors the `wait_for` carve-out. That is the second price this ruling
  charges, and it is charged deliberately: the alternative, page-wide, was
  ~~declared rather than guarded further~~ shipped for one round and falsified
  inside it. Any detach reopens §1's hazard in full when the fallback is
  page-wide — not a narrower cousin of it, the same thing: a no-op click, a
  frame the PAGE detached, an unrelated decoy iframe supplying the predicate,
  `postcondition_ok: true`. The sentence that stood here — "a no-op detaches
  nothing" — was wrong about who does the detaching (PR #66 R6,
  `detached-scope-cannot-be-verified-by-a-decoy`, the fixture committed). The
  T-M42-14 closes the same-frame replacement branch with a one-use marker;
  detached frames remain null because there is no document left to identify.
* A targetless `press` is now verifiable only against the main document. A
  plan that presses a key INTO a frame's control resolves a target in that
  frame and is scoped there — unchanged.
* `resolved.scope` appears on every resolving step in both modes; steps that
  resolve nothing keep `resolved: null` (or `resolved.scope` absent — the
  schema cases pin the top level, `resolved-scope-names-the-acted-document`
  pins the field).
