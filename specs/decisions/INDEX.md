# Decisions index

This is the current-rules digest: one line per ADR, the ruling only, not the
incident narrative behind it. Every ADR carries a matching `**Ruling**` /
`**Because**` / `**Enforced by**` header directly under its title — read the
full file when you need the "why" or the evidence, read this index when you
just need "what is now true" (groundwork GW-006).

- ADR-000 — specs/ holds only invariants, output contracts and ADRs; enforcement lives in hooks, never in prose — enforced by `.githooks/pre-commit`, `.claude/hooks/post-edit-invariant.sh` · amended by ADR-001
- ADR-001 — a bounded docs/ planning layer and a milestone-level tasks/TODO.md are allowed; specs/'s three-kind charter is unchanged — enforced by advisory (cold-reviewer subagent, CLAUDE.md rule 3)
- ADR-002 — sets the pre-commit gate: fast ≥ baseline, invariant = 100%, trap-catch ≥ 90%, fast cost = $0.00, fast wall clock ≤ 60s — enforced by `.eval-baseline.json` + `.githooks/pre-commit`, wall clock by `fast-wall-clock-budget` · amended by ADR-009, ADR-010
- ADR-003 — recovery runs on two dispatch-classified ladders (locate→relocate, act→replan), budget exhaustion is classified by the failure it died of — enforced by `diagnosis-classifier-classes`, `relocation-distinct-tier`, `budget-replans-exhausted`
- ADR-004 — the trace stream emits every attempted step including superseded ones, the support matrix is parsed live never duplicated, every gateway failure returns the RunResult shape — enforced by `stream-shows-every-step`, `support-matrix-cites-real-cases`, `gateway-error-contract-shape`
- ADR-005 — answer matching separates value/unit/currency, a replan can't launder a no-op action, recovery requires a real strategy change, the URL guard re-checks after every action, supersede pointers are never dangling — enforced by `verifier-sign-currency-percent`, `replan-cannot-launder-noop-action`, `supersede-never-dangles`
- ADR-006 — implements `near:` as the `structural` tier (document-order nearest anchor, excludes its own subtree, exact-before-substring, refuses on ambiguity), closes 3 quiet-wrong-answer defects — enforced by `near-prefers-the-container`, `near-anchor-substring`, `relocate-fill-non-editable` · amended by ADR-007
- ADR-007 — navigation waits `domcontentloaded` then best-effort-bounded `load`, not strict `load`/`networkidle`; screenshot font-wait gets its own 2s bound; corrects ADR-006's live-coverage table — enforced by `nav-load-event-never-fires`, `nav-action-load-event-never-fires`
- ADR-008 — `not_a_dump` divides value length by real page size against DUMP_RATIO=0.35, gated by MIN_PAGE_CHARS=100, calibrated on a 25-record pinned confusion matrix (tp=10,fp=11,fn=1,tn=3) — enforced by `verifier-precision-recall`, `verifier-sparse-page-not-a-dump`, `verifier-dump-ratio-anchor-flip`
- ADR-009 — mutation catalogue admits 5 capability-breaking mutations (not 6), unrescuable losses are pinned honestly not smoothed over, survival/recovery counters are pure functions, quotes.toscrape.com/js is published unsupported — enforced by `mutation-metrics-honesty`, `mutation-catalog-integrity`, `opt-in-expect-keys-declared` · Decision 6 closed by ADR-010
- ADR-010 — ADR-002's 60s `fast` ceiling stands and is now applied by `evals/run.py` to the run it measured; the suite shares one Chromium (own BrowserContext per run, re-launched if it dies) and measures 54.1-55.9s — enforced by `over_budget()` in the runner, `fast-wall-clock-budget`, `agent-launches-its-own-browser`, `shared-browser-relaunches-when-dead` · amends ADR-002, ADR-009
