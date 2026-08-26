# ADR-026: an ambiguous target is narrowed by the page, not failed — under four conjuncts and in the trace

Date: 2026-08-23
Status: accepted

**Ruling**: when a semantic target resolves to N>1 elements at every tier, `resolve()` tries three site-agnostic narrowing rungs before raising `ambiguous-match`: on a READING step whose task asks for ONE thing, (1) the step's identity `anchor` reused as a proximity anchor and (2) the first match in document order, the latter only when the matches are interchangeable (same role AND same reading); and (3) inside proximity matching, on the same terms, an anchor string matched through typographic variants and then by its first 40 characters. `near`'s own exact and substring matching is unchanged and stays available to every step, as M6 shipped it. The rung that fired is named in the trace step's `note` (`narrowed: <rung>`); none of them is labelled `retry_or_recovery`.
**Because**: six deployment runs died `failure:locate` on pages that held the answer and plans that named it — two `pg` links on an HN item (`349e4839`, `e08b7627`, `bcae4fe7`, `63b9d944`), three `Albert Einstein` matches on quotes.toscrape.com (`e985e048`), and a `near` anchor the page rendered with typographic quotes (`e6768ee0`). In each, the ambiguity was one the page itself settles.
**Enforced by**: the rungs — `resolver-narrows-by-anchor-proximity`, `resolver-narrows-identical-matches`, `resolver-near-normalises-typography`; the guards, each red when and only when its own conjunct is removed — `resolver-refuses-narrowing-a-click` (reading steps), `resolver-refuses-plural-with-anchor` + `resolver-refuses-plural-wording` (singular task, both rungs) + `resolver-refuses-plural-name-the` / `-who-are` / `-give-me` / `-zh` (the wording), `resolver-refuses-mixed-roles` (role half), `resolver-refuses-different-readings` (text half), `resolver-refuses-plural-on-a-loose-anchor` + `resolver-refuses-a-click-on-a-loose-anchor` (both refusals reaching rung 3) and `resolver-narrows-singular-noun-ending-in-s` + `resolver-refuses-plural-menus` (the plural test, pinned in both directions); `resolver-narrowing-fails-closed` (the `loose` switch has no permissive default, so a future caller cannot restore the ungated rung by omission); and verified UNCHANGED by this milestone, pinning nothing in it: `l4-shop-duplicate-labels` (PR #42 R2 — it does not pin the acting refusal), `near-equidistant-is-ambiguous`, `near-anchor-substring`, `relocation-preserves-near`

---

## Context

`specs/000` treats ambiguity as a loud `locate` failure, and every prior decision
in this repo has widened that rather than narrowed it:
`near-equidistant-is-ambiguous` refuses a tie, `near-anchor-substring` refuses an
anchor that names two places, `resolver-substring-name` refuses substring name
matching. Those rulings are why the resolver has never reported a wrong element
as a confident answer through the `near` path.

They are also why the M37 deployment receipts read the way they do. Six runs —
three shapes, the first of them attempted four times — ended with no answer on a
page that displayed it:

| run | target | what the resolver said |
|---|---|---|
| `349e4839` `e08b7627` `bcae4fe7` `63b9d944` | `{role: link, name: "pg"}` | `2 matches at tier role`; the relocation rung retargeted `{text: "pg"}` and hit the same two |
| `e985e048` | `{text: "Albert Einstein"}` | `3 matches at tier text` |
| `e6768ee0` | `{near: "“The world as we have created it …”"}` | `no tier resolved` |

The first two are the same shape: several matches, and a page that distinguishes
them — one `pg` is in the submission subline the task is about, and the three
`Albert Einstein`s are the same string three times over, so the choice cannot
change the answer. The third is not ambiguity at all: `get_by_text` is a literal
match, the page renders U+201C/U+201D, the plan quoted ASCII and more of the
sentence than the page shows, and a missed anchor is indistinguishable from a
page that does not have it.

## Decision

Three rungs, in `src/browser/resolver.py`, tried **after every tier has been
given its chance to resolve uniquely** — a clean single match at the text tier
still beats a narrowed one at the role tier, so narrowing sits after the loop
rather than inside it.

**Two refusals gate ALL THREE rungs** (amended, PR #42 R1 and R7), because both answer
"may this ambiguity be settled without asking?" rather than "which candidate
wins":

- **reading steps only.** Narrowing turns a loud failure into an answer, and on
  a click or a fill it would turn one into an act on a control the plan did not
  uniquely name. `near` is exempt because the plan asked for proximity there;
  nothing in this section was asked for. `observe` is excluded with the acting
  verbs: drilling the wrong container feeds the planner a subtree nobody asked
  about, and it has its own ladder (ADR-020).
- **singular tasks only.** One of several matches is not a worse answer to a
  plural ask — it is an answer to a different question, wrong by omission and
  silently so.

They were reached in two steps, and each step is a case. The singular test
shipped INSIDE rung 2, which left rung 1 answering plural asks: `List all the users who posted in this thread.` with an identity anchor
returned one of two users, `success`, verdict PASS. That is the defect this ADR
exists to prevent, in the rung nobody guarded, and the committed negative case
did not catch it because its anchor was the candidate text itself, so it never
reached rung 1 at all (PR #42 R1, `resolver-refuses-plural-with-anchor`, and
`resolver-refuses-plural-wording` re-anchored to reach rung 1).

Then both refusals were hoisted above rungs 1 and 2 — and rung 3 sits above
BOTH, in the `near` branch, which returns before that guard is reached. So the
same plural ask was still answered one rung up, through an anchor only M38's
prefix pass can resolve, and an acting step could be narrowed the same way (PR
#42 R7, `resolver-refuses-plural-on-a-loose-anchor`,
`resolver-refuses-a-click-on-a-loose-anchor`). The refusals are now computed
once, as `may_narrow`, and every rung reads that one value.

**What rung 3 gates is the two passes M38 ADDED, not `near`.** Exact and
substring matching stay available to every step, plural or singular, reading or
acting: an anchor the page actually contains is the proximity the plan asked
for, and M6 shipped it that way. Only `normalised` and `prefix` — which resolve
anchors that previously resolved to nothing, and so turn a loud failure into an
element — are withheld. R7's acting-half repro (`near: "to  arden"`, two
spaces) is NOT one of them and was not a regression: Playwright's substring
matching normalises whitespace itself, measured at 1 match with no M38 code
involved, so that input presses the same button on `main`. The case that
replaced it anchors on an ASCII hyphen against the fixture's em dash, which
only the normalising pass can resolve.

tasks/TODO.md M38 did not scope the rungs by action; that is the second place
the guard is narrower than the spec, for the same reason as the first.

1. **`anchor-proximity`.** The plan's identity anchor is a string from the part
   of the page the task is about, so it is a proximity anchor the plan already
   carries. Reuses `_nearest` unchanged. Unlike `near` it is not a *request* for
   proximity, so an anchor that identifies no single place falls through to the
   next rung instead of raising: loudness belongs to what the plan asked for.
2. **`document-order`.** The first match. Four conjuncts, and the rung is
   refused if any fails:
   - the plan carried no `index` — true by construction where the rung sits;
   - the task does not ask for several things — the shared guard above;
   - the step READS (`extract`) rather than acts — the shared guard above;
   - the matches are **interchangeable**: same `role || tagName` and the same
     normalised text. This one gates rung 2 ONLY. Rung 1 exists to choose
     between candidates that DIFFER, from evidence the plan carries; a rung
     allowed to pick only between identical elements is not a proximity rung at
     all, and gating it that way would delete it along with its own case. That
     half of PR #42 R1's acceptance is declined for that reason; the plural half
     is fixed above.
2b. **What `_PLURAL_ASK` reads** (amended, PR #42 R4 and R8). Three shapes,
   because a quantifier is only one of the ways English asks for a set: a
   quantifier (`all`, `every`, `both`, `how many`…), an imperative or request
   naming a PLURAL NOUN (`name the authors`, and not `name the author`), and
   the plural copula (`who are the authors`). A trailing `s` is not by itself
   what separates those two, which this section claimed for a round: `\w+s`
   read every singular noun ending in s as plural, so `show me the address`,
   `the business` and `the class` all stopped narrowing (R8,
   `resolver-narrows-singular-noun-ending-in-s`). The character before the
   final s carries what can be carried, and that is `ss` alone: an English
   plural of a word ending in `ss` is `-sses`, so no plural has `ss`
   immediately before its final s. `u` and `i` were excluded beside it for one
   round and that was a worse bug than the one it fixed — `the status` and `the
   menus` both end in `us`, `the analysis` and `the taxis` both in `is`, so a
   whole class of real plurals stopped being recognised and was answered from
   one match (R13, `resolver-refuses-plural-menus`). Separating those needs a
   lexicon. **Where no rule is correct in both directions, this milestone keeps
   the over-firing**, because the costs are not symmetric: an unrecognised
   plural is a confident wrong answer, a refused narrowing is a loud failure.
   So `the status`, `the genius`, `the analysis`, `the lens` and `the news` all
   read as plural and refuse to narrow — declared as D29 (4), and pinned in
   both directions by two cases that cannot be traded for each other. The
   CJK alternatives carry no `\b`, because the boundary never matches inside a
   CJK run and the English list was therefore structurally inert on the six ZH
   cases this repo ships — the lesson `agent.SCOPE_BLOCK` already carried
   (`screening-word-boundary`). One case per phrasing, each watched red against
   the committed regex. It is still a regex over natural language and D29
   carries what it misses.
3. **`near-normalised` / `near-prefix`.** `_nearest` gains two passes after
   exact and substring: a regex that accepts typographic variants of
   quote/apostrophe/dash characters and collapses whitespace runs, and then the
   same over the anchor's first `NEAR_PREFIX` (40) characters. Strictest first,
   so the loosest match is only ever reached when every stricter one found
   nothing, and an ambiguous loose match is still refused by `NEAREST_JS`.

**No site knowledge** (CLAUDE.md rule 6): the rungs read the plan's own strings,
document order, tag names and rendered text. HN and quotes.toscrape.com appear
in this file and in fixture comments, and nowhere in `src/browser/`.

**The trace says which rung fired**, as `note: "narrowed: <rung>"`, and
`resolved.tier` is `structural` for rung 1 for the reason `near` is
(specs/001: proximity is what identified the element). It is deliberately NOT
labelled `retry_or_recovery: "recovery"`. The contract reserves that label for
"a classified failure that led to a different strategy", and the recovery metric
counts those steps by construction; a narrowing happens inside one `resolve()`
call, with nothing raised, nothing superseded and no ladder run. Labelling it
would inflate a published metric with attempts that never failed — the same
ruling the plan lint's note got at M31 and M32's drill-down got at ADR-020.

## Alternatives rejected

**Keep failing loudly on every ambiguity** — the current behaviour, and it has
the strongest argument of anything here: a page that is genuinely ambiguous and
gets silently disambiguated is exactly how a wrong answer ships with a green
verdict, and this repo has shipped that twice (`near-equidistant-is-ambiguous`,
`resolver-substring-name`). What decides it is that "loud" is only honest when
the ambiguity is real. Three matches that read identically, or two elements one
of which sits inside the line the anchor names, are not a page that failed to
say which — they are a resolver that refused to look. So the rungs are gated to
exactly the shapes where the page has already answered, and rung 2's conjuncts
and the shared refusals are individually pinned by negative cases —
`resolver-refuses-mixed-roles`, `resolver-refuses-different-readings`,
`resolver-refuses-narrowing-a-click`, and the plural family — each red when and
only when its own conjunct is removed, verified by ablating each one over the
whole suite rather than by argument, so widening any of them turns exactly one
case red rather than turning a run into a guess.

**Make the planner disambiguate (a replan on `locate`)** — it already can, and
`relocation_candidates` already spends a rung on it. On the four HN runs it
retargeted at a different tier and hit the same two matches, because the ambiguity
is in the page, not in the tier. A second planning call costs money and a round
trip to re-derive what document order already knows.

**Narrowing on any action, not just reads** — rejected: two buttons with the
same accessible name do different things, and clicking the first is an act
nobody authorised. `resolver-refuses-narrowing-a-click` is what pins that, and
it is the ONLY thing that does: two controls, one accessible name, the same
reading, different effects, so every other conjunct passes and widening `READS`
presses the wrong button. This ADR previously credited
`l4-shop-duplicate-labels` with pinning it and PR #42 R2 falsified that —
that mutation's two buttons carry different visible text, so the
interchangeability test blocks them too and widening `READS` alone left the
whole suite green. `l4-shop-duplicate-labels` keeps its own job (role+name
uniqueness breaking, rescued by relocation); it does not do this one. The same
argument extends to rung 1 and is applied there: an identity `anchor` is
contractually an extract-step field (specs/001), and using it to choose which
control to press would read a signal that means something else as authority to
act.

**Rung 2 guarded only on role, as tasks/TODO.md M38 specified** — implemented
with the text half added, not instead. The role conjunct is vacuous on the role
tier (`get_by_role` returns one role by construction) and the text conjunct is
vacuous on the text tier (whole-string matching returns one string by
construction — as of T-M42-20 that is an anchored case-insensitive regex rather
than `exact=True`, so the text conjunct is now merely NEARLY vacuous there: two
matches can differ in case, and the check refuses to narrow them, which is the
conservative direction and not a change of rule), so
either alone leaves the other tier unguarded: `{role: link, name: "user
profile"}` over two bylines reading "arden" and "bellweather" is same-role,
different-answer, and role alone would have picked one. Each half is the whole
guard on one tier, which is why both are here. The text half is pinned by
`resolver-refuses-different-readings` and the role half by
`resolver-refuses-mixed-roles`; each is red when and only when its own half is
removed. PR #42 R3 is why that sentence names those two cases and not
`resolver-narrows-by-anchor-proximity`, which the ADR used to cite here and
which cannot pin anything of the sort — rung 1 fires there, rung 2 is never
reached, and that fixture's document order coincides with its expected answer.

## Consequences

- Ambiguity is no longer terminal in three shapes, and remains terminal in every
  other. The `fast` suite gains 17 cases (153 -> 170) and ~2s: three for the
  rungs, thirteen for the guards, one for the guard's own signature. The ratio
  is the record of three review rounds, which found guards pinned by nothing,
  claims wider than the guard they described, and a fix that opened the unsafe
  direction while closing the safe one. A rung is cheap; knowing it cannot
  answer the wrong question is not.
- One declared limitation, `docs/support-matrix.md` **D29**: the role test reads
  `getAttribute('role') || tagName`, not the computed ARIA role.
- `resolve()` returns a 3-tuple and takes the step's `anchor`, the task string
  and the action. The policy lives in the resolver rather than in `agent.py` so
  that "may this ambiguity be settled without asking?" has one home.
- The known risk, accepted: an identity anchor that sits confidently nearer the
  WRONG candidate produces a confident wrong answer where the old code produced
  a loud failure. No case in the suite has that shape and none is invented here
  — the honest form of that claim is D29's, and the trace names the rung on
  every run it fires, so the evidence for a wrong answer of this kind is in the
  artifact rather than in a reader's inference.
