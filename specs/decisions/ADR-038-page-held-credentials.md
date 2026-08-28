# ADR-038 — a page-held credential is seeded per origin by the browser, never injected into pages

Date: 2026-08-28. Status: accepted. **Numbered 038, not 037**: this was written into the 037 slot and renumbered before merge because PR #78 (`task/M46`) already held that slot on an unmerged branch, with its own `…-m46-plan-then-loop-escalation.md`. Nothing in this tree could see that — a decision file that exists only on another branch is absent from `specs/decisions/` and from `INDEX.md`, so `adr-header-and-index` correctly reported the slot free. Note that the slot cannot even be NAMED here in the usual form: this paragraph originally cited it that way and the same check called the citation dangling, which is right — it resolves against this tree, and in this tree it dangles. The in-tree half of the collision class is guarded (PR #69); the cross-branch half is not, this was the sixth instance in one evening, and it is tracked as `T-M39-15-D2`. Recorded rather than left as an unexplained gap.

**Ruling**: a site whose credential lives in the PAGE rather than in the request is reached by seeding that origin's `localStorage` before navigation, from `BROWSER_AGENT_ORIGIN_STORAGE` — a JSON object of `{"<origin>": {"<key>": "<value>"}}` read by `agent.origin_storage_state()` and handed to `browser.new_context(storage_state=…)`. Unset returns `None`, which is Playwright's own "no seeding" and leaves every existing run byte-identical. Malformed configuration RAISES, including the two shapes that would otherwise be silent no-ops — a bare host with no scheme, and an origin carrying a path or a trailing slash — because Playwright matches neither and the run would look fine while the seed did nothing.
**Because**: the sec-10k inspector put its paid model tier behind a key the PAGE holds, and its deep-link start URL — already an `EXAMPLES` row here — extracts during load, before an agent could type into the key field. Seeding is the only route by which a run of this agent reaches that path at all. `add_init_script` is the obvious implementation and is REFUSED: this agent browses arbitrary sites, an init script is injected into every page's JS context, and an origin guard inside the script does not help because the guard only decides whether to WRITE while the value is already present to read. `storage_state` is written by the browser into each origin's own partition before any page script runs, so no page ever sees another origin's secret.
**Enforced by**: `evals/adversarial/origin-storage-seed-is-scoped.json` (`fast`+`invariant`) — four conjuncts, graded by AST rather than by substring so the prose explaining why `add_init_script` is wrong is not itself read as the violation: no `add_init_script` CALL anywhere in the package; two origins in, two partitions out, with an explicit cross-origin bleed assertion; no host or storage key hardcoded in any module (rule 6) and the secret read from the environment alone (rule 8); and six malformed shapes all refused (rule 4). Mutation-verified before commit — dropping the origin-shape validation, flattening the origins into one partition, and returning an empty state instead of `None` each redden a different conjunct, and restore green.

---

## 1. Why this does not violate rule 6

Rule 6 allows exactly three per-site items in the execution policy: a start URL,
a rate limit, and a ground-truth API endpoint. **A credential is none of them**,
so it may not be hardcoded — and neither may the origin it belongs to, nor the
storage key it is written under. All three arrive as configuration. What lives
in `agent.py` is a mechanism that knows the SHAPE of the problem (origins hold
storage; storage is seeded before navigation) and nothing about any site.

The check enforces that directly: `BROWSER_AGENT_ORIGIN_STORAGE` may be named
in `agent.py` and `eval_adapter.py` and nowhere else, and no module may call
`add_init_script` at all.

## 2. What this does not do

- It does not prove the target site accepts the credential. That is the other
  repo's check, and this one asserts nothing about the token's value or length.
- It does not touch the network. The `storage_state` is built and inspected as
  data; no case here logs in to anything.
- It writes `localStorage` only. Cookies, `sessionStorage` and IndexedDB are out
  of scope and no part of this mechanism touches them.
- It does not make the secret safe to put in a URL. It exists precisely so the
  secret does not have to travel in one.

## 3. The doc-scan repair that came with it

Adding one case moved every derived number in this repo, which is the intended
cost — and it surfaced a pre-existing defect that had made the local gate
unpassable: `docs-numbers-are-derived` walked `.claude/worktrees/`, which is
git-IGNORED and holds zero tracked files, so it graded ANOTHER BRANCH's checked
out `AGENTS.md`/`CLAUDE.md`. Measured on clean `main`: six ceiling breaches, all
of them a stale `blissful-dhawan-037761` checkout of
`claude/groundwork-pr-loop-m38-2275ee` still publishing the pre-ADR-029 15s/75s
ceilings. No commit to this tree could have fixed them. `worktrees` joins
`.git`/`.venv` in the prune set, for the reason already written beside it:
machinery is not documentation.
