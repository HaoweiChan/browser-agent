"""Deploy spike: proves the platform stack — FastAPI + SSE + headless Chromium.

Grows into the M1 gateway (POST /tasks, run records, trace streaming);
the inline smoke page is replaced by the real frontend at M4.
"""

import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="browser-agent")

SMOKE_URL = "https://example.com"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>browser-agent — deploy spike</title>
<h1>browser-agent deploy spike</h1>
<p>Proves FastAPI + SSE + headless Chromium run on this host.</p>
<button onclick="run()">Run smoke test</button>
<pre id="log"></pre>
<script>
function run() {
  const log = document.getElementById('log');
  log.textContent = '';
  const es = new EventSource('/smoke/stream');
  es.onmessage = (e) => {
    log.textContent += e.data + '\\n';
    const ev = JSON.parse(e.data).event;
    if (ev === 'done' || ev === 'error') es.close();
  };
  es.onerror = () => { log.textContent += '[stream closed]'; es.close(); };
}
</script>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/healthz")
async def healthz():
    return {"ok": True}


async def smoke_events():
    def ev(event, **kw):
        return f"data: {json.dumps({'event': event, **kw})}\n\n"

    yield ev("start", target=SMOKE_URL)
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            yield ev("launching", browser="chromium")
            # ponytail: --no-sandbox — PaaS kernels block the userns sandbox;
            # risk bounded by the non-root container user now and the URL guard
            # once the agent lands.
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page()
            yield ev("navigating")
            await page.goto(SMOKE_URL, timeout=15_000)
            title = await page.title()
            await browser.close()
        yield ev("done", title=title)
    except Exception as e:  # loud failure is the contract (CLAUDE.md rule 4)
        yield ev("error", error=f"{type(e).__name__}: {e}")


@app.get("/smoke/stream")
async def smoke_stream():
    return StreamingResponse(smoke_events(), media_type="text/event-stream")
