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
from .judge import live_judge
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
# The run currently holding SEM, for /readyz. One variable rather than a registry:
# concurrency is 1 by design, so "which run" has exactly one answer or none.
ACTIVE_RUN: str | None = None


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


def _is_delimiter(line: str) -> bool:
    """`|---|---|` and friends. Nothing else: an em-dash cell is content."""
    cells = line.strip("|").split("|")
    return bool(cells) and "-" in line and set("".join(cells)) <= set("-: ")


def _check_block(block: list) -> None:
    """A markdown table is a CONTIGUOUS run of `|` lines: header, delimiter, rows.

    A row that drifts a blank line away from its table still parses line-by-line
    and renders as a literal paragraph of pipes. That has now happened three
    times — D10 (PR #12, fixed by hand, unguarded), D14 (PR #15 R20), and D14
    again because the first guard missed it (R22). D14 is the disclosure that no
    ablation cell measures the model the system actually runs on, so an honesty
    row that stops being a row is the honesty artifact failing in the flattering
    direction.

    Both of the first guard's bugs are worth naming, because both made it pass on
    the case it was written for: it only ran when a block reached exactly two
    lines, so a row orphaned as the LAST of its table (D14's position) formed a
    one-line block nothing checked; and it tested `> set("-: ")`, a proper
    superset, so it fired only when the next line happened to contain all of
    `-`, `:` and space — an em-dash row read as a delimiter. 29 of the file's 33
    data rows could be orphaned silently. Checking the whole block, at the point
    it closes, has neither hole."""
    if not block:
        return
    if len(block) < 2 or not _is_delimiter(block[1]):
        raise ValueError(
            f"support matrix: table row {block[0][:60]!r} is not part of a table — a "
            f"{len(block)}-line block with no header/delimiter pair. A row separated from "
            "its table by a blank line renders as a paragraph of pipes")


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
            _check_block(block)  # any non-table line ends the current block
            block = []
            continue
        block.append(line)
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
    _check_block(block)  # a table running to EOF still has to be a table
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
    global ACTIVE_RUN
    q = STREAMS[run_id]
    result = None
    async with SEM:
        ACTIVE_RUN = run_id
        try:
            result = await run_task(
                task, url, live_planner(model), RUN_ROOT / run_id,
                judge=live_judge(), url_guard=url_ok,
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
            ACTIVE_RUN = None
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
<title>Browser Agent</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090d13">
<style>
  /* TinBoker terminal language, blended into this repo's evidence-first UI:
     amber drives commands, cyan marks interaction/recovery, and the trace keeps
     the room that the SEC inspector gives its document pane. */
  :root {
    --bg:#090d13; --panel:#0f151d; --raised:#141c26; --line:#253240;
    --fg:#dce7ee; --dim:#91a0ad; --amber:#f4ae2b; --amber-ink:#ffc65c;
    --on-amber:#171004; --accent:#3ac6d8; --ok:#47d683; --bad:#ff7a83;
    --warn:var(--amber-ink); --grid:rgb(58 198 216 / .07);
    --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
    --radius:3px; --speed:150ms cubic-bezier(.4,0,.2,1);
    color-scheme:dark;
  }
  @media (prefers-color-scheme:light) { :root {
    --bg:#e9e6dc; --panel:#f7f4eb; --raised:#efebe1; --line:#c9c2b2;
    --fg:#1a222a; --dim:#53606a; --amber:#965600; --amber-ink:#744100;
    --on-amber:#fff; --accent:#006d7a; --ok:#0d6b3a; --bad:#a82b3a;
    --warn:var(--amber-ink); --grid:rgb(56 72 84 / .08);
    --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
    --radius:3px; --speed:150ms cubic-bezier(.4,0,.2,1);
    color-scheme:light;
  } }
  * { box-sizing:border-box }
  html { min-height:100%; background:var(--bg) }
  body { margin:0; min-height:100vh; background-color:var(--bg); color:var(--fg);
         font:14px/1.6 var(--mono); letter-spacing:-.01em;
         background-image:linear-gradient(var(--grid) 1px,transparent 1px),
           linear-gradient(90deg,var(--grid) 1px,transparent 1px),
           radial-gradient(900px 520px at 50% -12%,rgb(58 198 216 / .08),transparent 65%);
         background-size:44px 44px,44px 44px,100% 100%; background-attachment:fixed }
  body::before { content:""; position:fixed; inset:0 0 auto; height:2px; z-index:100;
         pointer-events:none; background:linear-gradient(90deg,var(--amber),var(--accent),var(--amber)) }
  header, main, footer { width:min(100% - 2.5rem,78rem); margin-inline:auto }
  header { padding:2.6rem 0 1.35rem; border-bottom:1px solid var(--line) }
  .mast { display:flex; justify-content:space-between; gap:1.5rem; align-items:flex-start }
  .eyebrow { color:var(--amber-ink); font-size:11px; font-weight:700;
         letter-spacing:.14em; text-transform:uppercase }
  .signal { color:var(--accent); border:1px solid var(--accent); padding:.16rem .45rem;
         font-size:11px; letter-spacing:.09em; text-transform:uppercase; white-space:nowrap }
  h1 { font-size:clamp(1.7rem,4.4vw,2.48rem); line-height:1.1; margin:.35rem 0 .55rem;
         letter-spacing:-.055em; font-weight:800 }
  h1::before { content:"> "; color:var(--amber-ink); font-weight:600 }
  h2 { display:flex; align-items:center; gap:.65rem; color:var(--fg); font-size:12px;
       text-transform:uppercase; letter-spacing:.12em; margin:2rem 0 .7rem; font-weight:700 }
  h2::after { content:""; height:1px; background:var(--line); flex:1 }
  .section-no { color:var(--amber-ink) }
  p.sub { color:var(--dim); max-width:52rem; margin:0 }
  main { padding-bottom:1rem }
  .panel { background:var(--panel); border:1px solid var(--line);
       border-radius:var(--radius); padding:1rem; box-shadow:0 18px 50px rgb(0 0 0 / .08) }
  .command { border-top:2px solid var(--amber) }
  label { display:block; color:var(--dim); font-size:11px; font-weight:700;
       letter-spacing:.1em; text-transform:uppercase; margin:0 0 .3rem }
  input, button, select { font:inherit }
  input, select { background:var(--bg); border:1px solid var(--line); color:var(--fg);
       border-radius:var(--radius); padding:.6rem .7rem; width:100%; min-width:0;
       transition:border-color var(--speed),background-color var(--speed) }
  input:hover, select:hover { border-color:color-mix(in srgb,var(--fg) 32%,var(--line)) }
  input::placeholder { color:var(--dim) }
  .row { display:flex; gap:.65rem; flex-wrap:wrap; margin-bottom:.7rem; align-items:flex-end }
  .field { flex:1 1 20rem }
  .actions { display:flex; gap:.55rem; flex:0 0 auto }
  button { background:var(--amber); border:1px solid var(--amber); color:var(--on-amber);
       font-weight:800; border-radius:var(--radius); padding:.6rem 1rem; cursor:pointer;
       flex:0 0 auto; text-transform:uppercase; letter-spacing:.06em; font-size:12px;
       transition:background-color var(--speed),border-color var(--speed),color var(--speed),transform var(--speed) }
  button:not(.ghost):hover:not(:disabled) { background:color-mix(in srgb,var(--amber) 86%,var(--bg)); transform:translateY(-1px) }
  button.ghost { background:transparent; border-color:var(--accent); color:var(--accent) }
  button.ghost:hover:not(:disabled) { background:color-mix(in srgb,var(--accent) 10%,transparent) }
  button:disabled { opacity:.5; cursor:not-allowed }
  :focus-visible { outline:2px solid var(--accent); outline-offset:2px }
  code, pre { font-family:var(--mono); font-size:13px }
  pre { overflow-x:auto; background:var(--bg); border:1px solid var(--line);
       border-radius:var(--radius); padding:.8rem; margin:.55rem 0 0;
       white-space:pre-wrap; word-break:break-word }
  #err { border-color:var(--bad); color:var(--bad) }
  #live { scroll-margin-top:1rem }
  .step { position:relative; border:1px solid var(--line); border-left:3px solid var(--line);
       border-radius:var(--radius); padding:.72rem .85rem; margin-bottom:.55rem;
       background:var(--panel); transition:border-color var(--speed),background-color var(--speed) }
  .step:hover { background:var(--raised) }
  .step.failed { border-left-color:var(--bad) }
  .step.recovered { border-left-color:var(--accent) }
  .step.superseded { border-style:dashed; background:color-mix(in srgb,var(--dim) 5%,var(--panel)) }
  .hd { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap }
  .hd > code { min-width:0; overflow-wrap:anywhere }
  .i { color:var(--amber-ink); font-weight:700 }
  .act { font-weight:750 }
  .badge { font-size:11px; padding:.1rem .4rem; border-radius:var(--radius);
       border:1px solid var(--line); color:var(--dim); white-space:nowrap;
       text-transform:uppercase; letter-spacing:.04em }
  .badge.ok { color:var(--ok); border-color:var(--ok) }
  .badge.bad { color:var(--bad); border-color:var(--bad) }
  .badge.warn { color:var(--warn); border-color:var(--warn) }
  .badge.acc { color:var(--accent); border-color:var(--accent) }
  .ms { margin-left:auto; color:var(--dim); font-size:12px }
  details summary { cursor:pointer; color:var(--dim); font-size:12px; margin-top:.5rem;
       text-transform:uppercase; letter-spacing:.06em }
  details summary:hover { color:var(--accent) }
  img.shot { max-width:100%; border:1px solid var(--line); border-radius:var(--radius); margin-top:.65rem }
  .table-wrap { overflow:auto; padding:0 }
  table { border-collapse:collapse; width:100%; min-width:42rem; font-size:13px }
  th, td { border:1px solid var(--line); padding:.55rem .65rem; text-align:left; vertical-align:top }
  th { color:var(--amber-ink); font-weight:700; background:var(--raised);
       text-transform:uppercase; font-size:11px; letter-spacing:.07em }
  td.supported { color:var(--ok) } td.unreliable { color:var(--warn) }
  td.unsupported { color:var(--bad) } td.none { color:var(--dim) }
  .note { color:var(--dim); font-size:13px }
  #guards::before { content:"guardrails :: "; color:var(--amber-ink); font-weight:700 }
  .status-line { display:flex; gap:.7rem; align-items:center; flex-wrap:wrap; margin-bottom:.7rem }
  .big { font-size:13px; font-weight:800; text-transform:uppercase; letter-spacing:.08em;
       border:1px solid currentColor; padding:.17rem .45rem }
  .big.success { color:var(--ok) } .big.failure { color:var(--bad) }
  .big.unsupported { color:var(--warn) } .big.running { color:var(--accent) }
  .progress { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.4rem;
       list-style:none; margin:0 0 .9rem; padding:0 }
  .progress li { min-width:0; border:1px solid var(--line); border-left:3px solid var(--line);
       padding:.42rem .5rem; color:var(--dim); font-size:11px; line-height:1.25;
       text-transform:uppercase; letter-spacing:.05em }
  .progress li::before { content:"○ "; color:var(--dim) }
  .progress li[data-state="complete"] { border-left-color:var(--ok); color:var(--fg) }
  .progress li[data-state="complete"]::before { content:"✓ "; color:var(--ok) }
  .progress li[data-state="current"] { border-left-color:var(--accent); color:var(--fg);
       background:color-mix(in srgb,var(--accent) 8%,var(--panel)) }
  .progress li[data-state="current"]::before { content:"› "; color:var(--accent) }
  .progress li[data-state="failed"] { border-left-color:var(--bad); color:var(--bad) }
  .progress li[data-state="failed"]::before { content:"× "; color:var(--bad) }
  .limits-summary { margin:0; padding-left:1.2rem; color:var(--fg) }
  .limits-summary li + li { margin-top:.35rem }
  .limit-details { margin-top:.9rem }
  .limit-details > div { margin-top:.65rem }
  a { color:var(--accent) }
  footer { color:var(--dim); border-top:1px solid var(--line); padding:1rem 0 2.5rem;
       font-size:12px; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap }
  @media (max-width:680px) {
    header, main, footer { width:min(100% - 1.25rem,78rem) }
    header { padding-top:1.8rem }
    .mast { display:block }
    .signal { display:inline-block; margin-top:.8rem }
    .actions, .actions button { width:100% }
    .actions { flex-wrap:wrap }
    .ms { margin-left:0; width:100% }
    .panel { padding:.8rem }
  }
  @media (prefers-reduced-motion:reduce) {
    *,*::before,*::after { scroll-behavior:auto!important; transition:none!important; animation:none!important }
  }
</style>
<header>
  <div class="mast">
    <div>
      <div class="eyebrow">human-review console / browser runtime</div>
      <h1>Browser Agent</h1>
      <p class="sub">Natural-language task &rarr; plan &rarr; execute in a real headless Chromium
      &rarr; verified result. Every attempt is traced, including the ones a recovery
      ladder replaced.</p>
    </div>
    <span class="signal">trace first</span>
  </div>
</header>

<main>
<h2><span class="section-no">01</span> Run task</h2>

<div class="panel command">
  <div class="row">
    <div class="field"><label for="task">Task instruction</label>
      <input id="task" placeholder="e.g. What is the price of the Aurora Desk Lamp?"></div>
    <div class="field"><label for="url">Start URL / optional</label>
      <input id="url" placeholder="http/https, public hosts only"></div>
    <div class="actions">
      <button id="go" onclick="submitTask()">Run task</button>
      <button class="ghost" onclick="smoke()">Smoke test</button>
    </div>
  </div>
  <p class="note" id="guards">Guarded: public URLs only (private and loopback hosts blocked) ·
    30 actions · 100k tokens · 2 replans · one active run.</p>
  <pre id="err" hidden></pre>
</div>

<div id="live" hidden>
  <h2><span class="section-no">02</span> Trace <span class="note" id="runid"></span></h2>
  <div class="status-line"><span class="big running" id="status">running</span>
    <span class="note" id="budgets"></span></div>
  <ol class="progress" id="progress" aria-label="Run progress" aria-live="polite">
    <li data-phase="planning" data-state="upcoming">Planning</li>
    <li data-phase="browser" data-state="upcoming">Open page</li>
    <li data-phase="action" data-state="upcoming">Run actions</li>
    <li data-phase="verification" data-state="upcoming">Verify answer</li>
    <li data-phase="complete" data-state="upcoming">Complete</li>
  </ol>
  <div id="steps"></div>
  <div id="result"></div>
</div>

<h2><span class="section-no">03</span> Support matrix</h2>
<p class="note">Report-assisted, human-declared: the eval report suggests a status, a human
  declares it with a reason. A pass rate does not threshold itself into &ldquo;supported&rdquo;.
  Served from <code>docs/support-matrix.md</code> — the same file the README renders.</p>
<div id="matrix" class="panel table-wrap">loading&hellip;</div>

<h2><span class="section-no">04</span> Limitations</h2>
<p class="note">Four headline limits; the full evidence remains below.</p>
<div id="limits" class="panel">loading&hellip;</div>
</main>

<footer><span>Browser Agent / reviewer evidence surface</span><span>amber = command · cyan = interaction / recovery</span></footer>

<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let es = null, runId = null;
const PHASES = ["planning", "browser", "action", "verification", "complete"];
const SUPPORT_LABELS = {
  TC1: "Read a page", TC2: "Search and read", TC3: "Navigate and read",
  TC4: "Compare or sort", TC5: "Submit a form"
};

function progressItems() { return [...$("progress").children]; }
function labelProgress() {
  progressItems().forEach(item => item.setAttribute(
    "aria-label", `${item.textContent} — ${item.dataset.state}`));
}
function setPhase(name) {
  const current = PHASES.indexOf(name);
  progressItems().forEach((item, index) => {
    item.dataset.state = index < current ? "complete" : index === current ? "current" : "upcoming";
    item.toggleAttribute("aria-current", index === current);
  });
  labelProgress();
}
function resetProgress() {
  $("progress").removeAttribute("data-terminal");
  $("progress").querySelector('[data-phase="complete"]').textContent = "Complete";
  setPhase("planning");
}
function phaseFor(s) {
  if (s.action === "navigate") return "browser";
  if (s.action === "extract") return "verification";
  if (s.action === "extract_all") return "verification";
  return "action";
}
function setTerminal(status) {
  const failed = !String(status).startsWith("success");
  const items = progressItems(), active = items.findIndex(item => item.dataset.state === "current");
  items.forEach((item, index) => {
    if (index < PHASES.length - 1 && index <= active) item.dataset.state = "complete";
    item.removeAttribute("aria-current");
  });
  if (failed && active >= 0) items[active].dataset.state = "failed";
  const terminal = items[items.length - 1];
  terminal.dataset.state = failed ? "failed" : "complete";
  terminal.textContent = failed ? "Failed" : "Complete";
  terminal.setAttribute("aria-current", "step");
  $("progress").dataset.terminal = failed ? "failure" : "success";
  labelProgress();
}

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
  setTerminal(r.status);
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
  $("progress").hidden = true;
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
    resetProgress();
    $("progress").hidden = false;
    $("runid").textContent = "run " + runId;
    es = new EventSource("/tasks/" + runId + "/stream");
    const live = [];
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.event === "step") { live.push(ev.step); setPhase(phaseFor(ev.step)); renderSteps(live); }
      else if (ev.event === "done") { es.close(); setTerminal(ev.result.status); renderResult(ev.result); $("go").disabled = false; }
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
  $("progress").hidden = true;
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
    TCS.map(t => `<th>${esc(SUPPORT_LABELS[t] || t)}</th>`).join("")}</tr>${
    m.rows.map(row => `<tr><td>${esc(row.domain)}</td>${TCS.map(t => {
      const v = row.cells[t] || "—";
      const cls = ["supported","unreliable","unsupported"].includes(v) ? v : "none";
      return `<td class="${cls}">${esc(v)}</td>`;
    }).join("")}</tr>`).join("")}</table>`;
  const summary = m.limitations.slice(0, 4);
  const title = (text) => text.replace(/^\*\*D\d+\*\* — /, "").replace(/\s+/g, " ");
  $("limits").innerHTML = `<ul class="limits-summary">${
    summary.map(l => `<li>${esc(title(l.limitation))}</li>`).join("")}</ul>
    <details class="limit-details"><summary>Full limitations and evidence (${m.limitations.length})</summary>
      <div class="table-wrap"><table><tr><th>Limitation</th><th>Evidence</th><th>Status</th></tr>${
        m.limitations.map(l => `<tr><td>${esc(l.limitation)}</td><td><code>${
          esc(l.evidence)}</code></td><td>${esc(l.status)}</td></tr>`).join("")}</table></div>
    </details>`;
}).catch(e => { $("matrix").textContent = "support matrix unavailable: " + e; });
</script>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/readyz")
async def readyz():
    """Can this service BEGIN a new task right now?

    Distinct from /healthz, which stays liveness only and answers `{"ok": true}`
    whether or not the agent can do anything. Through all five aborted ablation
    sweeps /healthz answered in ~0.2s while submissions were failing, so a fast
    /healthz is evidence the process exists and nothing more (support-matrix D18).

    Semantics. `ready` means the run slot is free, so a task submitted now starts
    immediately instead of queueing. It does NOT mean `POST /tasks` would be
    rejected otherwise: submission always succeeds and queues behind `SEM`, so
    readiness is about capacity to *begin*, not permission to *submit*.

    Always HTTP 200, deliberately, including when not ready. The k8s convention
    of 503-when-not-ready is wrong here: "busy with a run" is the normal, healthy
    state of a concurrency-1 demo service, and a 503 invites the platform to
    restart a container that is working exactly as designed.

    What it proves: the event loop is serving requests, and the slot state as the
    app understands it. Crucially, it is served by the SAME event loop that runs
    the agent, so a /readyz that answers promptly with `busy: true` while a run
    executes is positive evidence the loop is NOT blocked — which is one of the
    named open candidates in D18. A slow or absent /readyz is the opposite signal.

    What it does not prove: that a browser can launch, that the network path out
    is healthy, or that a submitted run will succeed. It reads state; it starts
    nothing and spends nothing.
    """
    busy = SEM.locked()
    return {
        "ready": not busy,
        "busy": busy,
        "active_run_id": ACTIVE_RUN,
        "running": sum(1 for r in RUNS.values() if r.get("status") == "running"),
        "reason": f"a run is executing ({ACTIVE_RUN})" if busy else None,
    }


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
