# T-M40-1 — the `/smoke/stream` guard hunks, verbatim, for conflict resolution

**RESOLVED — this is now a record, not a prediction.** PR #43 merged to `main`
as `f813af5`, T-M40-1 merged `origin/main` back in, and the conflict this file
was written for happened exactly as described: six files, with `smoke_events`
and the console `smoke()` handler among them. It went the way this file says —
`await SEM.acquire()` and `finally: SEM.release()` kept, PR #43's read-only
`if SEM.locked(): … return` deleted rather than kept alongside. The case was
re-run against the MERGED page source and still binds (see below). The rest of
the file is left as written, because what it argues is why that resolution is
the correct one.

PR #43 (`claude/gifted-elbakyan-07bbef`) added a guard of its own to
`smoke_events` in `src/browser/server.py`. T-M40-1 replaces that function's
opening and adds a `finally` to it. Both PRs therefore touch the same lines, and
`specs/decisions/ADR-019-*.md` + `README.md`'s band table for the same reason
M39/PR #44 does: adding a case moves the published case counts.

This file exists so that whichever PR rebases second resolves from recorded
evidence rather than from whichever diff `git` happens to show first.

**Post-merge verification**, so the claim above is not just an assertion. Two
mutants, run against the merged tree, both red:
`the single run slot is busy — ` (the reworded refusal) gives
`refusal_does_not_satisfy_the_page_busy_branch`, and PR #43's read guard put
back in place of the acquire — with the `finally` removed, as it had none —
gives `second_stream_launched_a_second_browser` plus four more. The console
branch is graded as a substring of the merged `PAGE`, which now also carries
#43's `busy(false)` unlock in the same handler; both were kept, neither
displaced the other.

**Load-bearing**: the `await SEM.acquire()` and the `finally: SEM.release()`.
Everything else in these hunks is prose and may be resolved either way.

**Resolve toward the acquire.** PR #43's guard is a READ of the semaphore
(`if SEM.locked(): ... return`) with no acquire. It is one-directional: it stops
a browser check starting under a run and stops nothing else — two concurrent
`/smoke/stream` clients both reach `launching` and launch two Chromiums, a
`POST /tasks` inside a check's window launches the second, and `/readyz` answers
`{"ready": true, "busy": false}` throughout because it reads `SEM` too. On a
small PaaS container the second Chromium is the OOM the slot exists to prevent.
Taking PR #43's hunk over this one silently reintroduces all four, with the case
below still green on the half it does cover — so if the resolution loses the
`acquire`/`release` pair, `smoke-stream-takes-the-run-slot` is the thing that
says so. Watched red against exactly that mutant (PR #43's guard applied to this
branch): `second_stream_launched_a_second_browser`, `slot_not_held_while_smoke_runs`,
`readyz_ready_while_a_browser_is_up`, `readyz_reason_names_a_run_that_does_not_exist`,
`slot_not_held_at_launching`, `refusal_does_not_satisfy_the_page_busy_branch`
(that last key was renamed and strengthened by PR #45 R1; same assertion slot,
same six keys).

---

## 1. `smoke_events`, after `yield ev("start", ...)`

BEFORE (origin/main d06a569 — no guard at all):
```python
    yield ev("start", target=SMOKE_URL)
    try:
        from playwright.async_api import async_playwright
```

PR #43 (the read):
```python
    yield ev("start", target=SMOKE_URL)
    if SEM.locked():
        yield ev("error", error="busy: a run is executing")
        return
    try:
        from playwright.async_api import async_playwright
```

AFTER (this branch — the acquire; comment elided, see the commit):
```python
    yield ev("start", target=SMOKE_URL)
    if SEM.locked():
        yield ev("error", error="busy: the single run slot is taken — "
                 + ("a run is executing" if ACTIVE_RUN else "a browser check is running")
                 + ". No browser was launched; try again in a moment.")
        return
    await SEM.acquire()
    try:
        from playwright.async_api import async_playwright
```

## 2. `smoke_events`, the tail — new in this branch, absent from PR #43

AFTER:
```python
    except Exception as e:  # loud failure is the contract (CLAUDE.md rule 4)
        yield ev("error", error=f"{type(e).__name__}: {e}")
    finally:
        SEM.release()
```
Non-negotiable if hunk 1 keeps the `acquire`: a slot taken and never returned
bricks the service permanently, which is worse than the bug being fixed. The
`finally` covers the exception path AND the `GeneratorExit` Starlette throws in
when a viewer closes the tab mid-check.

## 3. `/readyz`'s `reason`

BEFORE: `"reason": f"a run is executing ({ACTIVE_RUN})" if busy else None,`
AFTER: busy with no `active_run_id` is the browser check, and says so instead of
naming a run that does not exist ("a run is executing (None)"). Not load-bearing
against PR #43 — resolve either way, but the case pins the `(None)` shape.

## 4. ADR-019 §2/§3 band lines + README's band table

Same collision as M39/PR #44 and for the same reason: this branch adds one case,
so `fast` 153 -> 154 and `invariant` 58 -> 59, and `published-band-matches-the-ledger`
requires both bands republished at the shipped count. Numbers here:
post-merge, at `fast` 156 / `invariant` 59 —
`fast` ts `20260824-085348`, 72.02s, 154/156, 72.02 × 1.15 = 82.82 → **85**;
`invariant` ts `20260824-000935`, 13.12s, 59/59, 13.12 × 1.15 = 15.09 → **20**.
The `invariant` citation is M40's own clean row: 59 was not a new count after the
merge, so item 2 (cited-run) refused a dirty citation and picked the clean one
over §6's residue rule — ADR-019 §3 states the resulting gap to the maximum.
Do not copy a row count or a row list into either document — the pre-commit
hook appends a ledger row to the very commit that publishes the band, so such a
list is false on write (PR #45 R4).
Whoever rebases second must NOT merge both branches' rows — the parse is
last-wins and a superseded row left above the live one is graded as
`adr_publishes_two_bands`. Re-derive at the merged count from the ledger; the
grader prints the count and the ledger maximum it wants.
