# Postmortem — 2026-08-24 demo: the agent could not drive our own sec-10k inspector

**What happened.** At the 2026-08-24 live demo the ask was: point this
deployed browser agent at Task 2's own deployed inspector
(<https://whaleforce-sec10k.zeabur.app>) and answer a question from it. It
failed. This document is the retrospective for that failure line. The same
demo had a second, independent failure line — the inspector's *extractions*
being wrong at conf 0.95 on Intel/Citigroup filings — which is owned by the
sec-10k-extract repo and written up there
(`docs/evals/audits/2026-08-25-demo-intel-citi-postmortem.md` in that repo);
this document is only about why the *agent* could not drive the *page*.

**Evidence status, stated first.** No run ids from the demo survive —
`RUNS` is in-memory (support-matrix D19) and the deployment has restarted
since. Everything below is therefore a static shape analysis: the
inspector's page source read against this repo's executor, observer and
declared support matrix. Each claimed failure shape is a *prediction that
must be pinned red by a case before it is fixed* (CLAUDE.md rule 2), not a
replayed trace. The remediation milestone is `tasks/TODO.md` M41; this file
is the narrative it points back to. Nothing here is normative — `specs/`
binds.

## 1. The headline finding: the failure was overdetermined

The inspector page (sec-10k-extract,
`src/sec10k/web/static/index.html`) simultaneously exhibits at least four
shapes this repo's own support matrix already lists as failing or
unsupported. Any one of them ends a run; the demo did not lose to a single
bug. In matrix terms, the demo was an unplanned live probe of D28's
declared boundary, run on a same-owner domain in front of an audience.

**S1 — the whole page is fetch-then-render.** The fixture `<select>`, the
item list, the status banner and the extracted text are all painted by
`fetch()` + `innerHTML` after user actions. The observation the planner
plans from (`src/browser/observe.py`) shows placeholders — "Items appear
here.", "No filing extracted yet." — so the plan is authored against a page
on which the answer does not yet exist. This is the exact class the matrix
calls *unplannable* on quotes.toscrape.com's JS page
(`live-quotes-js-role-tier-blind`: the text tier can reach the content,
`live-quotes-js-text-tier-reaches`, but the planning observation contains
none of it). Content that appears only after a click must travel the
observe→replan path, which T-M40-5 round 2 measured as the recovery path —
and as rep-level nondeterministic (debt row T-M40-5-3).

**S2 — the answers are not the accessible name of any small element.** The
status banner is a bare `<div id="banner">` (accessibility role `generic`,
dropped by `SKIP_ROLES` in `observe.py`); the per-item extracted text is a
bare `<pre class="text">` (also `generic`). D28's post-M32 finding is that
the planner fails on "any page whose answer is not already the accessible
name of a small element, since the planner reaches for the document root
instead" (the T-M40-2 `WebArea` shape). The one live domain with a real
repeat count behind `supported` — companiesmarketcap.com — answers
precisely because its value *is* a heading's accessible name. The
inspector's main output region is the opposite of that shape everywhere.

**S3 — three identical "Extract" buttons.** The three input modes each
render a button whose role and accessible name are exactly `button` /
"Extract". A plan targeting it resolves to 3 matches — the ambiguity shape
M38 exists for (its Origin lists the same "N matches at tier X" failures on
HN and quotes.toscrape.com).

**S4 — nothing waits for the async result unless the plan says to.** After
"Extract" is clicked, results arrive whenever the POST returns. The
executor's only wait is `check_state`'s settle-retry loop
(`src/browser/agent.py`), which runs only when the planner authored an
`expected_state` on the click step. Whether the live planner reliably
authors one on a SPA click is unmeasured; without it the next step executes
against the un-updated DOM.

Two lesser shapes, named for completeness: the executor has no
select-option action (`click`/`fill`/`extract`/`extract_all`/`observe`/
`navigate` is the whole vocabulary, `agent.py`), so no fixture other than
the dropdown's default is reachable; and on the pre-extraction page the
capabilities `<details open>` table competes for the observation's
`MAX_ELEMS` element budget (`observe-content-survives-chrome` is the
existing pin for budget exhaustion, though its chrome sub-budget does not
cover a `details` table).

Not the problem: `url_ok` (`src/browser/server.py`) admits any public
http(s) host, so the deployment could reach the inspector fine.

## 2. Why this was predictable, and what that is worth

Every shape above was already written down before the demo — S1 is D7/D28,
S2 is T-M40-2/D28, S3 is M38's open queue block, S4's fragility is implicit
in T-M40-5's replan findings. The miss was not knowledge but *integration*:
nothing ever pointed the agent at the one external site this project also
controls, so the boundary was documented in the matrix and still walked
into live. The lesson mirrors D28's build-expiry rule, with a twist worth
recording: a live-declared row is a claim about one deployed build **of the
target site too**. When the target is our own other repo, its deploys
expire our rows exactly the way our own deploys do — so any inspector row
must record the inspector build sha it was probed against (the page footer
serves it at `/api/meta` as `git_sha`).

## 3. The remediation split, and the rule that shapes it

CLAUDE.md rule 6 forbids site-specific knowledge in the execution policy,
and owning the target site is not an exemption. So the agent may not learn
"how to drive the inspector"; the inspector must become legible to a
generic accessibility-first agent — which is nothing more than correct
ARIA, i.e. screen-reader correctness the page should have anyway. The
legitimate integration surface is exactly the per-site data rule 6 already
allows: the **start URL** and a **ground-truth API endpoint**.

**sec-10k-extract side** (queued in that repo's Demo-remediation track in
`tasks/TODO.md`, same track as its D6–D9 rows; display layer only):

1. Deep link: query parameters (e.g. `?fixture=aapl-2025&run=1`) that
   preload and extract on page load. Highest-leverage single change: a
   parameterised start URL is allowed per-site data on the agent side, and
   an agent landing on an already-rendered page bypasses S1, S3 and S4 in
   one move — reducing the task to the single-page read shape the matrix
   says is the agent's strongest.
2. `#banner` gets `role="status"` so `doc_status` is a named element.
3. `pre.text` gets `role="region"` + an `aria-label` naming the item.
4. The three Extract buttons get distinct `aria-label`s.

**This repo's side** (`tasks/TODO.md` M41): treat the inspector as a live
domain under the M40 method — probe the deployment with small-value tasks,
pin every failure shape as a red case first, declare a matrix row with run
ids, repeat counts and both build shas, and route ground truth through
`/api/extract/fixture` as the rule-6 ground-truth endpoint (verifier/eval
only, never the planner). Capability gaps S3/S4 stay with their existing
owners (M38; a possible default post-click settle). A select-option action
is deliberately deferred: if the deep link ships, YAGNI. *(Superseded
2026-08-25, before this record was ever committed: ADR-027's loop-mode
mandate ships `select_option` and moves the S4 settle question to M42 —
this paragraph is kept as written because the M41 block now says so.)*

Ordering note for whoever takes M41: probing before the sec-10k
legibility/deep-link row deploys measures the old page and expires when it
ships. Probe once for the red baseline, but declare the row only against
the page shape that will stay deployed.

## 4. What is NOT claimed

(a) That these four shapes are what actually killed the demo runs — no
trace survives; they are the shapes a fresh run must get through, each
individually sufficient to fail it. (b) That fixing the inspector's ARIA
makes the domain `supported` — S1 still applies to any flow that clicks
before reading, and the observe→replan path's measured instability
(T-M40-5-3) is untouched by anything here. (c) That the demo tasks
themselves are known — the probe tasks in M41 are chosen fresh, small-value
by design (a whole item's text would correctly die on
`extract-container-dump-is-not-the-answer`'s guard and the judge).
