# ADR-033: the deployment reports the build it is running, or says it does not know

Date: 2026-08-27
Status: accepted

**Ruling**: `GET /version` answers `{"sha": <7-40 lowercase hex> | null, "source": "image" | "unavailable" | "malformed"}`. The value comes from `/app/BUILD_SHA`, a file the Dockerfile writes at build time from Zeabur's `ZEABUR_GIT_COMMIT_SHA` — not an environment variable, which a service-level setting shadows at runtime, and not the local git checkout, which is a different tree from the one that was built. Anything that is not a whole-string git sha is refused rather than echoed, a build that supplied nothing answers `null` with a `source` saying so, and there is deliberately no hand-set fallback.
**Because**: M44 must publish the build sha of our own deploy and cannot — `/version` was 404, `/healthz` answers only `{"ok": true}`, nothing set a build variable — and the failure this route exists to prevent is a confidently wrong sha, not a missing one: a live-declared matrix row is a claim about ONE deployed build, so a row carrying the wrong sha expires quietly instead of loudly.
**Enforced by**: `version-never-guesses-a-build-sha`

---

## Context

Two documents had already written down that this was missing, in the same
words, and neither could be acted on without a route:

- `.github/workflows/deploy-smoke.yml` has carried the ceiling in a comment
  since M5: on a `push` the job cannot prove it is testing the NEW build,
  because Zeabur keeps serving the old one until the deploy flips "and the app
  exposes no /version". Its fixed 240s sleep is a heuristic standing in for a
  fact nothing could read.
- `docs/evals/2026-08-24-demo-sec10k-inspector-postmortem.md` §2 rules that a
  live-declared row is a claim about one deployed build **of the target site
  too**, and the sec-10k inspector was made to serve its own sha at
  `/api/meta` for exactly that reason. Ours serves nothing, so ADR-030's
  probe recorded our build sha `9c3340c` by hand, off the deploy-smoke run
  that pushed it. `tasks/TODO.md` T-M41-3 already says out loud that "nothing
  in this repo reads either sha back".

M44's acceptance clause — "matrix rows updated with run ids, repeat counts,
**and both build shas** where the target is our own deploy" — is the clause
that cannot be met today. Hence this prerequisite, and nothing more than it.

The failure mode being designed against is specific, and it is not "the
endpoint is missing". It is D23/M29's shape: a number published against a
build nobody can name, which then cannot be shown to be stale. A route that
guesses converts that into something worse — a number published against a
build that is named **wrongly**, which reads as evidence and is not.

## Decision

### 1. One route, and it names its own source

`GET /version` returns two fields and no others:

| field | value |
|---|---|
| `sha` | the build's commit sha (lowercase hex, 7-40 chars, whole-string), or `null` |
| `source` | `image` when the sha came from the build; `unavailable` when the build supplied nothing; `malformed` when it supplied something that was refused |

`source` is not decoration. Without it a reader staring at `"sha": null` has
to guess whether the build said nothing or said something the route threw
away — two different misconfigurations with two different fixes, one of which
would otherwise be a silent `null`.

What `source` deliberately does NOT have to distinguish is a baked sha from a
hand-set one, and that is Decision 2's doing rather than an omission: there is
no mechanism by which a human can set this value, so `image` has one meaning.
The first draft of this ADR read the value from an environment variable and
claimed `source` made "an injected sha distinguishable from a defaulted one";
a cold review pointed out that it separated *set* from *unset* and never
*baked* from *hand-set*, which is the distinction the whole ADR is about. The
repair was to delete the second case, not to name it.

### 2. The value is a file the build writes, and no runtime setting can shadow it

Zeabur's documentation lists `ZEABUR_GIT_COMMIT_SHA` — "the Git commit SHA
value that the current deployment belongs to" — among its built-in variables,
and says of that whole Git group that the variables "will only appear during
the build phase of the Git service". So the platform does know the sha, and
it stops knowing it before our process starts. The `Dockerfile` therefore
takes it as a build argument and writes it into the image:

```
ARG ZEABUR_GIT_COMMIT_SHA=""
RUN printf '%s' "$ZEABUR_GIT_COMMIT_SHA" > /app/BUILD_SHA
```

Three alternatives were considered and rejected:

- **Read the local git checkout at request time.** Rejected, and it is the
  reason this ADR exists. Inside the image there is no checkout — `Dockerfile`
  copies `src/` and one doc, and `.dockerignore` excludes `.git` from the build
  context entirely — so the honest outcome is an error path. Everywhere else
  there IS a checkout and it is a *different tree* from the one that produced
  the running build, so the fallback answers a real sha of the wrong thing. A
  wrong sha is worse than no sha, because it is citable. Watched red rather
  than asserted: given that fallback, `/version` answered
  `{"sha": "fd3ae2aa77251d3bce4d91ecb18e003089e253af", "source": "image"}` — a
  real sha, of a tree that produced no build.
- **An image `ENV` set from the same build argument.** This was the first
  implementation and a cold review killed it. The bake is not the problem — an
  `ENV` is frozen into the image exactly as a file is. The problem is that a
  platform's service-level environment variable **shadows** image `ENV` at
  runtime, so the moment anyone sets `BUILD_SHA` in the Zeabur dashboard — the
  natural quick fix if a build does not supply the sha — the route serves it
  forever, indistinguishable from a baked value, correct until the next deploy
  and a confident lie after it. That is not a hazard to document; it is the
  failure this endpoint exists to prevent, with a knob attached. A file written
  during the build is immune to that, because nothing at runtime can shadow it.
- **A hand-set value as a declared fallback.** Rejected on the same ground, and
  named separately because the first draft of this ADR *did* prescribe it while
  the `Dockerfile` comment two files away forbade it. One change giving
  opposite operational instructions for its highest-risk path is worse than
  either instruction alone. The ruling is the strict one: if the build does not
  supply a sha, the deployment says `unavailable`, and that is a finding rather
  than something to paper over by hand (see Consequences).

So the trade the task set — environment variable or baked file — is decided by
shadowing and by nothing else. What a file costs is four lines (a path, an
encoding, an `OSError` branch); what it buys is that a sha reaching this route
at RUNTIME is impossible.

**And that is the whole of what it buys — the first version of this section
claimed more.** A review walked the remaining path (PR #65 R3): an operator
types a sha into the dashboard, it reaches the declared `ARG`, every subsequent
build freezes that same value, and `/version` publishes a commit that is not
the running build with `source: "image"`, indistinguishable from a
platform-supplied one. That is the `ENV` failure moved from runtime to build
time, not removed. Two things follow, and both are the reason the earlier
absolute phrasing is now forbidden by
`claims_the_build_sha_has_no_operator_settable_path`: the claim here is
**runtime** immunity and nothing broader, and the remedy in Consequences is a
sha the build DERIVES, never one a human supplies to it.

### 3. A value that is not a sha is refused, not echoed

`[0-9a-f]{7,40}`, **whole-string**, after stripping surrounding whitespace.
Anything else is `malformed` with a `null` sha.

Every word of that is load-bearing, and the case grades each one against a
deliberately weakened matcher rather than taking it on trust — because a
matcher that rejects the obvious garbage can still be wrong in three ways a
later edit reaches by accident. `re.match` publishes `<40-hex>-dirty`, and a
41-character string, whole; `re.search` publishes `release-<40-hex>`; and
`re.IGNORECASE` publishes the uppercase spelling. All three answer
`source: "image"` while doing it, which is worse than a 404. Uppercase is
refused because git does not emit it and refusing errs toward the null. The
`RUN` line's double quotes are graded here too: single quotes would write the
literal `$ZEABUR_GIT_COMMIT_SHA` into the file, and that is a probe.

**What this cannot catch, stated rather than implied.** A value that is
genuinely 7-40 lowercase hex but is not a commit — a 24-character deployment
id copied out of a dashboard, a date like `20260827`, a decimal build number —
is echoed as a sha. There is no way to tell it from an abbreviated sha without
asking git, and asking git is exactly what Decision 2 forbids. The shape check
is the strongest guard available to a route that refuses to consult a
repository; the rest of that gap belongs to whoever cites the sha, and the
case declares it.

### 4. The case is `invariant`-only, and that is a ceiling decision

`version-never-guesses-a-build-sha` is tagged `invariant` and not `fast`.
Not a judgement about the case: the `fast` band has no room. ADR-019 §2
records that the committed ledger already holds rows at 230 `fast` cases —
90.65, 91.06 and 91.76s — and that the rule derives **110** from the slowest
of them against a committed 105, which is why PR #60 moved its extra case to
`invariant` rather than raise a ceiling by edit. This probe measured the same
thing again from the other side: with this case added, `fast` ran 230 cases in
90.41s locally (ledger ts `20260827-152555`,
`evals/report/20260827-152555-fast.json`), inside the band, and the ledger's
maximum at that count is still 91.76s and still derives 110. So the tag follows
the precedent instead of re-litigating it. The case drives no browser, makes no
network call and spends nothing; it does thirteen loopback round trips against
the app the suite already hosts in-process, which is what `invariant` admits.
Seven cases are already tagged this way.

## Consequences

**What this does not settle, and cannot from here.** Zeabur's docs place
`ZEABUR_GIT_COMMIT_SHA` in the build phase and separately say a declared `ARG`
is set before the build; they do not state that the Git group is passed to a
Dockerfile build as a build argument. That is one fact, it is documented
neither way, and guessing it is precisely the habit this ADR is about. It is
**unverified on purpose**, and the design fails to the honest null if it turns
out false: an unpassed `ARG` is empty, `/app/BUILD_SHA` is empty, and
`/version` answers `unavailable`. Nor was the image built here — there is no
Docker on the machine this was written on — so the `RUN` line is reasoned from
standard `ARG`/`ENV` semantics and not observed. The first deploy after this
merges settles both: read `/version` on the deployed URL and compare the sha
to the merge commit.

- If it answers a sha equal to the merge commit: done, and M44 may cite it.
- If it answers `{"sha": null, "source": "unavailable"}`: the build argument is
  not passed. **The remedy is a sha the build DERIVES, and there is exactly one
  candidate** — compute it during the build, which today also means letting
  `.git` into the build context `.dockerignore` excludes, and which nobody can
  set to a wrong value by hand. Filling the declared `ARG` from a dashboard
  field is deliberately NOT offered, though it would work and the first draft of
  this section did offer it: a human typing a sha into a form is the stale-value
  path Decision 2 rejects, and recommending it here while the `Dockerfile`
  forbade it made one change give opposite instructions in two files (PR #65
  R3). Until the build can derive the sha, the honest published state is
  `unavailable`, and a matrix row that cannot name our build says so instead of
  naming one.

**One thing `unavailable` deliberately does not distinguish**: a build that
passed nothing, a build that wrote an empty file, and a process launched
outside the image all answer identically. Diagnosing which is a job for the
deploy log, not for this route — collapsing them keeps the contract three
states wide, and all three mean the same thing to a caller.

**What is still owed to M44, and is deliberately not in this change.**
Comparing the deployed `/version` against `GITHUB_SHA` in `deploy-smoke.yml`
— the "honest fix" that workflow's own comment names — is the change that
retires its 240s sleep. It is not made here: this task is one route plus its
case, and the workflow change belongs with the milestone that consumes the
sha. `tasks/TODO.md` carries it under `## Debt` with `Origin: M44-P1`.

**No secret is exposed.** A commit sha of a repository the reviewer is being
handed is not sensitive, and the route reads exactly one file and prints the
one value in it — it reads no environment variable at all, so there is nothing
of the environment for it to enumerate or echo (CLAUDE.md rule 8).
