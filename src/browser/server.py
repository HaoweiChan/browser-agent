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
import urllib.error
import urllib.request
from urllib.parse import parse_qs, quote, urlparse

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


# --- Live page view -------------------------------------------------------
# The right-hand panel shows the real page, scrollable, not only a screenshot.
# It cannot iframe the site directly: the sites worth demoing send
# X-Frame-Options/CSP frame-ancestors and refuse to be framed. So the page is
# fetched here and served same-origin.
#
# Three things make that safe enough to expose publicly, and none of them is
# optional:
#  1. `url_ok` on the submitted URL AND on every redirect hop. A proxy that
#     validates only the first URL is an SSRF hole with extra steps -- the
#     redirect is the attack (case view-proxy-refuses-redirect-to-private).
#  2. The response is capped and never streamed unbounded: a demo endpoint that
#     will read an arbitrary number of bytes from an arbitrary host is a way to
#     fill this container's memory from outside it.
#  3. The frontend frames it with `sandbox` and no `allow-scripts` /
#     `allow-same-origin`, so the document lands in an opaque origin with
#     scripting off. `Content-Security-Policy: sandbox` repeats that on the
#     response, because the iframe attribute is the caller's promise and this
#     header is ours -- anything that reaches the endpoint by another route
#     (a pasted link, a fetch) gets the same treatment.
# What it is NOT: the DOM the agent saw. It is a fresh, script-free fetch of the
# same URL, so a page that builds itself with script renders emptier here than
# the trace shows. That is stated on the panel rather than left to be discovered.

VIEW_MAX_BYTES = 3_000_000
VIEW_TIMEOUT_S = 10
VIEW_MAX_REDIRECTS = 5
VIEW_UA = "Mozilla/5.0 (compatible; browser-agent page view; +https://github.com/HaoweiChan/browser-agent)"


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Every hop re-checked. urllib follows redirects inside `urlopen`, so the
    guard has to live in the handler -- checking `resp.url` afterwards means the
    request to the private address has already been made."""

    max_redirections = VIEW_MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_ok(newurl):
            raise urllib.error.HTTPError(
                newurl, 403, "redirect to a blocked host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_page(url: str) -> tuple[bytes, str]:
    opener = urllib.request.build_opener(_GuardedRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": VIEW_UA})
    with opener.open(req, timeout=VIEW_TIMEOUT_S) as resp:
        if not url_ok(resp.url):          # belt and braces: the final hop too
            raise ValueError(f"final URL blocked: {resp.url}")
        # read() one byte past the cap so a truncated body is detectable rather
        # than silently served as if it were the whole page.
        body = resp.read(VIEW_MAX_BYTES + 1)
        return body, resp.url


@app.get("/view")
async def view_page(url: str):
    """The submitted page, fetched server-side and served same-origin so the
    panel can frame and scroll it. Read-only, no cookies, no credentials."""
    if not url_ok(url):
        raise HTTPException(422, "url blocked: http/https public hosts only")
    try:
        body, final = await asyncio.to_thread(_fetch_page, url)
    except Exception as e:  # loud, and never a blank frame with no reason
        raise HTTPException(502, f"could not fetch the page: {type(e).__name__}: {e}") from e
    truncated = len(body) > VIEW_MAX_BYTES
    text = body[:VIEW_MAX_BYTES].decode("utf-8", "replace")
    # <base> so the page's own relative CSS/images resolve against ITS origin
    # rather than ours. Injected after any <meta charset> so it cannot displace
    # one; appended if the document has no <head> at all.
    tag = f'<base href="{html.escape(final, quote=True)}">'
    lower = text.lower()
    cut = lower.find("<head")
    if cut >= 0 and (close := lower.find(">", cut)) >= 0:
        text = text[:close + 1] + tag + text[close + 1:]
    else:
        text = tag + text
    if truncated:
        text += ('<p style="font:14px system-ui;padding:1rem;background:#ffe;border-top:2px solid #ca0">'
                 f'Page view truncated at {VIEW_MAX_BYTES:,} bytes. The run itself read the whole page.</p>')
    return HTMLResponse(text, headers={
        "Content-Security-Policy": "sandbox",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })


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
  /* `hidden` is a `display:none` UA default, and every one of this page's own
     layout rules outranks it: `.status-line{display:flex}` and
     `.progress{display:grid}` both kept rendering under `hidden=true`, so the
     idle panel showed a RUNNING chip with the spinner over an empty progress
     rail while the DOM correctly reported both as hidden. One rule, not a class
     per element -- the attribute is the intent and it should win. */
  [hidden] { display:none !important }
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
  /* The running stage spins. CSS only: the progress case forbids timers in the
     script, and a phase that advances on a clock would be a progress bar that
     lies about the trace. */
  @keyframes spin { to { transform:rotate(1turn) } }
  .progress li[data-state="current"]::after, .big.running::after {
       content:""; display:inline-block; width:.66em; height:.66em; margin-left:.45em;
       vertical-align:-.05em; border:2px solid color-mix(in srgb,var(--accent) 26%,transparent);
       border-top-color:var(--accent); border-radius:50%; animation:spin .75s linear infinite }
  /* Trace on the left, what the browser actually saw on the right. */
  .live-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,25rem);
       gap:.7rem; align-items:start }
  .live-main { min-width:0 }
  .pageview { position:sticky; top:.7rem; max-height:calc(100vh - 1.4rem); overflow:auto;
       padding:.75rem; min-width:0 }
  .pv-hd { display:flex; gap:.5rem; align-items:baseline; justify-content:space-between;
       flex-wrap:wrap; margin-bottom:.5rem }
  .pv-shot img { display:block; width:100%; border:1px solid var(--line); border-radius:var(--radius) }
  .pv-text { margin-top:.7rem }
  .pv-tabs { display:flex; gap:.3rem; margin:0 0 .55rem }
  .pv-tab { background:transparent; border:1px solid var(--line); color:var(--dim);
       padding:.3rem .55rem; font-size:11px; letter-spacing:.05em; flex:1 1 auto }
  .pv-tab[aria-selected="true"] { border-color:var(--accent); color:var(--accent);
       background:color-mix(in srgb,var(--accent) 10%,transparent) }
  .pv-tab:hover:not(:disabled) { color:var(--fg) }
  /* The frame is the point: it scrolls, so a reviewer can read the page the
     task was about instead of squinting at a screenshot of the fold. */
  #pvframe { display:block; width:100%; height:min(62vh,34rem); border:1px solid var(--line);
       border-radius:var(--radius); background:#fff; color-scheme:light }
  #pvframe[hidden] { display:none }
  .scrape { border-left:3px solid var(--accent); padding:.4rem .55rem; margin-top:.4rem;
       background:var(--bg); border-radius:var(--radius); overflow-wrap:anywhere }
  @media (max-width:900px) {
    .live-grid { grid-template-columns:minmax(0,1fr) }
    .pageview { position:static; max-height:none }
  }
  .limits-summary { margin:0; padding-left:1.2rem; color:var(--fg) }
  .limits-summary li + li { margin-top:.35rem }
  a { color:var(--accent) }
  .chip { text-transform:none; letter-spacing:0; font-weight:600; font-size:12px; padding:.35rem .65rem }
  .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(17rem,1fr)); gap:.6rem }
  .card { border:1px solid var(--line); border-radius:var(--radius); padding:.8rem .9rem;
       background:var(--panel); display:flex; flex-direction:column; gap:.45rem }
  .caps { list-style:none; margin:0; padding:0; font-size:13px }
  .caps li + li { margin-top:.15rem }
  .caps .supported { color:var(--ok) } .caps .unreliable { color:var(--warn) }
  .caps .unsupported { color:var(--bad) } .caps .none { color:var(--dim) }
  .card .try { align-self:flex-start }
  .summary { margin:0 0 .7rem; display:flex; gap:.6rem; align-items:center; flex-wrap:wrap }
  .answer { font-size:17px; font-weight:700; white-space:pre-wrap; word-break:break-word;
       margin:.3rem 0 .8rem; padding:.8rem; background:var(--bg);
       border:1px solid var(--line); border-left:3px solid var(--ok) }
  .answer.none { color:var(--dim); font-weight:500; border-left-color:var(--bad) }
  .answer.failed { font-size:13px; font-weight:500; max-height:14rem; overflow:auto; border-left-color:var(--bad) }
  .checks { display:flex; gap:.35rem; flex-wrap:wrap; margin-top:.45rem }
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
      <h1>Browser Agent</h1>
      <p class="sub">Ask a question about a web page &mdash; a real browser does the work
      and every step is shown, failures included.</p>
    </div>
    <span class="signal">trace first</span>
  </div>
</header>

<main>
<h2><span class="section-no">01</span> Run task</h2>

<div class="panel command">
  <div class="row">
    <div class="field"><label for="task">What should it find?</label>
      <input id="task" placeholder="e.g. What is the market cap of this company?"></div>
    <div class="field"><label for="url">Start URL</label>
      <input id="url" placeholder="https://… the page to start on" onchange="urlChanged()"></div>
    <div class="actions">
      <button id="go" onclick="submitTask()">Run task</button>
      <button id="check" class="ghost" onclick="smoke()"
        title="Launches Chromium against example.com — proves the browser works, spends no tokens">Browser check</button>
    </div>
  </div>
  <p class="note" id="guards">Public http/https pages only · up to 30 actions and 2 replans per run ·
    one run at a time · a run costs about $0.001 in model tokens.</p>
  <pre id="err" hidden></pre>
</div>

<div id="live" hidden>
  <h2><span class="section-no">02</span> Trace <span class="note" id="runid"></span></h2>
  <div class="status-line" id="statusline"><span class="big running" id="status">running</span>
    <span class="note" id="budgets"></span></div>
  <ol class="progress" id="progress" aria-label="Run progress" aria-live="polite">
    <li data-phase="planning" data-state="upcoming">Planning</li>
    <li data-phase="browser" data-state="upcoming">Open page</li>
    <li data-phase="action" data-state="upcoming">Run actions</li>
    <li data-phase="verification" data-state="upcoming">Verify answer</li>
    <li data-phase="complete" data-state="upcoming">Complete</li>
  </ol>
  <div class="live-grid">
    <div class="live-main">
      <div id="steps"></div>
      <div id="result"></div>
    </div>
    <aside class="panel pageview" id="pageview" aria-label="Page view">
      <div class="pv-hd"><b>Page view</b>
        <a class="note" id="pvlink" href="#" target="_blank" rel="noopener noreferrer" hidden>open the real page &#8599;</a></div>
      <div class="pv-tabs" role="tablist" aria-label="Page view mode">
        <button class="pv-tab" id="tab-live" role="tab" aria-selected="true" onclick="pvTab('live')">Live page</button>
        <button class="pv-tab" id="tab-shot" role="tab" aria-selected="false" onclick="pvTab('shot')">Screenshot</button>
        <button class="pv-tab" id="tab-read" role="tab" aria-selected="false" onclick="pvTab('read')">What was read</button>
      </div>
      <p class="note" id="pvcap">Enter a URL, or pick an example below.</p>
      <div id="pvlive" class="pv-pane">
        <iframe id="pvframe" title="The page, fetched and rendered read-only"
                sandbox referrerpolicy="no-referrer" loading="lazy"></iframe>
        <p class="note" id="pvlivenote"></p>
      </div>
      <div id="pvshot" class="pv-shot pv-pane" hidden></div>
      <div id="pvtext" class="pv-text pv-pane" hidden></div>
    </aside>
  </div>
</div>

<h2><span class="section-no">03</span> What works today</h2>
<p class="note">Each status is declared by a human from eval evidence, never inferred from a
  pass rate. &ldquo;Try&rdquo; buttons are examples that were run against this deployment.</p>
<div id="matrix" class="cards">loading&hellip;</div>

<h2><span class="section-no">04</span> Known limits</h2>
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
// One per real-site support-matrix row — the cards are the only example
// surface. Every entry was run against the deployment: the M35 entries on
// 2026-08-22, the four M40 ones (quotes, companiesmarketcap, x-rates, multpl)
// on 2026-08-23. A run_id here is a receipt against docs/support-matrix.md and
// the eval record, NOT against a live GET /tasks/<run_id> — RUNS is in-memory
// and a redeploy destroys the history (support matrix D19). A site declared supported/—
// cites a run that answered correctly; a site declared unreliable/unsupported
// may cite a run that demonstrates the declared status (fails loudly, never a
// wrong answer) and says so in `note`. An example nobody can reproduce is
// removed, not kept.
const EXAMPLES = {
  "books.toscrape.com (live)": {label: "Price of a book",
    url: "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    task: "What is the price of this book?"},                  // run ac69e850 → "£51.77"
  "news.ycombinator.com (live)": {label: "Title of an HN story",
    url: "https://news.ycombinator.com/item?id=1",
    // runs 97f2157d, 4453fae6 → "Y Combinator" (M37). Retired "Who submitted
    // this story?" (run bcdc8f8a → "pg"): post-M35 it failed 5/5 on the
    // deployment — 349e4839, e08b7627, bcae4fe7, 63b9d944, failure:locate,
    // the planner targets link "pg" and the page has two.
    task: "What is the title of this story?"},
  "quotes.toscrape.com (live)": {label: "First of the top ten tags",
    url: "https://quotes.toscrape.com/",
    // Third task on this card in one milestone, and the first that survives a
    // pre-merge re-run: 3/3 (51bc4a0a, eb5ed750, b131ac78 → "love"). The two it
    // replaces are both the resolver-ambiguity shape main's M38 exists to fix —
    // "Who wrote the quote about the world we have created?" is 1/6 on this build
    // ("3 matches at tier text" for "Albert Einstein", three of his quotes on the
    // page: f7dd7f52, 7d05d5e2), and the /author/ page answers with the site
    // title and is rejected by the judge (6811f8bf, 79572b33, a8fe1b01). This
    // task asks for a value that is unique on the page, which is the property
    // this agent needs and the page cannot always offer.
    task: "Which tag is listed first under Top Ten tags?",
    note: "3/3 on this task. The author-name tasks are 1/6 — the same value appears three times and the resolver will not guess; the declared failure is the JS-rendered /js/ pages."},
  "openlibrary.org (live)": {label: "See a failure: author of a book",
    url: "https://openlibrary.org/books/OL7025919M",
    task: "Who is the author of this book?",   // run f1ecf157 → failure:extract (015b6778, 65af344f too: loud, never wrong)
    note: "Declared unreliable — this example fails loudly, so you can see what a failure looks like."},
  "companiesmarketcap.com (live)": {label: "Market cap of a company",
    url: "https://companiesmarketcap.com/apple/marketcap/",
    // The only row here with a real repeat count behind it: 7/7 on the pre-M32
    // build and 8/8 on the current one (d0b63c7e, f2c8c624, 65bb1028, 03eedb79,
    // 2a058974, 4cec8304, 215e511a, f8925a42) across six pages. It survives a
    // build change because the answer IS a heading's accessible name, so no plan
    // ever needs a container — D28 has the shape.
    task: "What is the market cap of this company?"},
  "bankofcanada.ca (live)": {label: "A central bank's policy rate",
    url: "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/",
    task: "What is the current policy interest rate?",   // 3/3: e36edcc1, 93fc8e6f, 5125b503 → "2.25"
    },
  "ecb.europa.eu (live)": {label: "An ECB key rate",
    url: "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html",
    task: "What is the deposit facility rate?",   // 2/3: c8f04424, 9597fab9 → "2.25"
    note: "2/3 — the third run read the historical table instead of the current rate, and the judge rejected it."},
  "wikipedia.org": {label: "A university's motto",
    url: "https://en.wikipedia.org/wiki/Harvard_University",
    // 3/4 on the current build (4bdbd12f, f31a05c8, a51a772f → "Veritas
    // (Latin)[3]"; 7547e580 failed at locate). The pre-merge re-run is what
    // found the failure — the earlier note said "one verified run", which was
    // true and told a reader nothing about how often it holds.
    task: "What is the motto of this university?",
    note: "3/4 on this build; still no eval case, so nothing re-checks it."},
};
// Short limits for visitors; the declared rows with evidence stay in
// docs/support-matrix.md, linked below with their count from the payload.
const LIMITS = [
  "Needs a start URL or a site named in the task — no web search",
  "One visible value per page; second-page tasks (open category → read price) unreliable",
  "Large tables / infoboxes / stock-quote grids: often fails — reads the whole block, not the one cell",
  "Numbers painted by script after the page loads are invisible to the planner",
  "Can pass verification with a wrong answer — known defect, fix in progress",
  "Login, payment, CAPTCHA, delete, download: refused",
];
const EXPLAIN = {
  success: "Answer found and verified against the page.",
  "failure:locate": "Couldn't find the element the plan was looking for on the page.",
  "failure:extract": "Reached the page but didn't get an answer out of it.",
  "failure:semantic": "Got an answer, but it failed verification — not a single value grounded on the page.",
  "failure:nav": "The start page didn't load.",
  "failure:task": "Rejected before running — blocked URL or an invalid plan.",
  "failure:env": "A service problem (model or API), not the website.",
  failure: "The run failed; the trace shows where.",
  unsupported: "Refused on purpose: login, payment, CAPTCHA, deletion and download tasks are out of scope.",
};

// ponytail: the no-URL path is not a product. The planner plans blind without a
// page observation and the run dies at extract (run 2ce3e5c8), so the form does
// not spend a run on it: lift a site name out of the task if there is one, else
// ask. The API keeps accepting url=null because gateway eval cases pin it.
function siteInTask(task) {
  const m = task.match(/https?:\/\/\S+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/\S*)?/i);
  if (!m) return null;
  const u = m[0].replace(/[.,;:)]+$/, "");
  return /^https?:/i.test(u) ? u : "https://" + u;
}
function useExample(key) {
  const e = EXAMPLES[key];
  $("task").value = e.task;
  $("url").value = new URL(e.url, location.origin).href;
  urlChanged();
  if (!$("go").disabled) submitTask();
}

// Typing or pasting a URL is enough to see the page. The panel exists to let a
// reviewer read what the task is about; making that wait for a run would hide
// it behind the thing it is supposed to explain.
function urlChanged() {
  const url = $("url").value.trim();
  $("live").hidden = false;
  if (!runId) {                 // the panel is open to show a page, not a run
    $("statusline").hidden = true;
    $("progress").hidden = true;
    $("steps").innerHTML = ""; $("result").innerHTML = "";
  }
  pvTab("live");
  showLive(url);
  if (url) { $("pvlink").href = url; $("pvlink").hidden = false; }
  $("pvcap").textContent = url ? "the page, before anything runs" : "Enter a URL, or pick an example below.";
}
document.addEventListener("click", (ev) => {
  const hit = ev.target.closest("[data-example]");
  if (hit) useExample(hit.dataset.example);
  const step = ev.target.closest("[data-step]");
  if (step) { pinned = Number(step.dataset.step); showPage(pinned); }
});

// Both buttons open a stream and both write #status, #steps and the page view.
// Before this there was no shared owner: starting a browser check under a live
// run overwrote the trace with smoke output and painted `chromium ok` in the
// success colour over a run that was still executing (or had failed).
let smokeStream = null;

function busy(on) {
  $("go").disabled = on;
  $("check").disabled = on;
  if (!on) return;
  if (es) { es.close(); es = null; }
  if (smokeStream) { smokeStream.close(); smokeStream = null; }
}

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

// A silently truncated value is the one thing this panel must never do: the
// container dumps the verifier rejects are thousands of characters, and cutting
// one to 300 with no marker renders a page dump as a tidy, well-scoped
// extraction — hiding the defect the run was rejected for.
function clip(t, n) {
  return t.length > n ? esc(t.slice(0, n)) + `… <span class="note">(${t.length} chars)</span>` : esc(t);
}

// postcondition_ok is three-valued and null is NOT true: it means nothing was
// asserted about this step. Collapsing null into "ok" here would show a green
// tick on exactly the unverified action the contract calls a failure.
function postBadge(v) {
  if (v === true) return badge("postcondition ok", "ok");
  if (v === false) return badge("postcondition failed", "bad");
  return badge("unverified", "warn");
}

function stepEl(s, idx) {
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
  return `<div class="step ${cls}" data-step="${idx}">
    <div class="hd"><span class="i">#${s.i}</span><span class="act">${esc(s.action)}</span>
      <code>${esc(t.length > 90 ? t.slice(0, 90) + "…" : t)}</code>
      ${b}<span class="ms">${s.ms}ms</span></div>
    <details><summary>step detail${s.screenshot ? " + screenshot" : ""}</summary>
      <pre>${esc(JSON.stringify(s, null, 2))}</pre>${shot}</details>
  </div>`;
}

// The page view mirrors the trace: the latest step that produced a screenshot,
// unless a step was clicked. Screenshots are best-effort in the executor, so a
// step without one is a real state, not an error.
let LIVE = [], pinned = null;

// The panel has three views of one page and they answer different questions:
// the live frame is "what does this page say", the screenshot is "what did the
// browser see at this step", and the read pane is "what did we take off it".
// Only the first is useful before a run starts, so it is the default and it
// loads as soon as there is a URL.
let PV = "live";

function pvTab(which) {
  PV = which;
  for (const [name, pane] of [["live", "pvlive"], ["shot", "pvshot"], ["read", "pvtext"]]) {
    $(pane).hidden = name !== which;
    $("tab-" + (name === "live" ? "live" : name === "shot" ? "shot" : "read"))
      .setAttribute("aria-selected", String(name === which));
  }
}

// Framed through our own /view, because the sites worth demoing refuse to be
// framed directly (X-Frame-Options / frame-ancestors). Sandboxed with no
// allow-scripts: the frame renders and scrolls, and cannot run the page's
// script — which is also why a script-built page looks emptier here than the
// trace shows, and the note says so rather than leaving it to be discovered.
function showLive(url) {
  const frame = $("pvframe"), note = $("pvlivenote");
  if (!url) { frame.removeAttribute("src"); note.textContent = ""; return; }
  frame.src = "/view?url=" + encodeURIComponent(url);
  note.innerHTML = "Read-only copy, fetched server-side and rendered with scripting off — "
    + "so a page that builds itself with script shows less here than the trace read. "
    + "Scroll it like the real page.";
}

function showPage(idx) {
  const s = LIVE[idx];
  if (!s) return;
  $("pvcap").textContent = `step #${s.i} \u00b7 ${s.action}`
    + (pinned === idx ? " \u00b7 pinned" : "") + (s.screenshot ? "" : " \u00b7 no screenshot");
  if (s.action === "navigate" && s.value) showLive(s.value);
  $("pvshot").innerHTML = s.screenshot && runId
    ? `<img src="/runs/${runId}/${esc(s.screenshot)}" alt="The page as the browser saw it at step ${s.i}">`
    : "";
}

function renderSteps(steps) {
  LIVE = steps;
  $("steps").innerHTML = steps.map(stepEl).join("");
  let latest = -1;
  steps.forEach((s, i) => { if (s.screenshot) latest = i; });
  showPage(pinned !== null && pinned < steps.length ? pinned : latest);
}

// What was actually read off the page, with the text it was read from — the
// half of "is this answer right?" that a screenshot cannot settle.
function renderScraped(r) {
  const ex = (r.evidence && r.evidence.extractions) || [];
  $("pvtext").innerHTML = ex.length
    ? `<div class="note">Read from the page (${ex.length})</div>` + ex.map(e =>
        `<div class="scrape"><b>${clip(String(e.value), 300)}</b>
         <details><summary>surrounding page text</summary><pre>${esc(e.page_text || "")}</pre></details>
         </div>`).join("")
    : `<p class="note">Nothing was read off the page in this run.</p>`;
}

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
  renderScraped(r);
  const fin = r.evidence && r.evidence.final_url;
  if (fin) { $("pvlink").href = fin; $("pvlink").hidden = false; showLive(fin); }
  const v = r.verdict, none = r.answer === null || r.answer === undefined;
  const checks = v ? Object.entries(v.checks || {}).map(([k, ok]) =>
      badge((ok ? "✓ " : "✗ ") + k.replace(/_/g, " "), ok ? "ok" : "bad")).join("") : "";
  $("result").innerHTML = `<div class="panel" style="margin-top:1rem">
    <p class="summary"><span class="big ${esc(kind)}">${esc(r.status)}</span>
      <span>${esc(EXPLAIN[r.status] || EXPLAIN[kind] || "")}</span></p>
    <div><b>Answer</b>${kind === "success" || none ? "" : ' <span class="note">(rejected by the verifier)</span>'}</div>
    <div class="answer${none ? " none" : kind === "success" ? "" : " failed"}">${none ? "(no answer)"
        : esc(typeof r.answer === "string" ? r.answer : JSON.stringify(r.answer, null, 2))}</div>
    ${r.reason ? `<div><b>Why</b></div><pre>${esc(r.reason)}</pre>` : ""}
    <div style="margin-top:.8rem"><b>Verifier</b> ${v
        ? badge(v.verdict, v.verdict === "PASS" ? "ok" : "bad") +
          badge("layer " + v.layer) +
          badge(v.ground_truth ? "external ground truth" : "runtime predicates only",
                v.ground_truth ? "ok" : "warn")
        : badge("not reached", "warn")}</div>
    ${v ? `<div class="checks">${checks}</div>
      <details><summary>raw verdict</summary><pre>${esc(JSON.stringify(v, null, 2))}</pre></details>` : ""}
  </div>`;
}

async function submitTask() {
  const task = $("task").value.trim();
  if (!task) return;
  let url = $("url").value.trim();
  if (!url) { url = siteInTask(task); if (url) $("url").value = url; }
  if (!url) {
    $("err").hidden = false;
    $("err").textContent = "Add a start URL, or name the site in the task. This agent works " +
      "on a page you point it at — it has no web search, so a question with no page to " +
      "start on cannot be answered.";
    $("url").focus();
    return;
  }
  busy(true);
  $("statusline").hidden = false;
  $("err").hidden = true;
  $("live").hidden = false;
  $("progress").hidden = true;
  $("steps").innerHTML = ""; $("result").innerHTML = "";
  $("status").className = "big running"; $("status").textContent = "running";
  $("budgets").textContent = ""; $("runid").textContent = "";
  runId = null; LIVE = []; pinned = null;
  $("pvshot").innerHTML = ""; $("pvtext").innerHTML = "";
  $("pvcap").textContent = "waiting for the browser\u2026";
  $("pvlink").href = url; $("pvlink").hidden = false;
  showLive(url);
  try {
    const r = await fetch("/tasks", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task, url}),
    });
    const data = await r.json();
    if (!r.ok) {
      // A refusal is a terminal path too: without this the guard working once
      // disables the form for good, and the UI looks broken by its own success.
      busy(false);
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
    const mine = runId;  // this run's id, captured before any await
    es = new EventSource("/tasks/" + runId + "/stream");
    const live = [];
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.event === "step") { live.push(ev.step); setPhase(phaseFor(ev.step)); renderSteps(live); }
      else if (ev.event === "done") { setTerminal(ev.result.status); renderResult(ev.result); busy(false); }
    };
    // Stream dropped. The run record is the truth — but the poll for it can
    // fail too, and every way it failed used to end in the same place: the
    // button disabled for good and #status still reading `running`, now with a
    // spinner animating beside it. A page that asserts a run is in progress for
    // a run that is dead is the UI lying quietly, which is the one thing this
    // surface exists not to do. `mine` guards the other half: a late poll for
    // run A must not render against run B's id, or A's step captions get B's
    // screenshots with no error anywhere.
    es.onerror = () => {
      if (es) { es.close(); es = null; }
      fetch("/tasks/" + mine)
        .then(x => x.ok ? x.json() : Promise.reject(new Error("HTTP " + x.status)))
        .then(r => {
          if (runId !== mine) return;             // a newer run owns the surface
          if (r && typeof r.status === "string" && r.status === "running") detached(mine);
          else if (r && typeof r.status === "string") renderResult(r);
          else lost("stream lost, and the run record does not say what happened");
        })
        .catch(err => { if (runId === mine) lost("stream lost, and the run record is unreachable: " + err); })
        .finally(() => { if (runId === mine) busy(false); });
    };
  } catch (e) {
    $("err").hidden = false; $("err").textContent = String(e); busy(false);
  }
}

// Terminal, and honest about being terminal: no spinner, no claim of a verdict.
function lost(message) {
  setTerminal("failure:env");
  $("status").className = "big failure"; $("status").textContent = "stream lost";
  $("err").hidden = false; $("err").textContent = message;
}

// NOT terminal. The stream dropped — a proxy idle timeout, a sleeping laptop, a
// throttled background tab — and the run record says the run is still going. The
// first version of this path called `lost()` here, which painted a healthy run as
// `failure:env` with the progress rail marked failed: the same defect as the
// spinner over a dead run, pointed the other way, and worse because a run that
// then succeeds is never shown. So: no verdict, no `data-terminal`, no spinner,
// and the run id stays on screen because it is the only way back to the record.
function detached(id) {
  $("progress").removeAttribute("data-terminal");
  progressItems().forEach(item => item.removeAttribute("aria-current"));
  $("status").className = "big unsupported"; $("status").textContent = "detached";
  $("err").hidden = false;
  $("err").textContent = "The live stream dropped, but the run record says this run is still "
    + "executing. Nothing here is a verdict. Reload, or read the record directly at /tasks/" + id;
}

function smoke() {
  busy(true);
  runId = null;
  smokeStream = null;
  $("statusline").hidden = false;
  $("live").hidden = false;
  $("progress").hidden = true;
  $("steps").innerHTML = ""; $("result").innerHTML = "";
  LIVE = []; pinned = null;
  $("pvshot").innerHTML = ""; $("pvtext").innerHTML = "";
  $("pvcap").textContent = "the browser check takes no screenshots";
  $("pvlink").hidden = true;
  $("runid").textContent = "platform smoke — real Chromium, no LLM spend";
  $("status").className = "big running"; $("status").textContent = "running";
  const s = smokeStream = new EventSource("/smoke/stream");
  const lines = [];
  s.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    lines.push(e.data);
    $("steps").innerHTML = `<pre>${esc(lines.join("\n"))}</pre>`;
    if (ev.event === "done" || ev.event === "error") {
      s.close(); smokeStream = null;
      $("status").className = "big " + (ev.event === "done" ? "success" : "failure");
      $("status").textContent = ev.event === "done" ? "chromium ok" : "chromium failed";
      busy(false);
    }
  };
  // Same treatment as the task stream, because it is the same failure: without
  // it a check whose stream dies before `done` left #status reading `running`
  // with the spinner going, forever.
  s.onerror = () => {
    s.close(); smokeStream = null;
    lost("the browser check's stream dropped before it reported a result");
    busy(false);
  };
}

fetch("/support-matrix").then(r => r.json()).then(m => {
  // The task-class columns come from the payload, not a second hardcoded list:
  // parse_matrix refuses to return zero rows, so rows[0] is always there.
  const TCS = Object.keys(m.rows[0].cells);
  const MARK = {supported: "✓", unreliable: "△", unsupported: "×"};
  const SUFFIX = {unreliable: " — unreliable", unsupported: " — doesn't work"};
  // Real sites only: the fixture rows stay in the doc, not on the page.
  $("matrix").innerHTML = m.rows.filter(row => !/ fixture$/.test(row.domain)).map(row => {
    const caps = TCS.filter(t => MARK[row.cells[t]]).map(t => `<li class="${row.cells[t]}">${
      MARK[row.cells[t]]} ${esc(SUPPORT_LABELS[t] || t)}${SUFFIX[row.cells[t]] || ""}</li>`);
    const ex = EXAMPLES[row.domain];
    return `<div class="card"><div><b>${esc(row.domain.replace(/ \(live\)$/, ""))}</b></div>
      <ul class="caps">${caps.join("") || '<li class="none">Not evaluated yet</li>'}</ul>
      ${ex ? `<button class="ghost chip try" data-example="${esc(row.domain)}">Try: ${esc(ex.label)}</button>` : ""}
      ${ex && ex.note ? `<p class="note" style="margin:0">${esc(ex.note)}</p>` : ""}
    </div>`;
  }).join("");
  $("limits").innerHTML = `<ul class="limits-summary">${
    LIMITS.map(l => `<li>${esc(l)}</li>`).join("")}</ul>
    <p class="note" style="margin:.8rem 0 0">${m.limitations.length} declared limitations, each with
      its evidence and a case id: <a href="https://github.com/HaoweiChan/browser-agent/blob/main/docs/support-matrix.md">docs/support-matrix.md</a></p>`;
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
    if SEM.locked():
        # Concurrency is 1 by design (SEM, /readyz). Without this, two tabs --
        # or one tab before the M40 button-locking -- launched a second browser
        # outside the semaphore, so the property /readyz reports stopped holding
        # while /readyz still reported it from SEM alone.
        yield ev("error", error=f"a run is executing ({ACTIVE_RUN}); one browser at a time")
        return
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
