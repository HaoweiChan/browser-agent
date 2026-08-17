# ADR-007: What "the page has loaded" means, and the coverage claim it corrects

Date: 2026-08-18
Status: accepted
Supersedes: the live-coverage claims in ADR-006 Decision 5 (the mechanism
decisions in ADR-006 stand unchanged)

## Context

M6 declared openlibrary.org "evidenced but not currently verified" and its live
TC2 case "never green", both attributed to a site outage that began partway
through the milestone. On 2026-08-18 the host came back, and one of those two
cases went green immediately — `live-ol-search-a11y-invisible`, the first time
in its life, producing the `failure:locate` diagnosis it was written to grade.

The other, `live-ol-edition-title`, kept failing `nav`. The outage had been
masking a defect of ours:

| wait condition | result |
|---|---|
| `domcontentloaded` | page loads in **4.4s**, `heading[0]` = `'The monk and the dancer'` — the case's expected answer, already in the accessibility tree |
| `load` (Playwright's default, what `run_task` used) | **times out at 25s** |

One hanging subresource made a fully rendered page unreachable. `curl` fetched
the same URL in 2s. The agent was reporting `failure:nav` — blaming the site —
for a page it could read.

## Decision 1 — navigate for readability, not for `goto` returning

One `navigate(page, url)` helper, used by both call sites:

```
goto(wait_until="domcontentloaded")   # the document is parsed; content is there
wait_for_load_state("load", timeout=SETTLE_BUDGET_MS)   # swallowed on timeout
```

**Why `load` is still waited for.** The pre-plan path snapshots the page for
the planner on the very next line. A snapshot taken mid-hydration hands the
planner roles that do not exist yet, which surfaces later as a `locate` failure
on a page that was fine — an intermittent bug that also misattributes itself,
which is worse than the one being fixed. Bounding the wait keeps the behaviour
every existing case was written against and changes only the pathological case:
a healthy page has already fired `load` by the time `goto` returns and pays
nothing; a page that never fires it pays 2s and then gets read.

**Why not `networkidle`,** which is strictly stronger for hydration and was the
first implementation: measured, it cost **+34s on the fast suite** (36s →
70.7s), breaching the 60s ADR-002 budget, because it waits 500ms past the last
request on *every* navigation, healthy or not. It buys a guarantee no case asks
for, at a price every case pays. The rejected option is recorded because the
reasoning for it was sound and the measurement is the only thing that settles
it.

**Why both call sites.** `run_task` has two `page.goto` calls — the pre-plan hop
and the `navigate` action inside `execute()` — and the case that found this only
exercises the first. Fixing one would have turned that case green with the
defect fully alive on the path every multi-page plan uses. This came from
review, not from a run, and it is the reason there are two cases:
`nav-load-event-never-fires` (pre-plan) and
`nav-action-load-event-never-fires` (the `navigate` step). The second was
re-watched red *after* the first was fixed, which is the only state in which it
proves anything.

## Decision 2 — best-effort evidence gets a bound

`page.screenshot()` waits for fonts before it shoots, and on a page whose
`load` never fires that wait runs to its 30s default — per step, silently,
inside the `try/except` whose own comment reads "evidence best-effort; the
postcondition is the gate". It cost the two new cases 32s and 64s.

Best-effort and unbounded cannot both be true. The screenshot now gets the same
2s budget, and the suite went from 70.7s to 48.6s.

Worth naming *why* this survived a close review of exactly that block (the one
that produced the #6/#7 cleanups): **the comment asserted a property the code
did not have.** "evidence best-effort" reads as already-handled, so the reader
stops. A comment claiming a guarantee is a place to check the guarantee, not a
reason to skip it — and the same trap is one `try/except` away anywhere else in
this file.

No case asserts this directly: it is a latency property, and the repo has no
timing-assertion mechanism. The evidence is the committed report, where those
two cases read 4.3s and 8.4s instead of 32s and 64s. Recorded here rather than
implied, because an unmeasured claim in a performance section is exactly what
`docs/analysis.md` §1 promises not to do.

## Decision 3 — the coverage claim ADR-006 could not make

ADR-006 Decision 5 said two live domains and two task classes were verified,
with openlibrary.org resting on one pre-implementation run. That was true when
written and is superseded now:

| | ADR-006 (2026-08-17) | Now |
|---|---|---|
| Live suite | 4/6 | **6/6** |
| Live domains green | 2 of 3 | **3 of 3** |
| Live task classes green | 2 of 3 (TC1, TC3) | **3 of 3** (TC1, TC2, TC3) |

B-floor criterion 2 is **met**, not "substantially closed". The qualification
that survives is the one that was never about the outage: **every green live
case still runs a hand-written plan**, `live-books-cheapest-travel` is still
unrun, and live *planning* quality remains unmeasured on all three domains.
Coverage of the resolver → executor → verifier path is what improved.

## Consequences

- The failure that looked like a third-party outage was half ours. The outage
  was real and the two are separable only because the site came back — which is
  the argument for re-running a declared-unreachable case rather than letting
  the declaration harden. `live-ol-search-a11y-invisible` had also been
  declared red-on-its-merits and was green on the first attempt after recovery.
- `docs/support-matrix.md` gains a closed-limitation row and loses the outage
  row; the openlibrary.org cells now rest on runs against current code.
- A fixture that never fires `load` (`slow-asset.html` + the `/fixtures/hang.png`
  endpoint) exists offline, so this class is held shut without depending on a
  real site being unwell.
