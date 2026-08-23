# 016 — M40: the demo surface, and what 43 live runs said about finance pages

**Date**: 2026-08-23 · **Milestone**: M40 · **Outcome**: the reviewer UI gained a
page view and a running-stage spinner, the example set went from 5 cards to 8,
and three finance domains were declared from live evidence — one `supported`,
two `unreliable` — with the 30 failing runs written up as D28 rather than
tuned away. `docs/support-matrix.md`, `src/browser/server.py`.

## Context

The owner's five asks, in one message, after looking at the deployed page:

> 我們放 openlibrary.org 跟 quotes.toscrape.com 在網站上結果不能跑出結果 這樣
> 效果非常不理想。然後我們現在只有 5 格 我想湊到 8 格。最後就是正在跑的階段我
> 希望可以秀出正在處理的旋轉 animation。另外可以開一個 right panel 去顯示網頁
> 原本內容 這樣方便 debug 也方便 interviewer 去檢視我們的爬出內容是否正確。最後
> 我希望我們網站要支援一些投資類的網站 畢竟面試者就是投資公司 他們常用的網站
> 應該不是我們現在設定這些。

Four of the five are frontend work. The fifth — "support the sites an
investment firm actually uses" — is not, and it is the only one that could not
be answered by writing code. It could only be answered by running the thing.

## The two examples that stopped working

Both complaints reproduced on the deployment on the first try, and neither was
a UI bug:

- `quotes.toscrape.com`, "Who wrote the quote about the world we have created?"
  (run `eefae1b8`) — `failure:locate`, *3 matches at tier text for
  {'text': 'Albert Einstein'}*. The listing page carries three Einstein quotes.
  The resolver refusing to guess between them is correct behaviour; it is just
  not something to put a Try button on.
- `openlibrary.org`, "Who is the author of this book?" (run `ca0be024`) —
  `failure:extract`. Three more phrasings of the same page (`4df0cfee`,
  `266216a3`) failed at locate or extract too.

The correction was not to fix the resolver. `quotes.toscrape.com`'s static
author pages answer 3/3 (`b973e350`, `93085a40`, `14833919`), so that card's
example moved to one, and the domain's TC1 cell moved `unsupported` →
`unreliable` — one page shape works, one does not, which is what the word
means. `openlibrary.org` stayed a failing example **on purpose**, relabelled
"See a failure: author of a book": a demo that cannot show a loud failure is
not evidence of anything.

## The 27 runs

Forty-three runs across twenty-two candidate finance domains, real planner,
against the deployment. Thirteen answered, thirty failed, and **nineteen of the
twenty-two domains never answered once**. The split was not the one we expected.

(The first version of this record said "fourteen domains, ten answered,
seventeen failed", and D28 published the same wrong arithmetic. Both were caught
by review, not by a check: nothing in this repo recomputes a hand-written count
against the run ids beside it, which is the same defect
`docs-numbers-are-derived` exists to prevent one document over. The figures here
and in D28 were re-derived from the raw probe logs and now agree.)

**It answered** on `companiesmarketcap.com` (7/7 across four pages),
`x-rates.com` (3/3 on one currency pair) and `multpl.com` (3/6, split by page).
**It failed everywhere else**: stockanalysis.com, cnbc.com, finviz.com,
coingecko.com, coinmarketcap.com, stooq.com, 8marketcap.com, sec.gov EDGAR,
fred.stlouisfed.org, macrotrends.net, slickcharts.com, marketbeat.com,
newyorkfed.org, federalreserve.gov, tradingeconomics.com, berkshirehathaway.com,
investor.gov, finance.yahoo.com and google.com/finance.

The dividing line is not site quality, popularity, or JS. It is whether the
number the task asks for sits in an element of its own. Where it does,
the plan targets it and the run answers. Where the number is one cell of a
quote grid, the planner targets `main` or the table, the extraction returns
several thousand characters, and the verifier rejects the run —
`failure:semantic`, every time, never a wrong answer. That is
`extract-container-dump-is-not-the-answer` — a case this repo already has,
offline — happening on six live finance pages.

Two results are worth naming separately. `finviz.com` (`cb86c0d7`) got past
every layer-1 check with the string "PE Ratio" as its answer, and the M36 LLM
judge rejected it: *merely repeats the label without supplying the required
numeric value (35.49)*. That is the first live evidence the judge earns its
cost — D25 declared its grading quality unverified because there was no key in
that environment. And `x-rates.com` USD→JPY (`0f8e532f`) failed on an identity
anchor the planner invented, on the same site whose EUR→USD page answers 3/3,
which is why that row is `unreliable` rather than `supported`.

## What was NOT done

The container-dump shape has an obvious-looking fix: a plan-lint clause that
refuses an `extract` targeting a container role, the same way ADR-018's lint
refuses an unranked aggregate. It was designed and then not built,
for one reason, found by reading the case it would have touched before writing
the clause: `extract-container-dump-is-not-the-answer` deliberately grades
what a run looks like *after* the verifier rejects a container dump, and a lint
that rejects the plan first would end that run as `failure:task` with nothing
in evidence — turning a committed case red by changing what it can observe,
not by fixing what it grades. Isolating the cell instead of giving up is
already debt (T-R66). Widening D28 with live evidence is the honest move;
shipping an unwatched guard on the way past is not.

## The rows expired before they merged

The branch had been green for a while when a merge with `main` turned up two
PRs that had landed in the meantime — M32's observation drill-down among them.
Merging meant the deployment this work had been measured against no longer
existed, so the probes were re-run.

Three of the four examples this milestone had just declared stopped answering.
`x-rates.com` went 3/3 → 0/3. `multpl.com` went 3/6 → 0/2. The
`quotes.toscrape.com` author page went 3/3 → 0/1 — it extracted the site title
and the judge rejected it. Only `companiesmarketcap.com` was unaffected, and the
reason is legible: its answer *is* the accessible name of a heading, so no plan
it produces ever needs a container. The failures share a shape none of the three
pre-M32 shapes covers — `extract {role: WebArea, name: "<page title>"}`, the
document root named by `<title>`, degrading into a `{text: "<page title>"}`
relocation that resolves nothing.

Two rows were withdrawn rather than shipped, `bankofcanada.ca` (3/3) and
`ecb.europa.eu` (2/3) were probed and declared in their place, and the whole
episode went into D28. It is not attributed to M32: the deployment moved
model-side as well as code-side, one task phrasing per page was tested, and two
pre-M32 runs already showed `WebArea` targets. T-M40-2 carries the confounds.

The generalisable part is smaller and worse than any of the individual results:
**a support-matrix row declared from live runs is a claim about one deployed
build, and it expires when the build does.** Nothing in this repo detects that
expiry — no gate, no case, no CI job re-runs any of it. It was caught by hand,
once, because a merge conflict happened to prompt a re-probe. Had the branch
merged an hour earlier it would have shipped three cards that no longer worked,
which is the exact complaint that started this milestone.

## Assumption → Eval contradiction → Correction

- Assumed: the two failing example cards were stale copy — the runs cited in
  `EXAMPLES` succeeded once, so the tasks presumably still worked.
- Eval said: both reproduced on the first attempt against the live deployment
  (`eefae1b8` locate-ambiguity, `ca0be024` extract-empty), and three further
  openlibrary phrasings failed too.
- Corrected: `quotes.toscrape.com`'s example moved to an author page (3/3) and
  its TC1 cell to `unreliable`; `openlibrary.org`'s stayed, relabelled as the
  deliberate failure demo.

- Assumed: "supports investment sites" is a matter of picking well-known
  finance domains — the recognisable ones would be the ones to add.
- Eval said: every recognisable one failed. stockanalysis.com, cnbc.com,
  finviz.com, coingecko.com, google.com/finance, sec.gov EDGAR and
  fred.stlouisfed.org all failed, while `companiesmarketcap.com` — a site
  nobody would name first — answered 7/7.
- Corrected: the three rows declared are the three that ran, not the three that
  would look best on a card, and D28 names the shape that decides it (a value
  in its own labelled element) rather than the domains.

- Assumed: one green run per domain is enough to declare a row, since each
  probe was end-to-end against the real deployment.
- Eval said: `multpl.com` answered 3/6 — 2/3 on one page and 1/3 on the page
  next door (`3ec2b4d5` green, `a9d565b2` and `602d70be` red), on identical
  task text. D23's lesson, again, on a new domain.
- Corrected: every candidate row was repeated before being declared, and the
  two that split are `unreliable` with the failing sibling run cited in D28.

- Assumed: the page view is a read-only panel over evidence the run already
  produced, so it could not introduce a failure of its own — the risky code was
  all in the probing.
- Eval said: cold review found three, and the milestone's own spinner made the
  worst one worse. `es.onerror` polled the run record with no `.catch` and
  `renderResult` read `r.status.split(':')` unguarded, so a record that 404s
  (in-memory `RUNS` after a redeploy, D19) threw and left the page asserting
  `running`, spinner animating, `Run task` disabled for good. Watched red against
  the pre-fix page: `#status` `RUNNING`, `go.disabled true`, one uncaught
  `TypeError`.
- Corrected: `busy()` owns both buttons and the stream handle, the poll is
  guarded on both HTTP status and the run id that owns the surface, a lost stream
  ends terminal, and `clip()` marks a truncated extraction with its true length.
  All four are pinned by `ui-terminal-state-on-every-ending`.

- Assumed: writing the counts into D28 straight from the probe session was safe —
  the run ids were right there in the same cell.
- Eval said: both reviewers recomputed them and both got different numbers than
  the prose. "27 live runs / 10 answered / 17 failed" against 40 enumerated ids;
  the true figures are 43 runs, 22 domains, 13 answered, 30 failed, 19 domains
  that never answered. `docs-numbers-are-derived` cannot see D28 — it recomputes
  README's block from a report, and D28 has no report.
- Corrected: every figure re-derived from the raw probe logs and cross-checked
  by re-running the count, in D28 and in this record. The underlying gap — a
  hand-typed count beside the ids it summarises, graded by nothing — is stated
  in D28 rather than closed.

- Assumed: adding rows and a limitation to the support matrix was a local edit
  to one document.
- Eval said: the spec-drift audit found four other documents asserting what the
  change reversed — `docs/analysis.md` §4 and §6, README's live-planning bullet
  and its "fourth live site" section, ADR-009 Decision 4 ("the support matrix
  row for the domain is `unsupported`", in the sentence whose job is "nothing
  was softened"), and `specs/decisions/INDEX.md` — none of them graded by
  anything, because no check reads a status word out of the matrix.
- Corrected: each amended in place with a dated M40 note rather than reworded,
  ADR-009 struck-not-deleted per the ADR-015 convention. The absence of a guard
  over the matrix's status words is now written down in three of those places
  instead of being rediscovered by the next audit.

- Assumed: a run id is durable evidence — a row declared from repeated live runs
  stays true, so the probe could be done once and written up.
- Eval said: merging `main` brought in two merged PRs, the deployment was
  replaced, and a re-probe of the same tasks put `x-rates.com` at 0/3,
  `multpl.com` at 0/2 and the `quotes.toscrape.com` author page at 0/1 —
  three of the four examples this milestone had declared.
- Corrected: those rows were withdrawn before merge and replaced with
  `bankofcanada.ca` (3/3) and `ecb.europa.eu` (2/3), every remaining example was
  re-run against the current build, and D28 now carries both probes plus the
  rule that fell out of it — a live-declared row expires when its build does.
  What is NOT corrected: nothing detects that expiry. The next build can do this
  again and no gate will notice.
