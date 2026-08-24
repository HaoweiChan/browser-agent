# ADR-024: The accessibility document root is not an answer

Date: 2026-08-24
Status: accepted

**Ruling**: a plan whose `extract`/`extract_all` names the accessibility document root (`WebArea` or `RootWebArea`, stripped and case-folded — NOT ARIA `document`, see §1) is refused by the plan lint for every task shape — above `plan_gap`'s `is_aggregate` early return, because the shape it catches is an ordinary single-answer question. Before execution that costs one replan from the existing budget; at a mid-run adoption point it ends the run, because the drill-down or act replan that produced the plan WAS the replan (see Consequences, and one enforcing case each). Only the extraction verbs: `observe` on a container is M32's feature, not this defect. Only the ROOT: every other container — a landmark, or an author's `role="document"` — stays with `verify`'s calibrated `not_a_dump` ratio (ADR-008), which judges it with the page in hand. `relocation_candidates` will not PROPOSE a root either: one set, defined once, in `resolver.py`.
**Because**: `observe` walks Chromium's snapshot from its root, and that root is in neither `SKIP_ROLES` nor `NAME_PROHIBITED` — so element #1 of every observation the planner sees is `WebArea — <the page title>`, the most answer-shaped string in the list attached to the one node whose text is the entire document. The M40 re-probe measured four of five live tasks planning exactly that; the resolver finds no match, and the single relocation rung left (role+name is the tier that just failed) is `{text: <the page title>}`, which either finds nothing or finds the title and answers with it.
**Enforced by**: `plan-lint-refuses-a-document-root-extract` (pre-execution), `plan-lint-refuses-a-document-root-extract-midrun` (the `adopt()` branch), `plan-gap-truth-table`, `relocation-distinct-tier` (row 5)

---

## Context

PR #43 (M40) declared three live failure shapes from 43 runs against the build
deployed *before* PR #34. The post-merge re-probe of the same tasks
(2026-08-23) found a fourth that none of them covers, and it is the dominant
one: the planner emits `extract {"role": "WebArea", "name": "<the page
title>"}`. Measured: x-rates.com 0/2 (`b8b95067`, `133264ee`), multpl.com 0/2
(`bdc38f65`, `c7fa2623`), quotes.toscrape.com 0/1 (`6811f8bf` — it extracted
the site title and the M36 judge rejected it), openlibrary.org 0/1
(`a6797fbe`). companiesmarketcap.com is unaffected (2/2): its answer is the
accessible *name* of a heading, so the plan never needs a container at all.

It is not claimed that M32 caused this. `WebArea` targets appear in two
pre-M32 runs too (`8c1a3344`, `c80b1dd0`). What is measured is that four of
five re-probed tasks that answered before do not answer now, and that the shape
they share is a container target the resolver cannot use.

## The mechanism, read off this repo rather than off the traces

Verified end to end on `hello.html` before anything was changed:

1. `observe.walk` starts at `page.accessibility.snapshot(...)`'s root node. Its
   role is `WebArea` and its name is the page `<title>`; neither `SKIP_ROLES`
   nor `NAME_PROHIBITED` contains it, so it is emitted as the first element of
   every observation, and `render` prints it as `- WebArea — 'Hello Fixture'`.
2. `resolve` builds `page.get_by_role("WebArea", name=…)`, which matches
   nothing — Playwright has no such role — so the step fails `locate`.
3. `relocation_candidates` has one rung to offer. The role+name tier is the one
   that just failed and is excluded by design, `text` is untried, and the only
   string the target carries is that page title: `{text: "<the page title>"}`.
4. On the four live pages the title is not visible text and the run dies as a
   locate failure. Where the title is also a heading, the rung *resolves*, and
   the run answers with the site title — `6811f8bf` live, and offline the
   fixture twin ran to `status: success`, `verdict: PASS`, every L1 check green,
   `answer: "Hello Fixture"` for "What does the second heading on this page
   say?".

## Decision

### 1. The refusal is the document root, not "a container", and not ARIA `document`

The defect class is "the plan targets a container that cannot be an answer",
and the tempting generalisation is a set of landmark roles (`main`,
`navigation`, `banner`, `contentinfo`, `region`, …). It is refused here. A
document root's text is the whole page *by construction*, so refusing it at
plan time has no false-positive case to argue: there is no page on which the
root is the answer. A landmark is a judgement about how much of a page is too
much of it, and this repo already makes that judgement where the evidence is —
`verify`'s `not_a_dump`, a ratio calibrated against a pinned 25-record
confusion matrix (ADR-008). Refusing landmarks from the plan alone would be
guessing at plan time what a calibrated check measures at grading time, which
is the shape ADR-016's own history (three regexes, each reverting the last)
says to stop reaching for.

The first version of this set included ARIA's `document` role, on the assumption
that it names an embedded root. It does not, and the cold review of this change
falsified it with a fixture: `role="document"` is an author-supplied role on an
in-page container (`<div class="modal-dialog" role="document">` is Bootstrap
boilerplate), Playwright resolves it, and
`get_by_role("document", name="Order confirmation")` returned a 40-character
confirmation inside a dialog — a correct answer, refused, with a reason string
asserting that node was "the ENTIRE page". That is a false statement about a page
manufactured from the plan alone, which is precisely what a plan-time rule may
never do. Note what separates the two: the root spellings do not resolve at all
(Playwright has no `WebArea` role), so refusing them can cost no run an answer,
while the one spelling that resolves is the one that is not the root.
`plan-gap-truth-table` pins both directions.

### 2. It is refused at the lint, not at the relocation rung

The acceptance named the lint; the code agrees, and the reason is ordering. The
lint runs at every plan-adoption point, before the first action of the plan it
lints. A plan refused there never reaches `resolve`, so the failed `locate`
that *builds* the `{text: <title>}` rung never happens — the degraded
relocation is unreachable for this shape rather than separately forbidden. That
is what `plan-lint-refuses-a-document-root-extract` asserts with
`trace_actions: ["navigate"]` and `actions: 1`, not a reason string.

Guarding the rung instead would be strictly worse: it would let the extraction
run, spend the action, and then refuse the recovery — the exact "pay for the
verdict in actions" cost ADR-018 moved one layer earlier.

What this does NOT close, stated rather than implied: the planner's REPLAN may
answer the gap note with `{text: "<the page title>"}` — the same wrong node, one
tier down and one replan later, on a page where the title is also a heading. The
lint cannot see that: `plan_gap(task, steps)` has no page and no title, and the
only rule that would catch it — refuse an extraction whose target string equals
the page title — is refuted by a case already in this repo, `tc1-hello-heading`,
whose correct answer IS that string. Logged as T-M40-2-4 with the cold review's
repro, and it is why T-M40-2-1 (stop advertising the root in the observation) is
the lever that would actually close the family.

The rung is guarded in the other direction, though: `relocation_candidates`
searches the fresh observation for an element whose name matches the failed
target's string, and the root is element #1 of every observation named by the
title — so a failed `{text: <title>}` used to relocate INTO `{role: WebArea,
name: <title>}`, spending one of two rungs on a target no tier can resolve
(`relocation-distinct-tier` row 5, watched red). It no longer proposes one.

### 3. Only the extraction verbs

`observe {role: WebArea}` is not refused. M32's drill-down exists to name a
container the planner can see but cannot read into (ADR-020), so a rule about
the role alone would refuse the feature. The rule is about the action and the
role together, and `plan-gap-truth-table` pins both directions.

"Not refused" is not "works": the cold review of this change showed that an
`observe` onto the root fails to locate like any other root target and then goes
down the relocation ladder, which — before the rung guard above — retargeted it
at the title's own heading and drilled into a 13-character subtree under a note
telling the planner it had the container it asked for. The guard removes that
particular rung; what remains is a read-only step whose locate failure has no
rung at all, and whose `recovery` label on a step that produces no answer is a
separate defect. Both are T-M40-2-5, out of this decision's scope: refusing
`observe` on the root would be a rule about the drill-down, which is ADR-020's
subject, not this one's.

## Consequences

- A root target no longer reaches `resolve` from either direction: a plan
  naming one is refused by the lint, and the relocation ladder will not invent
  one. What a refusal costs depends on where the plan was adopted, and the two
  are not the same. Refused BEFORE execution, the gap note goes to the planner
  and the replan is spent trying to close it; both branches have a case, and
  neither one's `replans: 0` means what the other's does.
  `plan-lint-refuses-a-document-root-extract` takes the pre-execution branch and
  reads 0 because the stub returns the same plan and the no-progress rule
  (`new_steps == steps`) ends the run — a planner that closed the gap would
  spend a replan there and be right to.
  `plan-lint-refuses-a-document-root-extract-midrun` takes the other: the
  drill-down's replan comes back with the root target, `adopt()` refuses it, and
  the run ends without a replan because the drill-down WAS the replan — there is
  nothing left to re-plan with. That second case exists because this paragraph
  once claimed the mid-run rule while no case reached `adopt()` with a root
  target at all (PR #46 R1).
- The observation itself is unchanged: the planner is still *shown*
  `WebArea — <the page title>` as element #1 of every page. Removing it from
  `observe` is the other half of the root cause and is deliberately not done
  here — it is a behaviour change on every run whose effect can only be measured
  by a live probe, and doing it in the same PR would make the T-M40-5 re-probe
  unable to attribute a recovery to either lever. Logged as debt (T-M40-2-1),
  with the planner-prompt line (T-M40-2-2) beside it for the same reason.
- No live claim is made here. This ADR ships an offline refusal and its
  watched-red cases; the D28 rows stay as PR #43 declared them until T-M40-5
  re-probes a deployed build.
