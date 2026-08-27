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

# Build identity (ADR-033). Zeabur's docs say ZEABUR_GIT_COMMIT_SHA exists during
# the BUILD phase only, so the sha has to be frozen into the image here — at
# runtime the variable is gone. A FILE and not an `ENV`: a service-level
# environment variable set in the Zeabur dashboard shadows an image `ENV` at
# runtime, and a sha set by hand that way is correct until the next deploy and a
# confident lie afterwards, indistinguishable from a baked one. A file in the
# image cannot be shadowed, so there is no hand-set path to go stale.
# Placed after the COPYs so it never busts the pip layer, and before USER so the
# write succeeds. If Zeabur does not pass the build argument, the ARG default
# leaves this file empty and /version answers `unavailable`: it fails to the
# honest null, never to a guess. Double quotes are load-bearing — single quotes
# would write the literal, which is what the `unexpanded` probe grades.
ARG ZEABUR_GIT_COMMIT_SHA=""
RUN printf '%s' "$ZEABUR_GIT_COMMIT_SHA" > /app/BUILD_SHA

USER pwuser
EXPOSE 8080
CMD ["sh", "-c", "uvicorn src.browser.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
