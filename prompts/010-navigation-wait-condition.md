# 010 — The outage that was half ours

**Date**: 2026-08-18 · **Milestone**: post-M6 fix (M6 merged as `f31b520`) ·
**Outcome**: live suite 4/6 → **6/6**, all three live domains and all three
live task classes green against current code; B-floor criterion 2 met;
navigation and screenshot waits bounded. ADR-007.

## Context

M6 shipped with openlibrary.org declared unreachable — a real outage, four
committed live runs showing `failure:nav` at `page.goto` while the other two
live domains answered normally in the same runs. The milestone was careful
about it: the outage got its own support-matrix row, criterion 2 was downgraded
from "met" to "substantially closed", and the live TC2 case was declared "never
green".

The host came back the next day.

## The prompt (verbatim)

The owner had already answered the standing question of what to do when it did:

> **openlibrary.org outage** → "Keep retrying before the PR"

and, when the retries ran out and the milestone shipped anyway, approved the
follow-up:

> **nav fix** → "Fix it now, eval-first"
> **paid run** → "Run one task, record the run id"

## What the retry found

`live-ol-search-a11y-invisible` went green on the first attempt — **its first
green ever**, producing the `failure:locate` diagnosis it was written to grade,
on a real site nobody here authored.

`live-ol-edition-title` kept failing `nav`. That is where the milestone's
careful declaration turned out to be half wrong:

| wait condition | result |
|---|---|
| `domcontentloaded` | loads in **4.4s**, `heading[0]` = the case's expected answer |
| `load` (Playwright's default, what `run_task` used) | **times out at 25s** |

One hanging subresource had been making a fully readable page unreachable. The
outage was real; it had also been providing cover for a defect of ours, and the
two are separable only because the site recovered.

## AI recommendation: accepted / rejected / modified

**Modified twice, both times by a peer session reading the diff rather than
running anything, and both notes changed what shipped.**

1. *"There are two gotos, not one."* `run_task` navigates in two places — the
   pre-plan hop and the `navigate` action — and my case exercised only the
   first. I wrote the second case, fixed the pre-plan goto alone, and re-ran:
   **it stayed red**, failing on the `navigate` step at 20s, exactly as
   predicted. Without that note the fix would have gone green with the defect
   fully alive on the path every multi-page plan uses.
2. *"`domcontentloaded` alone is the opposite mistake."* The pre-plan path
   snapshots the page for the planner on the very next line; a snapshot taken
   mid-hydration hands the planner roles that do not exist yet. Their suggested
   `networkidle` settle was **right in principle and rejected on measurement**:
   +34s on the fast suite (36s → 70.7s), breaching the 60s ADR-002 budget,
   because it waits 500ms past the last request on every navigation, healthy or
   not. Shipped instead as a *bounded* wait for `load` — healthy pages pay
   nothing and keep the behaviour every existing case was written against.

The peer was also wrong once, usefully: they read the 404 that took the
deployment down as possibly caused by their own commit, then disconfirmed it
themselves — deploy-smoke had passed against that sha four hours earlier, so
the build succeeded and served, and the outage is platform-side. Correlation
real in ordering, dead in mechanism.

## Assumption → Eval contradiction → Correction

- Assumed: `live-ol-edition-title` was red because openlibrary.org was down.
  Eval said: the host recovered, its sibling case went green immediately, and
  this one kept failing — an eval-side probe then loaded the same URL in 4.4s
  under `domcontentloaded` with the expected heading already in the
  accessibility tree.
  Corrected: navigation waits for a page that can be *read*, not for `goto` to
  return. A declared-unreachable case is a hypothesis with an expiry date, not
  a conclusion; re-running it is what separated their outage from our bug.

- Assumed: one case per defect.
  Review said: two `goto` call sites, one case.
  Corrected: `nav-action-load-event-never-fires`, re-watched red *after* the
  pre-plan fix — the only state in which it proves anything. An eval that can
  pass while the bug survives is worse than no eval, because it also stops
  anyone looking.

- Assumed: `try/except` around a screenshot with the comment "evidence
  best-effort" meant the screenshot could not hurt the run.
  Eval said: the two new cases cost **32s and 64s**. `page.screenshot()` waits
  for fonts, and on a page whose `load` never fires that wait runs to its 30s
  default — per step, silently.
  Corrected: the same 2s bound a postcondition gets; suite 70.7s → 48.6s. The
  comment is why it survived a close review of that exact block: it asserted a
  property the code did not have, so it read as already-handled.

- Assumed (by me, in the M6 docs): the honest move when a live domain is down
  is to declare it and move on.
  Eval said: half of what was declared as someone else's outage was ours.
  Corrected: the declaration was still right to make — it was accurate on its
  date and it named exactly what was unverified. What was missing is that
  "unreachable" is a claim with a shelf life. The same now applies to the
  deployed URL, which passed deploy-smoke at 14:02 UTC and was 404 on every
  path by 18:04 with no push in between; that gap has its own matrix row now.
