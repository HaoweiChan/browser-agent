"""Deploy spike: proves the platform stack — FastAPI + SSE + headless Chromium.

Grows into the M1 gateway (POST /tasks, run records, trace streaming);
the inline smoke page is replaced by the real frontend at M4.
"""

import asyncio
import hashlib
import html
import ipaddress
import json
import re
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .agent import assemble_result, run_task
from .mutate import apply_mutation
from .planner import ALLOWED_MODELS, DEFAULT_MODEL, live_planner

app = FastAPI(title="browser-agent")
FIXTURE_DIR = (Path(__file__).parent / "fixtures").resolve()
RUN_ROOT = Path("/tmp/runs")

# ponytail: in-memory run store + semaphore(1) — persisted records and higher
# concurrency if this ever serves more than one reviewer at a time; per-IP rate
# limiting stays BACKLOG. RUNS/STREAMS grow for the process lifetime, bounded in
# practice by the action budget and by nobody hammering a demo endpoint.
RUNS: dict[str, dict] = {}
STREAMS: dict[str, asyncio.Queue] = {}
SEM = asyncio.Semaphore(1)


# --- Support matrix --------------------------------------------------------
# docs/support-matrix.md is the single source: humans read the markdown, the
# frontend reads this parse of it. A second hand-maintained copy would drift,
# and the honesty table is the last place drift is acceptable.

MATRIX_DOC = Path(__file__).parents[2] / "docs" / "support-matrix.md"
TCS = ["TC1", "TC2", "TC3", "TC4", "TC5"]
# A citation is a backticked bare token with a hyphen and no path/extension —
# i.e. a case id. `full`, `fast`, `unsupported` (no hyphen) and
# `evals/report/....json` (slashes, dot) are deliberately not citations.
CASE_CITATION = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")
SHOT = re.compile(r"step_\d+\.png")


def parse_matrix(text: str | None = None) -> dict:
    """Markdown tables -> {rows, limitations, citation_text}.

    Fenced blocks are stripped before citations are collected: the entry-shape
    example in the doc cites `tc2-wiki-004`, which is illustrative and has no
    case file behind it."""
    text = MATRIX_DOC.read_text(encoding="utf-8") if text is None else text
    body, section, fenced, block = [], "", False, []
    rows, limitations = [], []
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        body.append(line)
        if line.startswith("## "):
            section = line[3:].strip().lower()
        if not line.startswith("|"):
            block = []  # any non-table line ends the current table block
            continue
        # A table is a CONTIGUOUS block whose second line is the delimiter. A row
        # that drifts a blank line away from its table still parses fine here —
        # and renders as a literal paragraph of pipes. That has now happened
        # twice: D10 in PR #12, fixed by hand and unguarded, and D14 in PR #15
        # (R20), which is the disclosure that no ablation cell measures the model
        # the system actually runs on. An honesty row that quietly stops being a
        # row is the honesty artifact failing in the flattering direction.
        block.append(line)
        if len(block) == 2 and set("".join(block[1].strip("|").split("|"))) > set("-: "):
            raise ValueError(f"support matrix: table row {block[0][:60]!r} is not part of a "
                             "table — no delimiter row follows its header. A row separated "
                             "from its table by a blank line renders as a paragraph of pipes")
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue  # header underline
        # Strict on width, not tolerant: a row that does not fit the shape used
        # to be skipped, so a single malformed row disappeared from the rendered
        # matrix while everything around it still parsed.
        if section.startswith("current matrix") and cells[0] != "Domain":
            if len(cells) != len(TCS) + 1:
                raise ValueError(f"support matrix: row {cells[0]!r} has {len(cells)} cells, "
                                 f"expected {len(TCS) + 1}")
            rows.append({"domain": cells[0], "cells": dict(zip(TCS, cells[1:]))})
        elif section.startswith("declared limitations") and cells[0] != "Limitation":
            if len(cells) != 3:
                raise ValueError(f"support matrix: limitation {cells[0][:40]!r} has "
                                 f"{len(cells)} cells, expected 3")
            limitations.append(dict(zip(("limitation", "evidence", "status"), cells)))
    # Loud, never quietly empty. Both sections are keyed on a heading prefix and
    # an exact cell count, so a renamed heading, an added column or one
    # unbalanced fence used to yield zero entries — and the frontend rendered a
    # clean header-only table, i.e. an agent declaring no limitations at all.
    # That is the honesty artifact failing in the flattering direction
    # (case matrix-parse-fails-loudly).
    for name, found in (("current matrix", rows), ("declared limitations", limitations)):
        if not found:
            raise ValueError(
                f"support matrix: '{name}' section parsed to zero entries — the heading, the "
                "column count or a code fence in docs/support-matrix.md changed")
    return {"rows": rows, "limitations": limitations, "citation_text": "\n".join(body)}


@app.get("/support-matrix")
async def support_matrix():
    return parse_matrix()


# Decimal/octal/hex/dotted-short IP literals ("2130706433", "127.1",
# "0x7f000001", "0x7f.0.0.1") raise ValueError in ipaddress but Chromium still
# normalizes them to real IPs (case url-guard-literal-ips).
IP_LITERAL = re.compile(r"(?:0x[0-9a-f]+|\d+)(?:\.(?:0x[0-9a-f]+|\d+))*$")


def url_ok(u: str) -> bool:
    """http/https only, no loopback/private/link-local hosts in any spelling.
    ponytail: hostname DNS-rebinding defense is BACKLOG (docs/plans)."""
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower().rstrip(".")
    if not host or host == "localhost":
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return not IP_LITERAL.match(host)  # named host unless an IP in disguise
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


class TaskIn(BaseModel):
    task: str
    url: str | None = None
    # The M9 ablation's independent variable. Absent means the default; anything
    # else must be on `planner.ALLOWED_MODELS` — the ablation set plus the
    # incumbent default, which stays reachable by explicit name even though it is
    # priced out of the comparison (ADR-010 Decision 6). This endpoint is public and
    # unauthenticated and OpenRouter bills whatever id it is handed, so an
    # unbounded field here is a stranger pointing this deployment's key at the
    # priciest model on the platform — and the run budgets would not notice,
    # because they count tokens, not price (case gateway-model-not-allowlisted).
    model: str | None = None


def _env_failure(reason: str, model: str | None = None) -> dict:
    """A contract-shaped result for a run that never got off the ground."""
    return assemble_result(
        [], None,
        {"actions": 0, "llm_tokens": 0, "llm_usd": 0.0, "replans": 0, "ms": 0},
        failure="env", reason=reason, model=model)


async def _execute(run_id: str, task: str, url: str | None, model: str):
    q = STREAMS[run_id]
    result = None
    async with SEM:
        try:
            result = await run_task(
                task, url, live_planner(model), RUN_ROOT / run_id, url_guard=url_ok,
                # Echoed back on the record so a committed ablation report is
                # self-attributing rather than trusting the driver's loop variable.
                model=model,
                # Copy on emit: the executor keeps mutating its record (a later
                # supersede lands on an attempt already sent). The final `done`
                # event carries the authoritative trace; steps stream as they are.
                on_step=lambda rec: q.put_nowait({"event": "step", "step": dict(rec)}),
            )
        except Exception as e:  # loud, never a hung "running"
            # Through the same assembler a real run uses: a hand-built dict here
            # drifted from the contract with evidence/budgets_spent null, and the
            # frontend renders both (gateway-error-contract-shape). Empty trace is
            # correct — live_planner() validates the key before a browser opens,
            # so nothing was attempted; only the shape was ever wrong.
            result = _env_failure(f"{type(e).__name__}: {e}", model)
        finally:
            # A run must always reach a terminal state. When the error path
            # itself raised (a NameError, once), the record stayed "running" and
            # the SSE stream never closed — a hung connection on a public
            # endpoint, and a reviewer watching a spinner with no end.
            if result is None:
                result = _env_failure("run ended without producing a result", model)
            RUNS[run_id] = result
            q.put_nowait({"event": "done", "result": result})


@app.post("/tasks")
async def submit_task(t: TaskIn):
    if not t.task.strip() or len(t.task) > 500:
        raise HTTPException(422, "task must be 1-500 chars")
    if t.url and not url_ok(t.url):
        raise HTTPException(422, "url blocked: http/https public hosts only")
    # `is not None`, not truthiness: an absent field and an explicit `null` both
    # mean "not specified" and default; `""` does not. JSON null IS the absent
    # value for an optional field, and Pydantic cannot tell the two apart here
    # anyway — so the rule is written as it behaves rather than the other way
    # round, and pinned by a row in gateway-model-reaches-planner (PR #15, R8).
    if t.model is not None and t.model not in ALLOWED_MODELS:
        raise HTTPException(422, "model blocked: allowlisted models only — "
                                 + ", ".join(ALLOWED_MODELS))
    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = {"status": "running"}
    STREAMS[run_id] = asyncio.Queue()
    asyncio.get_event_loop().create_task(
        _execute(run_id, t.task, t.url, t.model or DEFAULT_MODEL))
    return {"run_id": run_id}


@app.get("/tasks/{run_id}")
async def get_task(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run_id")
    return RUNS[run_id]


@app.get("/tasks/{run_id}/stream")
async def stream_task(run_id: str):
    """Live trace. Every attempt the executor makes is emitted, including the
    ones a recovery ladder later supersedes — a viewer that showed only the
    steps that worked would report a tidier run than the one that happened
    (evals/adversarial/stream-shows-every-step.json).

    ponytail: one consumer per run — the queue is drained, so a second viewer
    (or a reconnect) sees only what is left and then the `done` event. Polling
    GET /tasks/{id} remains the complete-result path for anyone who missed it.
    """
    if run_id not in STREAMS:
        raise HTTPException(404, "unknown run_id")
    q = STREAMS[run_id]

    async def gen():
        while True:
            ev = await q.get()
            yield f"data: {json.dumps(ev)}\n\n"
            if ev["event"] == "done":
                return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/runs/{run_id}/{shot}")
async def run_screenshot(run_id: str, shot: str):
    """Per-step screenshots — the visual half of inspecting a failure. Both
    path components are pattern-checked rather than joined and hoped for."""
    if not run_id.isalnum() or not SHOT.fullmatch(shot):
        raise HTTPException(404, "no such screenshot")
    path = RUN_ROOT / run_id / shot
    if not path.is_file():
        raise HTTPException(404, "no such screenshot")
    return FileResponse(path, media_type="image/png")

SMOKE_URL = "https://example.com"

# ponytail: one inline page, no build step, no framework. It is a trace viewer
# and a form; a bundler would be more machinery than the thing it ships.
PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>browser-agent</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {
    --bg:#0f1115; --panel:#161a21; --line:#262c36; --fg:#dbe1ea; --dim:#8b95a5;
    --ok:#4ade80; --bad:#f87171; --warn:#fbbf24; --accent:#60a5fa;
  }
  * { box-sizing:border-box }
  body { margin:0; padding:2rem 1.25rem 4rem; background:var(--bg); color:var(--fg);
         font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif }
  main { max-width:60rem; margin:0 auto }
  h1 { font-size:1.4rem; margin:0 0 .25rem }
  h2 { font-size:1rem; text-transform:uppercase; letter-spacing:.08em; color:var(--dim);
       margin:2.5rem 0 .75rem; font-weight:600 }
  p.sub { color:var(--dim); margin:0 0 1.5rem }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:1rem }
  input, button, select { font:inherit }
  input, select { background:#0b0e13; border:1px solid var(--line); color:var(--fg);
          border-radius:6px; padding:.55rem .7rem; width:100% }
  .row { display:flex; gap:.6rem; flex-wrap:wrap; margin-bottom:.6rem }
  .row > * { flex:1 1 16rem }
  button { background:var(--accent); border:0; color:#06121f; font-weight:600;
           border-radius:6px; padding:.55rem 1.1rem; cursor:pointer; flex:0 0 auto }
  button.ghost { background:transparent; border:1px solid var(--line); color:var(--dim) }
  button:disabled { opacity:.5; cursor:not-allowed }
  code, pre { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px }
  pre { overflow-x:auto; background:#0b0e13; border:1px solid var(--line); border-radius:6px;
        padding:.7rem; margin:.5rem 0 0; white-space:pre-wrap; word-break:break-word }
  .step { border:1px solid var(--line); border-left:3px solid var(--line);
          border-radius:6px; padding:.6rem .8rem; margin-bottom:.5rem; background:var(--panel) }
  .step.failed { border-left-color:var(--bad) }
  .step.recovered { border-left-color:var(--accent) }
  .step.superseded { opacity:.62 }
  .hd { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap }
  .i { color:var(--dim); font-family:ui-monospace,monospace }
  .act { font-weight:650 }
  .badge { font-size:11px; padding:.1rem .45rem; border-radius:99px; border:1px solid var(--line);
           color:var(--dim); font-family:ui-monospace,monospace; white-space:nowrap }
  .badge.ok { color:var(--ok); border-color:#1e4b32 }
  .badge.bad { color:var(--bad); border-color:#5b2626 }
  .badge.warn { color:var(--warn); border-color:#5c451a }
  .badge.acc { color:var(--accent); border-color:#204066 }
  .ms { margin-left:auto; color:var(--dim); font-size:12px; font-family:ui-monospace,monospace }
  details summary { cursor:pointer; color:var(--dim); font-size:12.5px; margin-top:.5rem }
  img.shot { max-width:100%; border:1px solid var(--line); border-radius:6px; margin-top:.5rem }
  table { border-collapse:collapse; width:100%; font-size:13.5px }
  th, td { border:1px solid var(--line); padding:.45rem .6rem; text-align:left; vertical-align:top }
  th { color:var(--dim); font-weight:600; background:#12161d }
  td.supported { color:var(--ok) } td.unreliable { color:var(--warn) }
  td.unsupported { color:var(--bad) } td.none { color:#4b5563 }
  .note { color:var(--dim); font-size:13px }
  .status-line { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin-bottom:.6rem }
  .big { font-size:1.05rem; font-weight:650 }
  .big.success { color:var(--ok) } .big.failure { color:var(--bad) }
  .big.unsupported { color:var(--warn) } .big.running { color:var(--accent) }
  a { color:var(--accent) }
</style>
<main>
<h1>browser-agent</h1>
<p class="sub">Natural-language task &rarr; plan &rarr; execute in a real headless Chromium
&rarr; verified result. Every attempt is traced, including the ones a recovery
ladder replaced.</p>

<div class="panel">
  <div class="row">
    <input id="task" placeholder="e.g. What is the price of the Aurora Desk Lamp?">
  </div>
  <div class="row">
    <input id="url" placeholder="start URL (optional) — http/https, public hosts only">
    <button id="go" onclick="submitTask()">Run task</button>
    <button class="ghost" onclick="smoke()">Browser smoke test</button>
  </div>
  <p class="note" id="guards">Guards live on this deployment: URL allow-list (no
    loopback/private/link-local in any spelling), 30 actions and 100k LLM tokens per run,
    2 replans per task, one run at a time. A blocked URL is refused before a browser opens.
    <code>POST /tasks</code> also takes an optional <code>model</code> field, gated on a
    five-model allow-list and refused the same way — this form never sends one, so every
    run started here uses the default planner model.</p>
  <pre id="err" hidden></pre>
</div>

<div id="live" hidden>
  <h2>Trace <span class="note" id="runid"></span></h2>
  <div class="status-line"><span class="big running" id="status">running</span>
    <span class="note" id="budgets"></span></div>
  <div id="steps"></div>
  <div id="result"></div>
</div>

<h2>Support matrix</h2>
<p class="note">Report-assisted, human-declared: the eval report suggests a status, a human
  declares it with a reason. A pass rate does not threshold itself into &ldquo;supported&rdquo;.
  Served from <code>docs/support-matrix.md</code> — the same file the README renders.</p>
<div id="matrix" class="panel">loading&hellip;</div>

<h2>Declared limitations</h2>
<p class="note">What this agent does <em>not</em> do, each citing the case that shows it.</p>
<div id="limits" class="panel">loading&hellip;</div>
</main>

<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let es = null, runId = null;

function badge(text, cls) { return `<span class="badge ${cls||""}">${esc(text)}</span>`; }

// postcondition_ok is three-valued and null is NOT true: it means nothing was
// asserted about this step. Collapsing null into "ok" here would show a green
// tick on exactly the unverified action the contract calls a failure.
function postBadge(v) {
  if (v === true) return badge("postcondition ok", "ok");
  if (v === false) return badge("postcondition failed", "bad");
  return badge("unverified", "warn");
}

function stepEl(s) {
  const cls = [s.failure_class ? "failed" : "",
               s.retry_or_recovery === "recovery" ? "recovered" : "",
               s.superseded_by ? "superseded" : ""].join(" ");
  const t = s.target ? JSON.stringify(s.target) : (s.value || "");
  let b = "";
  if (s.retry_or_recovery === "recovery") b += badge("RECOVERY — new strategy", "acc");
  if (s.retry_or_recovery === "retry") b += badge("retry", "warn");
  if (s.resolved && s.resolved.tier) b += badge("tier:" + s.resolved.tier);
  b += postBadge(s.postcondition_ok);
  if (s.failure_class) b += badge("failure:" + s.failure_class, "bad");
  if (s.superseded_by) b += badge("superseded by #" + s.superseded_by);
  const shot = s.screenshot && runId
    ? `<img class="shot" loading="lazy" src="/runs/${runId}/${esc(s.screenshot)}">` : "";
  return `<div class="step ${cls}">
    <div class="hd"><span class="i">#${s.i}</span><span class="act">${esc(s.action)}</span>
      <code>${esc(t.length > 90 ? t.slice(0, 90) + "…" : t)}</code>
      ${b}<span class="ms">${s.ms}ms</span></div>
    <details><summary>step detail${s.screenshot ? " + screenshot" : ""}</summary>
      <pre>${esc(JSON.stringify(s, null, 2))}</pre>${shot}</details>
  </div>`;
}

function renderSteps(steps) { $("steps").innerHTML = steps.map(stepEl).join(""); }

function renderResult(r) {
  const kind = r.status.split(":")[0];
  $("status").className = "big " + kind;
  $("status").textContent = r.status;
  const b = r.budgets_spent;
  $("budgets").textContent = b
    ? `${b.actions} actions · ${b.llm_tokens} tok · $${(b.llm_usd || 0).toFixed(4)} · ${b.replans} replans · ${b.ms}ms`
    : "";
  // Re-render from the final trace: it is authoritative where the live stream is
  // provisional — a supersede lands after its attempt was already sent.
  if (r.evidence && r.evidence.trace) renderSteps(r.evidence.trace);
  const v = r.verdict;
  $("result").innerHTML = `<div class="panel" style="margin-top:1rem">
    <div><b>Answer</b></div>
    <pre>${esc(r.answer === null || r.answer === undefined
        ? "(none)" : JSON.stringify(r.answer, null, 2))}</pre>
    ${r.reason ? `<div style="margin-top:.8rem"><b>Reason</b></div><pre>${esc(r.reason)}</pre>` : ""}
    <div style="margin-top:.8rem"><b>Verifier</b> ${v
        ? badge(v.verdict, v.verdict === "PASS" ? "ok" : "bad") +
          badge("layer " + v.layer) +
          badge(v.ground_truth ? "external ground truth" : "runtime predicates only",
                v.ground_truth ? "ok" : "warn")
        : badge("not reached", "warn")}</div>
    ${v ? `<pre>${esc(JSON.stringify(v.checks, null, 2))}</pre>` : ""}
  </div>`;
}

async function submitTask() {
  const task = $("task").value.trim();
  if (!task) return;
  $("go").disabled = true;
  $("err").hidden = true;
  $("live").hidden = false;
  $("steps").innerHTML = ""; $("result").innerHTML = "";
  $("status").className = "big running"; $("status").textContent = "running";
  $("budgets").textContent = ""; $("runid").textContent = "";
  if (es) es.close();
  try {
    const r = await fetch("/tasks", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task, url: $("url").value.trim() || null}),
    });
    const data = await r.json();
    if (!r.ok) {
      // A refusal is a terminal path too: without this the guard working once
      // disables the form for good, and the UI looks broken by its own success.
      $("go").disabled = false;
      $("live").hidden = true;
      $("err").hidden = false;
      $("err").textContent = "rejected (" + r.status + "): " +
        (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      return;
    }
    runId = data.run_id;
    $("runid").textContent = "run " + runId;
    es = new EventSource("/tasks/" + runId + "/stream");
    const live = [];
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.event === "step") { live.push(ev.step); renderSteps(live); }
      else if (ev.event === "done") { es.close(); renderResult(ev.result); $("go").disabled = false; }
    };
    es.onerror = () => {  // stream dropped — the run record is still the truth
      es.close();
      fetch("/tasks/" + runId).then(x => x.json()).then(s => {
        if (s.status !== "running") renderResult(s);
        else { $("status").textContent = "stream lost — reload to poll"; }
        $("go").disabled = false;
      });
    };
  } catch (e) {
    $("err").hidden = false; $("err").textContent = String(e); $("go").disabled = false;
  }
}

function smoke() {
  $("live").hidden = false;
  $("steps").innerHTML = ""; $("result").innerHTML = "";
  $("runid").textContent = "platform smoke — real Chromium, no LLM spend";
  $("status").className = "big running"; $("status").textContent = "running";
  const s = new EventSource("/smoke/stream");
  const lines = [];
  s.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    lines.push(e.data);
    $("steps").innerHTML = `<pre>${esc(lines.join("\n"))}</pre>`;
    if (ev.event === "done" || ev.event === "error") {
      s.close();
      $("status").className = "big " + (ev.event === "done" ? "success" : "failure");
      $("status").textContent = ev.event === "done" ? "chromium ok" : "chromium failed";
    }
  };
  s.onerror = () => s.close();
}

fetch("/support-matrix").then(r => r.json()).then(m => {
  // The task-class columns come from the payload, not a second hardcoded list:
  // parse_matrix refuses to return zero rows, so rows[0] is always there.
  const TCS = Object.keys(m.rows[0].cells);
  $("matrix").innerHTML = `<table><tr><th>Domain</th>${
    TCS.map(t => `<th>${t}</th>`).join("")}</tr>${
    m.rows.map(row => `<tr><td>${esc(row.domain)}</td>${TCS.map(t => {
      const v = row.cells[t] || "—";
      const cls = ["supported","unreliable","unsupported"].includes(v) ? v : "none";
      return `<td class="${cls}">${esc(v)}</td>`;
    }).join("")}</tr>`).join("")}</table>`;
  $("limits").innerHTML = `<table><tr><th>Limitation</th><th>Evidence</th><th>Status</th></tr>${
    m.limitations.map(l => `<tr><td>${esc(l.limitation)}</td><td><code>${
      esc(l.evidence)}</code></td><td>${esc(l.status)}</td></tr>`).join("")}</table>`;
}).catch(e => { $("matrix").textContent = "support matrix unavailable: " + e; });
</script>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/healthz")
async def healthz():
    return {"ok": True}


# --- Fixture sites ---------------------------------------------------------
# Served through the mutation layer rather than StaticFiles: `?mut=` is the
# self-maintenance ground truth, so it has to sit on the only serving path.
# The forms fixture's last submission is the eval's external ground truth.

FORM_STATE: dict = {}

CONFIRM = """<!doctype html>
<meta charset="utf-8">
<title>Enquiry received — Nimbus Shop</title>
<h1>Enquiry received</h1>
<p>Thank you, {name}.</p>
<div role="group" aria-label="Reference"><span>{ref}</span></div>
<p><a href="/fixtures/forms.html">Send another</a></p>
"""


@app.post("/fixtures/forms/submit", response_class=HTMLResponse)
async def forms_submit(request: Request):
    body = (await request.body()).decode()
    data = {k: v[0] for k, v in parse_qs(body).items()}
    ref = "REF-" + hashlib.sha1(
        f"{data.get('name', '')}|{data.get('email', '')}".encode()
    ).hexdigest()[:6].upper()
    FORM_STATE.clear()
    FORM_STATE.update({**data, "ref": ref})
    return CONFIRM.format(name=html.escape(data.get("name", "")), ref=ref)


@app.get("/fixtures/forms/state")
async def forms_state():
    """Ground truth for TC5 — what the server actually received."""
    return FORM_STATE


@app.post("/fixtures/forms/reset")
async def forms_reset():
    FORM_STATE.clear()
    return {"ok": True}


@app.get("/fixtures/hang.png")
async def fixture_hang():
    """A subresource that never arrives, so the page referencing it never fires
    `load`. openlibrary.org's edition pages behave exactly like this in the
    wild — the document and every word of its content are there in seconds
    while one asset hangs (case nav-load-event-never-fires). Async sleep, so it
    parks a coroutine rather than a worker; the eval closes the page long
    before this returns."""
    await asyncio.sleep(120)
    raise HTTPException(504, "unreachable by design")


@app.get("/fixtures/{name}", response_class=HTMLResponse)
async def fixture(name: str, mut: str | None = None):
    path = (FIXTURE_DIR / name).resolve()
    if path.parent != FIXTURE_DIR or not path.is_file():
        raise HTTPException(404, "no such fixture")
    try:
        return apply_mutation(path.read_text(), mut)
    except KeyError as e:
        raise HTTPException(422, str(e)) from e


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
