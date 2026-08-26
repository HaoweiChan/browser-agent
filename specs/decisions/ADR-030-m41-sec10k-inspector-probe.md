# ADR-030: the sec-10k inspector probe is pre-registered, its ground-truth endpoint is eval-only, and the row it declares measures mode B

Date: 2026-08-26
Status: accepted

**Ruling**: before any run of the M41 inspector probe executes, this ADR freezes the two-task set, the exact task text and start URL for each, the protocol (3 runs per task via `POST /tasks` on the deployed URL with no `model` override, every run's `run_id`/answer/terminal status/cost/wall time published regardless of outcome, ground truth re-verified through the inspector's `/api/extract/fixture` at probe time, both build shas recorded), the four ADR-025 metrics and the pass/fail thresholds in §Thresholds — and rules two boundaries that outlive the probe: the inspector's ground-truth endpoint is reachable from the eval side only and never from the planner or executor, and the `docs/support-matrix.md` row this milestone declares measures **mode B only** and says so, with M44 named as the owner of its loop-mode column.
**Because**: this is the same act ADR-025 pre-registered for T-M40-5 and the same reason applies with one addition — the target site is our own other deployment, so a row here is a claim about two builds, not one (postmortem §2), and the thresholds must be frozen before the numbers exist because M41's own acceptance clause requires a row whatever the numbers say; the eval-only boundary is CLAUDE.md rule 6's third allowance used deliberately rather than drifted into, because an executor that can ask a site's API for the answer passes every case on that domain without reading the page and no other check in this repo would notice.
**Enforced by**: the pre-registration half is procedural (the commit that carries this file precedes the probe, and the probe's results land in §Outcome below); the ground-truth boundary is enforced by `sec10k-ground-truth-endpoint-eval-only`; the mode-B scoping is enforced by the row's own text and by ADR-022's live-declaration rule.

---

## Context

The 2026-08-24 demo failed on our own sec-10k inspector, and
`docs/evals/2026-08-24-demo-sec10k-inspector-postmortem.md` is the retrospective:
four page shapes (S1 fetch-then-render, S2 answers-are-not-accessible-names,
S3 three identical "Extract" buttons, S4 unauthored async settle), each
individually sufficient to end a run, none of them replayed from a surviving
trace because `RUNS` is in-memory (D19). `tasks/TODO.md` M41 is the remediation
block. Its cross-repo dependency — sec-10k-extract's display-layer legibility
row — **has since deployed**: `/api/meta` reports `git_sha` `5a44758598f5`, the
deep link `?fixture=<id>&run=1` preloads and extracts on page load, `#banner`
carries `role="status" aria-label="doc_status"`, the extracted-text panes carry
`role="region" aria-label="Item <n> extracted text"`, and the three Extract
buttons carry distinct `aria-label`s. The postmortem's ordering note is
therefore satisfied: the page shape probed here is the one that stays deployed.

### The scope ruling, stated rather than left as a tension

M41's `Update 2026-08-25` says the declared matrix row "should wait for M42 and
be probed under both modes", while M41's own Acceptance requires the row. This
ADR rules: **declare the row now, as a mode-B row, and make the row say so.**
The block itself calls the update "sequencing guidance, not a hard Depends"; the
stated reason to wait (probing the old page) is gone now that the page-side row
deployed; and M44 "owns folding the loop-mode results back into this row", which
cannot fold into a row that does not exist. The row must state plainly that it
measures mode B, that loop mode is unprobed, and that M44 owns that column.
Nothing in loop mode, `select_option`, frame-piercing observation or a default
post-click settle is built here — all four are M42's.

### ADR-number collision check

Highest ADR on `origin/main` is `ADR-027-loop-mode-is-a-deliverable.md`.
`gh pr list --state open --json headRefName,number` (checked 2026-08-26, from
this branch) returns three open PRs: `task/M42` (#57), which adds decision files
numbered **028 and 029**; `task/M45` (#56), which adds a decision file also
numbered **028** — the two collide with each other at 028, the way #42 and #44
collided at 023 when ADR-025 ran this check; and
`chore/m39-done-and-id-uniqueness` (#54), which adds none. This ADR therefore
takes **030**, the number after the highest reserved anywhere, rather than 028
after `main`'s maximum: ADR-025 took `main`+1 and was safe because the collision
was between two other branches, whereas 028 here would make an existing two-way
collision a three-way one.

## Frozen task table

Both task texts are quoted verbatim from the M41 block; neither is chosen after
seeing any result. One start URL, because one deep link is the whole point of
the page-side row: a parameterised start URL is per-site data CLAUDE.md rule 6
allows, and it is the only inspector knowledge that reaches a run.

| # | Task (verbatim, frozen here) | Start URL | Ground truth | Source of ground truth |
|---|---|---|---|---|
| 1 | `What is the doc_status of the aapl-2025 fixture?` | `https://whaleforce-sec10k.zeabur.app/?fixture=aapl-2025&run=1` | `success` | `POST /api/extract/fixture {"fixture":"aapl-2025"}` → `doc_status`, re-verified at probe time |
| 2 | `How many items are extracted?` | same | `18` (with 5 more `incorporated_by_reference`, 23 items total) | same call → `counts.extracted`, re-verified at probe time |

An answer counts as **correct** if it carries the ground-truth value. The page
renders both values inside one status line — `doc_status: success — 18 extracted
· 5 incorporated_by_reference fixture: aapl-2025` — so an answer that returns
that whole line carries the value and is graded correct; this is decided here,
before the runs, because it would otherwise be exactly the kind of judgment call
ADR-025 exists to prevent being made after the fact. An answer of `18` alone is
also correct for task 2. An answer of `23` is **wrong** for task 2 (that is the
item count, not the extracted count) and, if it terminates `success`, is a
wrong-success.

### The wrong-success shape this probe predicts before it runs

Pre-registered so that finding it cannot be presented afterwards as an expected
result. The deep link removes the click, not the race: measured while writing
`live-sec10k-authored-wait-reaches-the-doc-status`, the observation the planner
is given is taken before the page's own extraction round-trip lands, and with
the settle deleted from the plan, 3 reps produced two runs terminating
`success` with the answer `"Extracting…"` and one `failure:semantic`. If a
live run answers `"Extracting…"` or `"No filing extracted yet."` and terminates
`success`, that is a **wrong success** under §Metrics and trips threshold (a).
It is not a refusal, not a loud failure, and not a footnote.

## Validity precondition

This probe counts only if run against the deployment of `main@9c3340c` or a
later `main` commit (`deploy-smoke` run `32926527916`, conclusion `success`,
2026-08-26T03:27:42Z — read off the workflow timeline, since there is still no
`/version` endpoint to compare against, the declared ceiling T-M40-4 names), and
only while the inspector reports `git_sha` `5a44758598f5`. If the inspector's
sha has moved at probe time the probe is re-run against the new one and the sha
recorded is that one: D28's build-expiry rule applies to the target site's build
too, which is the postmortem's §2 finding.

**Nothing in the PR that carries this ADR changes what is measured.** The M41
branch adds eval cases, a fixture snapshot, two eval-side scanner exclusions and
documents; `src/browser/agent.py`, `planner.py`, `observe.py`, `resolver.py`,
`verifier.py` and `judge.py` are untouched. So this probe measures the deployed
mode-B agent as it already stands, and this PR cannot have moved its numbers in
either direction.

## Protocol

1. Each of the 2 tasks is run **3 times** against
   `https://whaleforce-browser-agent.zeabur.app` via `POST /tasks`, `url` set to
   the frozen start URL and **no `model` field** — 6 runs total.
2. For every run record `run_id`, the final `answer`, terminal `status`, cost
   and wall-clock time, read from `GET /tasks/{run_id}`.
3. Ground truth is re-verified at probe time through the inspector's
   `/api/extract/fixture`, and `/api/meta`'s `git_sha` is read before and after
   the probe. The endpoint is called by the probe script and by nothing the
   agent runs — the boundary below.
4. Every run_id is published, whatever it did. No run is dropped.
5. Runs are serialised, not parallel: the deployment holds one run slot
   (`/readyz`), and the deep link makes the inspector re-extract on every hit.

## The ground-truth-endpoint boundary

Rule 6 allows three pieces of per-site data anywhere: a start URL, a rate limit,
and a ground-truth API endpoint. M41 uses the first and the third. The rule that
keeps the third honest is direction: `/api/extract/fixture` may be reached by
the probe script, by `evals/` and by an eval adapter, and by nothing that
decides what the agent does. `sec10k-ground-truth-endpoint-eval-only` enforces
three conjuncts, each watched red before it was green — the endpoint path
appears in no module of `src/browser/` except `eval_adapter.py`; the inspector
host reaches `server.py`'s `EXAMPLES` (a start URL, which rule 6 allows first
and `examples-cover-matrix` requires for every live row) but never
`agent`/`planner`/`observe`/`resolver`/`verifier`/`judge`; and every inspector
case carrying an `expect.answer` names the endpoint its ground truth came from.

## Metrics — reported separately, never blended

The four ADR-025 metrics, unchanged and quoted rather than restated loosely:
**correct answer** (terminal `success`, judge-certified, answer carries the
re-verified ground-truth value), **loud failure** (any `failure:*` terminal
status), **wrong success** (terminal `success` with an answer that does not
carry the ground-truth value), **refusal** (the gateway rejects the task before
a run starts, or the run reports a defined refusal state distinct from the
three above). Four separate numbers per task. Never combined into one rate.

## Pre-registered thresholds (fixed, verbatim)

(a) **HARD**: zero wrong-success across all 6 runs. Any wrong-success = probe
verdict FAIL regardless of every other number, and — per ADR-027's Invariants
and M44's Acceptance — is a stop-ship finding routed to a queue block, not a
row footnote.
(b) The matrix status is decided by the correct-answer rate over the 6 runs,
and by this rule rather than by judgment after the fact: **6/6 → `supported`;
3–5 of 6 → `unreliable`; 0–2 of 6 → `unsupported`.** A verdict of FAIL on (a)
overrides this row-status rule and the row is declared `unsupported` whatever
the correct-answer rate.
(c) Refusals are counted separately and never counted toward (b).
(d) The row records both build shas, every run id, and the repeat count. A row
that cannot name the inspector's `git_sha` it was probed against is withdrawn,
not softened.

## Commitment

Whatever the outcome, results land in §Outcome below and in
`docs/support-matrix.md` as declared limitation **D30** plus a
`whaleforce-sec10k.zeabur.app (live)` row, in the same commit, including
declaring the row `unsupported` where the thresholds say so. Every run_id from
every one of the 6 runs is published there, not just the ones that support the
verdict. Raw per-run evidence is committed under `evals/report/`.

## Consequences

- The row this declares is a mode-B row and is labelled as one. It is not
  evidence about loop mode in either direction, and M44 owns re-declaring it
  under both modes.
- Shapes S3 and S4 are not fixed here. S3 is fixed page-side on this one page
  (`sec10k-extract-buttons-are-distinguishable`) and the capability gap behind
  it stays with M38/ADR-026. S4 is declared, with `l4-shop-render-delayed` as
  its existing offline pin and M42 as owner of the default settle.
- A new failure shape found by this probe is a new adversarial case (rule 2),
  not an adjustment to this ADR's frozen task list or thresholds.

## Outcome

**Not yet run.** This section is empty by design at the moment this file is
committed: the whole point of the pre-registration is that the commit carrying
the frozen table and the thresholds precedes the runs, so the commit order is
itself the evidence (ADR-025's own protocol, same reading). The results land
here in the follow-up commit, with every run_id, whatever they say.
