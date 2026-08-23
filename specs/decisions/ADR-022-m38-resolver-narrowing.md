# ADR-022: an ambiguous target is narrowed by the page, not failed — under four conjuncts and in the trace

Date: 2026-08-23
Status: accepted

**Ruling**: when a semantic target resolves to N>1 elements at every tier, `resolve()` tries three site-agnostic narrowing rungs before raising `ambiguous-match`: on a READING step only, (1) the step's identity `anchor` reused as a proximity anchor and (2) the first match in document order, the latter only when the task asks for one thing and the matches are interchangeable (same role AND same reading); and on any step, (3) inside proximity matching, an anchor string matched through typographic variants and then by its first 40 characters. The rung that fired is named in the trace step's `note` (`narrowed: <rung>`); none of them is labelled `retry_or_recovery`.
**Because**: six deployment runs died `failure:locate` on pages that held the answer and plans that named it — two `pg` links on an HN item (`349e4839`, `e08b7627`, `bcae4fe7`, `63b9d944`), three `Albert Einstein` matches on quotes.toscrape.com (`e985e048`), and a `near` anchor the page rendered with typographic quotes (`e6768ee0`). In each, the ambiguity was one the page itself settles.
**Enforced by**: `resolver-narrows-by-anchor-proximity`, `resolver-narrows-identical-matches`, `resolver-near-normalises-typography`, `resolver-refuses-mixed-roles`, `resolver-refuses-plural-wording`, and unchanged: `l4-shop-duplicate-labels`, `near-equidistant-is-ambiguous`, `near-anchor-substring`, `relocation-preserves-near`

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

Rungs 1 and 2 are for **reading steps only** — narrowing turns a loud failure
into an answer, and on a click or a fill it would turn one into an act on a
control the plan did not uniquely name. `near` is exempt because the plan asked
for proximity there; nothing in this section was asked for. `observe` is
excluded with the acting verbs: drilling the wrong container feeds the planner a
subtree nobody asked about, and it has its own ladder (ADR-020). tasks/TODO.md
M38 did not scope the rungs by action; this is the second place the guard is
narrower than the spec, for the same reason as the first.

1. **`anchor-proximity`.** The plan's identity anchor is a string from the part
   of the page the task is about, so it is a proximity anchor the plan already
   carries. Reuses `_nearest` unchanged. Unlike `near` it is not a *request* for
   proximity, so an anchor that identifies no single place falls through to the
   next rung instead of raising: loudness belongs to what the plan asked for.
2. **`document-order`.** The first match. Four conjuncts, and the rung is
   refused if any fails:
   - the plan carried no `index` — true by construction where the rung sits;
   - the task does not ask for several things (`_PLURAL_ASK`);
   - the step READS (`extract`) rather than acts — the shared guard above;
   - the matches are **interchangeable**: same `role || tagName` and the same
     normalised text.
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
are individually pinned by negative cases (`resolver-refuses-mixed-roles`,
`resolver-refuses-plural-wording`, `l4-shop-duplicate-labels`) so that widening
any one of them turns a case red rather than turning a run into a guess.

**Make the planner disambiguate (a replan on `locate`)** — it already can, and
`relocation_candidates` already spends a rung on it. On the four HN runs it
retargeted at a different tier and hit the same two matches, because the ambiguity
is in the page, not in the tier. A second planning call costs money and a round
trip to re-derive what document order already knows.

**Narrowing on any action, not just reads** — rejected, and it is why
`l4-shop-duplicate-labels` still passes: two buttons with the same accessible
name do different things, and clicking the first is an act nobody authorised.
That mutation's whole point is that role+name *uniqueness* broke, and it must
keep being rescued by relocation rather than answered by a coin flip. The same
argument extends to rung 1 and it is applied there: an identity `anchor` is
contractually an extract-step field (specs/001), and using it to choose which
control to press would read a signal that means something else as authority to
act. No case distinguishes the two versions — no plan in the suite puts an
`anchor` on a click — so this is a refusal chosen on the record rather than
demonstrated, and it is the safe direction of an untestable choice.

**Rung 2 guarded only on role, as tasks/TODO.md M38 specified** — implemented
with the text half added, not instead. The role conjunct is vacuous on the role
tier (`get_by_role` returns one role by construction) and the text conjunct is
vacuous on the text tier (`exact=True` returns one string by construction), so
either alone leaves the other tier unguarded: `{role: link, name: "user
profile"}` over two bylines reading "arden" and "bellweather" is same-role,
different-answer, and role alone would have picked one. Each half is the whole
guard on one tier, which is why both are here.

## Consequences

- Ambiguity is no longer terminal in three shapes, and remains terminal in every
  other. The `fast` suite gains 5 cases (153 -> 158) and ~0.6s.
- One declared limitation, `docs/support-matrix.md` **D28**: the role test reads
  `getAttribute('role') || tagName`, not the computed ARIA role.
- `resolve()` returns a 3-tuple and takes the step's `anchor`, the task string
  and the action. The policy lives in the resolver rather than in `agent.py` so
  that "may this ambiguity be settled without asking?" has one home.
- The known risk, accepted: an identity anchor that sits confidently nearer the
  WRONG candidate produces a confident wrong answer where the old code produced
  a loud failure. No case in the suite has that shape and none is invented here
  — the honest form of that claim is D28's, and the trace names the rung on
  every run it fires, so the evidence for a wrong answer of this kind is in the
  artifact rather than in a reader's inference.
