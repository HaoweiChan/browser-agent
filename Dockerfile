# Playwright base image ships matching Chromium + system deps; the pip pin in
# requirements.txt must stay in lockstep with this tag.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app
COPY src/browser/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src/ /app/src/

USER pwuser
EXPOSE 8080
CMD ["sh", "-c", "uvicorn src.browser.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
