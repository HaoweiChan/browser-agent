# Build identity, stage 1 of 2 (ADR-034, which replaces ADR-033's ARG fill).
# The 2026-08-28 post-merge live read answered {"sha":null,"source":"unavailable"}
# on the freshly deployed build: Zeabur does not pass its Git-group variables to
# a Dockerfile build, so the declared ARG was never filled and is now gone —
# with the platform verifiably not supplying it, the only value that could ever
# arrive through it is one an operator types into a dashboard build-arg field,
# which every later build then re-bakes (ADR-033 Decision 2's rejected path at
# build time; PR #65 R3). The sha is DERIVED instead: the context's own HEAD,
# computed here from `.git` (which .dockerignore now admits) and carried into
# the final stage as the one file /version reads. Same base tag as the final
# stage, so no new image dependency; the stage itself is discarded.
# On ANY failure the RUN exits 0 and leaves the file EMPTY — /version then
# answers `unavailable`, the honest null, and the build never breaks. Known
# ways that happens: the context arrives without `.git` at all — BuildKit drops
# it by default for a Git context unless BUILDKIT_CONTEXT_KEEP_GIT_DIR=1, and
# `COPY .` rather than `COPY .git` keeps even that from being a build error, see
# ADR-034's declared limits; the context is a git
# WORKTREE, whose `.git` is a pointer file into a repository the image does not
# have; or the base image some day drops git. The route's validation (ADR-033
# Decision 3) refuses anything that is not a whole-string sha, so a partial or
# garbled derivation is `malformed`, never echoed.
# Graded by `build-sha-is-derived-not-supplied`, which extracts and executes
# the RUN line below — the exact command shape is load-bearing.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS build-identity
COPY . /ctx
RUN git -C /ctx rev-parse HEAD > /BUILD_SHA 2>/dev/null || : > /BUILD_SHA

# Playwright base image ships matching Chromium + system deps; the pip pin in
# requirements.txt must stay in lockstep with this tag.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app
COPY src/browser/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src/ /app/src/
# The frontend parses this at request time — docs/support-matrix.md is the one
# source the README and the UI both render, so the image ships the file rather
# than a second copy of the table baked into code.
COPY docs/support-matrix.md /app/docs/support-matrix.md

# Build identity, stage 2 of 2. One file out of the stage above; `.git` itself
# never enters this image. A FILE and not an `ENV`, unchanged from ADR-033: a
# service-level environment variable set in the Zeabur dashboard SHADOWS an
# image `ENV` at runtime, so a sha set that way is correct until the next
# deploy and a confident lie afterwards; a file written at build time is immune
# to that, because nothing at runtime can shadow it. Placed after the COPYs so
# it never busts the pip layer, and before USER so the write succeeds.
COPY --from=build-identity /BUILD_SHA /app/BUILD_SHA

USER pwuser
EXPOSE 8080
CMD ["sh", "-c", "uvicorn src.browser.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
