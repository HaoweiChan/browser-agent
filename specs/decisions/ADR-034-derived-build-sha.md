# ADR-034: the build derives its own sha

Date: 2026-08-28
Status: accepted

**Ruling**: `/app/BUILD_SHA` is a value the build DERIVES: a separate build-identity stage (same base tag) runs `git rev-parse HEAD` against the build context, whose `.git` `.dockerignore` now admits, and the final stage COPYs that one file — never `.git` itself. A derivation that fails for any reason exits 0 and writes nothing, so `/version` answers `{"sha": null, "source": "unavailable"}` rather than breaking the build or guessing. The never-filled `ARG ZEABUR_GIT_COMMIT_SHA` is removed.
**Because**: the first deploy after ADR-033 merged settled its one deliberately unverified fact — on 2026-08-28 `curl https://whaleforce-browser-agent.zeabur.app/version` answered `{"sha":null,"source":"unavailable"}` while `/healthz` was ok, so the new build was running and Zeabur does not pass its Git-group variables to a Dockerfile build. ADR-033's Consequences pre-recorded exactly this outcome and named the remedy this ADR implements.
**Enforced by**: `build-sha-is-derived-not-supplied`

---

## The one decision

ADR-033 designed `/version` to fail to the honest null if Zeabur turned out not
to fill the build argument, and it turned out not to. This ADR changes how the
file gets its content and nothing else: route, contract and the 13-probe case
`version-never-guesses-a-build-sha` are untouched.

The Dockerfile gains a first stage that COPYs the context in and runs

```
git -C /ctx rev-parse HEAD > /BUILD_SHA 2>/dev/null || : > /BUILD_SHA
```

and the final stage replaces the old `ARG` + `printf` pair with a single
`COPY --from=build-identity /BUILD_SHA /app/BUILD_SHA`, at the same layer
position (after the pip layer, before `USER`) for the same reasons.

**The `ARG` is dropped, not kept as a fallback.** The live read proved the
platform never fills it, so the only value that could still arrive through it
is one an operator types into a dashboard build-arg field — and every later
build re-bakes a typed value, which is ADR-033 Decision 2's rejected path
arriving at build time instead of runtime (PR #65 R3). The claim stays narrow
and positive: the value is the context's HEAD, and a failed derivation writes
nothing.

**Fail-to-null, enumerated.** `COPY . /ctx` rather than `COPY .git /ctx/.git`,
so a context stripped of `.git` is not a COPY error; the `|| :` branch turns
every derivation failure — no `.git` in the context, a worktree's `.git`
pointer file dangling inside the image, git missing from the base — into an
empty file, which the route reports as `unavailable`. Anything partial or
garbled is refused by the route's whole-string sha validation (ADR-033
Decision 3).

## What this does not settle

Whether Zeabur's builder keeps `.git` in the build context. Documented neither
way, same posture as ADR-033: the design fails to the honest null if not, and
the first deploy after this merges settles it — read
`https://whaleforce-browser-agent.zeabur.app/version` and compare the sha to
the merge commit. A sha equal to the merge commit closes M44-P1;
`unavailable` again means the context reached the build without `.git`, and the
honest published state stands, with any matrix row saying it cannot name our
build.

Dropping the `.dockerignore` line only guarantees Docker will not FILTER `.git`
out; it cannot put `.git` into a context that never carried it, and Docker
documents the mechanism by which that happens: for a **Git context**, BuildKit
by default does not keep the `.git` directory, and keeping it takes the build
argument `BUILDKIT_CONTEXT_KEEP_GIT_DIR=1`. So `unavailable` after this change
has two distinct causes with one symptom — the settled one (the platform passes
no Git-group build argument, which is why the `ARG` is gone) and this one (the
derivation ran against a context with no repository in it). Which state we are
in is what the next post-merge read tells us; either way postmortem §2's rule
holds and a row that cannot name its build says so.

If the deploy shows a Git context is the cause, the follow-up is to set
`BUILDKIT_CONTEXT_KEEP_GIT_DIR=1` — a repo-owner action in the Zeabur
dashboard, not something this change can do or verify, and left unset until a
deploy shows it is needed. Recorded here with its hazard analysis so the next
session does not re-derive it: that switch carries no sha. It is a boolean
deciding whether the tree the derivation reads is present, while the sha stays
derived per build from that tree, so a wrong setting (or none) yields the empty
file and `unavailable` rather than a stale value — which is exactly what
separates it from the struck `ARG` path, where the dashboard field carried the
value itself.

Nor was the image built here — no Docker on this machine, the same declared
limit ADR-033 ran under. What is exercised instead is the derivation command
itself: `build-sha-is-derived-not-supplied` extracts it from the Dockerfile
and runs it, against this repo's root (must write HEAD) and against a git-less
directory (must exit 0 and leave the file empty).

## What the `.git`-in-the-context tradeoff costs, and what the guard is worth

This is a property of the decision, not a weakness of the check, so it is
recorded here rather than only in a triage note. Deriving a sha requires `.git`
in the build context. Once `.git` is in the context, **any instruction that can
read the context can carry it into the final image** — that is what admitting it
means, and no amount of guarding the Dockerfile's `COPY` lines changes it.

So the two sentences a reader might take away are not equivalent, and only one
of them is true:

- TRUE — an accidental context copy is caught. `build-sha-is-derived-not-supplied`
  reads every `COPY`/`ADD` in the final stage and refuses any source that is not
  one of the four this image ships, across every spelling the parser reads:
  case, indentation, line continuation, `--chown=`/`--link`/`--from=` flags, and
  `ADD` as well as `COPY`. Thirteen bypasses are pinned red as self-test rows the
  check runs on itself, and six correct spellings are pinned green.
- NOT TRUE — that `.git` cannot reach the image. It can, through a path that has
  no `COPY` line in it at all. Verified rather than argued:
  `RUN --mount=type=bind,source=.git,target=/tmp/g cp -r /tmp/g /app/.git`
  is GREEN against the case and puts the whole history in the image. A text scan
  of `COPY`/`ADD` instructions cannot see that, and widening it to chase `RUN`
  bodies is chasing an unbounded surface — `cp` from a mount, a clone, a fetch —
  which is why this stops here. (`ARG`-substituted sources, heredoc `COPY`
  forms and a lowercase `FROM` were probed in the same pass and all three fail
  closed, loudly.)

The upgrade that would make the stronger sentence true is a CI job that builds
the image and asserts `/app/.git` does not exist — the only check that reads the
artifact instead of the recipe. It is filed as `M44-P1-D8` rather than done
here, with its cost recorded so the next session does not re-derive this: it
needs a Docker build of the Playwright base in CI, and CI's wall clock is
already under a separate breach on another line. Until it exists, the guarantee
is the first bullet and the ADR says so in those words.
