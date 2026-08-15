"""Deploy spike: proves the platform stack — FastAPI + SSE + headless Chromium.

Grows into the M1 gateway (POST /tasks, run records, trace streaming);
the inline smoke page is replaced by the real frontend at M4.
"""

import asyncio
import ipaddress
import json
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import run_task
from .planner import live_planner

app = FastAPI(title="browser-agent")
app.mount("/fixtures", StaticFiles(directory=Path(__file__).parent / "fixtures"), name="fixtures")

# ponytail: in-memory run store + semaphore(1) — persisted records and higher
# concurrency when the M4 UI lands; per-IP rate limiting stays BACKLOG.
RUNS: dict[str, dict] = {}
SEM = asyncio.Semaphore(1)


def url_ok(u: str) -> bool:
    """http/https only, no loopback/private/link-local literals.
    ponytail: hostname DNS-rebinding defense is BACKLOG (docs/plans)."""
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return False
    host = p.hostname or ""
    if host.lower() == "localhost":
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return True  # named host


class TaskIn(BaseModel):
    task: str
    url: str | None = None


async def _execute(run_id: str, task: str, url: str | None):
    async with SEM:
        try:
            result = await run_task(
                task, url, live_planner(), f"/tmp/runs/{run_id}", url_guard=url_ok
            )
        except Exception as e:  # loud, never a hung "running"
            result = {"status": "failure:env", "answer": None,
                      "reason": f"{type(e).__name__}: {e}", "evidence": None,
                      "budgets_spent": None}
        RUNS[run_id] = result


@app.post("/tasks")
async def submit_task(t: TaskIn):
    if not t.task.strip() or len(t.task) > 500:
        raise HTTPException(422, "task must be 1-500 chars")
    if t.url and not url_ok(t.url):
        raise HTTPException(422, "url blocked: http/https public hosts only")
    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = {"status": "running"}
    asyncio.get_event_loop().create_task(_execute(run_id, t.task, t.url))
    return {"run_id": run_id}


@app.get("/tasks/{run_id}")
async def get_task(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run_id")
    return RUNS[run_id]

SMOKE_URL = "https://example.com"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>browser-agent — deploy spike</title>
<h1>browser-agent deploy spike</h1>
<p>Proves FastAPI + SSE + headless Chromium run on this host.</p>
<button onclick="run()">Run smoke test</button>
<pre id="log"></pre>
<h2>Run a task (live planner)</h2>
<p>Minimal M1 harness — the real frontend lands at M4.</p>
<input id="task" size="60" placeholder="natural-language task">
<input id="url" size="40" placeholder="start URL (optional)">
<button onclick="submitTask()">Run</button>
<pre id="out"></pre>
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
async function submitTask() {
  const out = document.getElementById('out');
  const body = {task: document.getElementById('task').value,
                url: document.getElementById('url').value || null};
  const r = await fetch('/tasks', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const {run_id, detail} = await r.json();
  if (!run_id) { out.textContent = 'rejected: ' + detail; return; }
  out.textContent = 'run ' + run_id + ' running...';
  const poll = setInterval(async () => {
    const s = await (await fetch('/tasks/' + run_id)).json();
    if (s.status !== 'running') {
      clearInterval(poll);
      out.textContent = JSON.stringify(s, null, 2);
    }
  }, 2000);
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
