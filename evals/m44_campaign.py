#!/usr/bin/env python3
"""M44's frozen, sequential, three-mode live campaign.

This file is deliberately both registry and runner: splitting an experiment's
task list from the code that counts it creates two things that can drift.

Registry ruling, frozen before spend: ADR-025 contributes six D28 tasks; the
eight non-SEC ``EXAMPLES`` are the M40 card set because ADR-031 calls its two
finance rows "two of the eight M40 cards", although server.py's historical
comment says only four cards originated in M40. Three identities overlap
exactly (OpenLibrary, Companies Market Cap, Bank of Canada), so their union is
11. ADR-030 adds two SEC deep-link tasks and the interviewer flow adds one
root-page intc-2002 interaction: 14 identities, paired zh/en, three modes, three
reps = 252 runs. Only exact ``(task, url, language)`` identities deduplicate.

No command spends by default. ``--execute`` is required, every POST carries an
explicit mode, and a POST with an ambiguous outcome is journaled and never
retried. One frozen build event binds every run, and any invalid recovered
journal stops before build discovery or HTTP. Text paraphrases pause for a
human or one independently allowlisted, non-self model to adjudicate.
``--max-usd`` is a stop line over COMPLETED reported runs, not an
absolute cap: one delivered run may still be active, a loop can cross its cap
on the billed call that trips it, and judge attempts have no token/USD cap.
Those limitations are copied into every report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = "https://whaleforce-browser-agent.zeabur.app"
SEC_BASE = "https://whaleforce-sec10k.zeabur.app"
MODES = ("plan", "loop", "escalate")
REPS = 3
DEFAULT_MAX_RUNS = 252
DEFAULT_MAX_USD = 160.0
DEFAULT_MAX_WALL_SECONDS = 108_000
DEFAULT_RUN_TIMEOUT = 420
MUTABLE_TRUTH_MAX_AGE_SECONDS = 900
ADJUDICATOR_MODELS = ("deepseek/deepseek-v4-flash-0731",)


def _rule(kind: str, *fields: str) -> dict:
    return {"kind": kind, "fields": fields}


# Lists keep source membership inspectable; one run can satisfy several groups.
PROBES = (
    {"id": "x-rates-eur-usd", "url": "https://www.x-rates.com/calculator/?from=EUR&to=USD&amount=1",
     "en": "What is the current exchange rate from EUR to USD?",
     "zh": "目前歐元兌美元的匯率是多少？", "sources": ("D28",),
     "mutable": True, "match": (_rule("number", "rate", "exchange", "匯率"),)},
    {"id": "multpl-sp500-pe", "url": "https://www.multpl.com/s-p-500-pe-ratio",
     "en": "What is the current S&P 500 P/E ratio?",
     "zh": "目前標普 500 指數的本益比是多少？", "sources": ("D28",),
     "mutable": True, "match": (_rule("number", "p/e", "ratio", "本益比"),)},
    {"id": "quotes-author-born", "url": "https://quotes.toscrape.com/author/Albert-Einstein/",
     "en": "When was this author born?", "zh": "這位作者是何時出生的？",
     "sources": ("D28",), "mutable": False,
     "match": (_rule("text"),)},
    {"id": "openlibrary-author", "url": "https://openlibrary.org/books/OL7025919M",
     "en": "Who is the author of this book?", "zh": "這本書的作者是誰？",
     "sources": ("D28", "M40-card"), "mutable": False,
     "match": (_rule("text"),)},
    {"id": "companies-market-cap", "url": "https://companiesmarketcap.com/apple/marketcap/",
     "en": "What is the market cap of this company?", "zh": "這家公司的市值是多少？",
     "sources": ("D28", "M40-card", "ADR-031"), "mutable": True,
     "match": (_rule("number", "market cap", "市值"),)},
    {"id": "bank-of-canada-rate", "url": "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/",
     "en": "What is the current policy interest rate?", "zh": "目前的政策利率是多少？",
     "sources": ("D28", "M40-card", "ADR-031"), "mutable": True,
     "match": (_rule("number", "interest rate", "policy rate", "利率"),)},
    {"id": "books-price", "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
     "en": "What is the price of this book?", "zh": "這本書的價格是多少？",
     "sources": ("M40-card", "ADR-031"), "mutable": False,
     "match": (_rule("number", "price", "價格"),)},
    {"id": "hn-title", "url": "https://news.ycombinator.com/item?id=2",
     "en": "What is the title of this story?", "zh": "這篇文章的標題是什麼？",
     "sources": ("M40-card",), "mutable": False,
     "match": (_rule("text"),)},
    {"id": "quotes-top-tag", "url": "https://quotes.toscrape.com/",
     "en": "Which tag is listed first under Top Ten tags?",
     "zh": "「Top Ten tags」下列出的第一個標籤是什麼？", "sources": ("M40-card",),
     "mutable": False, "match": (_rule("text"),)},
    {"id": "ecb-deposit-rate", "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html",
     "en": "What is the deposit facility rate?", "zh": "歐洲央行的存款機制利率是多少？",
     "sources": ("M40-card",), "mutable": True,
     "match": (_rule("number", "rate", "利率"),)},
    {"id": "wikipedia-motto", "url": "https://en.wikipedia.org/wiki/Harvard_University",
     "en": "What is the motto of this university?", "zh": "這所大學的校訓是什麼？",
     "sources": ("M40-card",), "mutable": False,
     "match": (_rule("text"),)},
    {"id": "sec-aapl-status", "url": SEC_BASE + "/?fixture=aapl-2025&run=1",
     "en": "What is the doc_status of the aapl-2025 fixture?",
     "zh": "aapl-2025 fixture 的 doc_status 是什麼？", "sources": ("ADR-030",),
     "mutable": False, "match": (_rule("status", "doc_status", "status"),)},
    {"id": "sec-aapl-count", "url": SEC_BASE + "/?fixture=aapl-2025&run=1",
     "en": "How many items are extracted?", "zh": "擷取了多少個項目？",
     "sources": ("ADR-030",), "mutable": False,
     "match": (_rule("integer", "extracted", "items", "項目"),)},
    # The feedback did not preserve a verbatim task. This wording freezes the
    # actual current control (`intc-2002` in the committed-fixture select)
    # rather than pretending the page accepts a free-form ticker called INTC.
    {"id": "sec-intc-flow", "url": SEC_BASE + "/",
     "en": "In the SEC 10-K Extractor, select the intc-2002 committed fixture, run the extraction, wait for it to finish, and report the doc_status and number of extracted items.",
     "zh": "在 SEC 10-K Extractor 中選取 intc-2002 的 committed fixture，執行擷取，等待擷取完成，然後回報 doc_status 和擷取項目數。",
     "sources": ("interviewer-INTC",), "mutable": False,
     "match": (_rule("status", "doc_status", "status"),
               _rule("integer", "extracted", "items", "項目"))},
)

# Filled from canonical JSON below; the invariant makes any text/URL/source edit
# a deliberate experiment change rather than a silently different campaign.
FROZEN_REGISTRY_SHA256 = "e30343d19e552f5ec8e719915192d564aa8feaa05354428e722a98f95435e297"

LIMITATIONS = {
    "usd_stop_is_not_absolute": (
        "max_usd is checked only after completed run records; one delivered run may "
        "remain active and overshoot before its result can be read"),
    "loop_cap_is_post_call": (
        "the production loop USD budget is checked after the billed call that crosses it"),
    "judge_usd_is_unbounded": (
        "judge attempts are count-bounded but have no production token or USD cap"),
    "client_timeout_does_not_cancel": (
        "a client poll timeout stops new submissions but does not cancel a delivered run"),
    "client_wall_stop_can_overshoot": (
        "network, filesystem and scheduler delay make client overshoot unbounded; a delivered "
        "server run is not cancelled and may continue after the client stops"),
    "sec_sha_is_self_reported": (
        "the inspector git_sha comes from its own /api/meta response, not independent attestation"),
}


def registry_payload() -> list[dict]:
    return [{**p, "sources": list(p["sources"]),
             "match": [{**r, "fields": list(r["fields"])} for r in p["match"]]} for p in PROBES]


def registry_sha256() -> str:
    raw = json.dumps(registry_payload(), sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def campaign_rows() -> list[dict]:
    return [{"probe_id": p["id"], "url": p["url"], "language": lang,
             "task": p[lang], "mode": mode, "rep": rep}
            for p in PROBES for lang in ("en", "zh")
            for mode in MODES for rep in range(1, REPS + 1)]


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON constant: {value}")


def _strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _strict_loads(value):
    return json.loads(value, parse_constant=_reject_json_constant,
                      object_pairs_hook=_strict_object)


def _strict_load(stream):
    return json.load(stream, parse_constant=_reject_json_constant,
                     object_pairs_hook=_strict_object)


def _json(url: str, payload: dict | None = None, *, timeout: int = 30,
          opener=urllib.request.urlopen) -> dict:
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with opener(req, timeout=timeout) as response:
        return _strict_load(response)


def _append(path: Path, event: dict) -> None:
    line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _create_journal(path: Path, first_event: dict) -> None:
    if path.suffix != ".jsonl":
        raise ValueError("journal must use the .jsonl suffix")
    line = json.dumps(first_event, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _write_report(path: Path, journal: Path, report: dict) -> None:
    if path == journal or path.suffix != ".json" or path.exists():
        raise FileExistsError("report must be a new .json path distinct from the journal")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as f:
            tmp_name = f.name
            json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.link(tmp_name, path)  # atomic and refuses an existing destination
    finally:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)


def _builds(base: str, include_sec: bool) -> dict:
    browser = _json(base + "/version")
    builds = {"browser": browser.get("sha"), "browser_source": browser.get("source")}
    if include_sec:
        builds["sec"] = _json(SEC_BASE + "/api/meta").get("git_sha")
    if _build_errors(builds, include_sec):
        raise RuntimeError(f"build identity unavailable: {builds}")
    return builds


def _build_errors(builds, include_sec: bool) -> list[str]:
    expected = {"browser", "browser_source", *(('sec',) if include_sec else ())}
    if not isinstance(builds, dict) or set(builds) != expected:
        return ["build keys differ from the strict contract"]
    errors = []
    if builds.get("browser_source") != "image":
        errors.append("browser build source is not image")
    for key in ("browser", *(('sec',) if include_sec else ())):
        value = builds.get(key)
        if (not isinstance(value, str) or not value or value != value.strip() or
                any(char.isspace() for char in value)):
            errors.append(f"{key} build identity is not a canonical nonempty string")
    return errors


def _wait_ready(base: str, seconds: int = 30, *, read=_json, pause=time.sleep) -> None:
    deadline = time.monotonic() + seconds
    while True:
        ready = read(base + "/readyz")
        if ready.get("ready"):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"deployment stayed busy: {ready}")
        pause(.5)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _positive_finite(value) -> bool:
    try:
        return (isinstance(value, (int, float)) and not isinstance(value, bool) and
                math.isfinite(value) and value > 0)
    except (OverflowError, TypeError, ValueError):
        return False


def _nonnegative_finite(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool) and
            math.isfinite(value) and value >= 0)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not _positive_finite(parsed):
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if not _positive_finite(parsed):
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def _truth_snapshot(path: Path, mutable_probe: dict | None = None,
                    *, now: datetime | None = None) -> dict:
    raw = path.read_bytes()
    data = _strict_loads(raw)
    if data.get("registry_sha256") != registry_sha256():
        raise ValueError("ground truth was captured for a different registry")
    captured_at = data.get("captured_at")
    _parse_time(captured_at)
    tasks = data.get("tasks") or {}
    missing = sorted({p["id"] for p in PROBES} - tasks.keys())
    bad = sorted(k for k, v in tasks.items()
                 if not isinstance(v, dict) or not v.get("verified_at") or
                 not v.get("source") or not isinstance(v.get("values"), list))
    if missing or bad:
        raise ValueError(f"ground truth incomplete: missing={missing}, invalid={bad}")
    probes = {p["id"]: p for p in PROBES}
    for probe_id, truth in tasks.items():
        probe = probes.get(probe_id)
        if not probe or len(truth["values"]) != len(probe["match"]) or any(
                not isinstance(v, (str, int, float)) or str(v).strip() == ""
                for v in truth["values"]):
            raise ValueError(f"ground truth values do not match rule for {probe_id}")
        if any(rule["kind"] == "text" for rule in probe["match"]):
            exact = truth.get("accepted_exact")
            if (not isinstance(exact, list) or not exact or
                    any(not isinstance(value, str) or not _normalize_text(value) for value in exact) or
                    len({_normalize_text(value) for value in exact}) != len(exact)):
                raise ValueError(f"text ground truth needs unique accepted_exact for {probe_id}")
        _parse_time(truth["verified_at"])
    if mutable_probe and mutable_probe["mutable"]:
        verified = _parse_time(tasks[mutable_probe["id"]]["verified_at"])
        age = ((now or datetime.now(timezone.utc)) - verified).total_seconds()
        if age < -300 or age > MUTABLE_TRUTH_MAX_AGE_SECONDS:
            raise ValueError(f"mutable truth expired for {mutable_probe['id']}: age={age:.0f}s")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "captured_at": captured_at,
            "tasks": tasks}


def _truth_for_post(path: Path, probe: dict, initial: dict) -> dict:
    return _truth_snapshot(path, probe) if probe["mutable"] else initial


def _answer_text(answer) -> str:
    return " ".join(json.dumps(answer, ensure_ascii=False, allow_nan=False).casefold().split())


_NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])")
_NEGATION = re.compile(
    r"(?:(?:\bnot\b|\bno\b|\bwithout\b)(?:\s+\w+){0,2}|n't|不是|並非|并非|沒有|没有)\s*$")
_NEGATION_AFTER = re.compile(
    r"^\s*(?:(?:was|is|were|has|had)\s+)?(?:not|never)\b|^\s*(?:不是|並非|并非|沒有|没有)")
_STATUS = re.compile(r"(?<!\w)(success_with_warning|success|failed|failure|unsupported|running)(?!\w)")


def _negated(answer: str, start: int, end: int) -> bool:
    return bool(_NEGATION.search(answer[max(0, start - 24):start]) or
                _NEGATION_AFTER.search(answer[end:end + 24]))


def _field_spans(rule: dict, answer: str) -> list[tuple[int, int]]:
    spans = []
    for field in rule["fields"]:
        field = field.casefold()
        pattern = re.escape(field)
        if field.isascii():
            pattern = r"(?<!\w)" + pattern + r"(?!\w)"
        spans.extend(match.span() for match in re.finditer(pattern, answer))
    return spans


def _asserted(matches: list[tuple[int, int, object]], fields: list[tuple[int, int]]) -> set:
    if not fields:
        return {value for start, end, value in matches}
    asserted = set()
    for field_start, field_end in fields:
        distances = [(min(abs(end - field_start), abs(start - field_end)), value)
                     for start, end, value in matches]
        if distances:
            nearest = min(distance for distance, _ in distances)
            asserted.update(value for distance, value in distances if distance == nearest)
    return asserted


def _matches(rule: dict, expected, answer: str) -> bool:
    kind = rule["kind"]
    expected = str(expected).casefold().strip()
    answer = answer.casefold()
    if kind in {"number", "integer"}:
        try:
            target = Decimal(expected.replace(",", ""))
        except InvalidOperation:
            return False
        numbers = []
        for match in _NUMBER.finditer(answer):
            try:
                if not _negated(answer, match.start(), match.end()):
                    numbers.append((*match.span(), Decimal(match.group().replace(",", ""))))
            except InvalidOperation:
                pass
        if kind == "integer" and target != target.to_integral_value():
            return False
        return _asserted(numbers, _field_spans(rule, answer)) == {target}
    if kind == "status":
        statuses = [(*match.span(), match.group()) for match in _STATUS.finditer(answer)
                    if not _negated(answer, match.start(), match.end())]
        return _asserted(statuses, _field_spans(rule, answer)) == {expected}
    return False


def _normalize_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _normalize_model(value) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold() if isinstance(value, str) else ""


def classify(record: dict, truth: dict, match_rules: tuple | list) -> str:
    status = record.get("status")
    if status == "success":
        answer = _answer_text(record.get("answer"))
        typed = [(rule, value) for rule, value in zip(match_rules, truth["values"])
                 if rule["kind"] != "text"]
        if not all(_matches(rule, value, answer) for rule, value in typed):
            return "wrong_success"
        if any(rule["kind"] == "text" for rule in match_rules):
            exact = {_normalize_text(value) for value in truth.get("accepted_exact", [])}
            return ("correct" if _normalize_text(record.get("answer")) in exact
                    else "needs_adjudication")
        return "correct"
    if isinstance(status, str) and status.startswith("failure:"):
        return "loud_failure"
    if status == "unsupported":
        return "refusal"
    return "partial"


ACCOUNTING_KEYS = {"actions", "llm_tokens", "llm_usd", "replans", "ms",
                   "judge_calls", "judge_tokens", "judge_usd"}
ACCOUNTING_COUNTS = ACCOUNTING_KEYS - {"llm_usd", "judge_usd"}


def _leg_calls(leg: dict, trace: list | None = None) -> dict:
    mode, budgets = leg.get("mode"), leg.get("budgets_spent") or {}
    reason, status = leg.get("reason") or "", leg.get("status") or ""
    actions = int(budgets.get("actions", 0))
    first_failure = (trace or [{}])[0].get("failure_class")
    steps = len(trace) if trace is not None else int(leg.get("steps", actions))
    if (status == "failure:nav" and steps <= 1 and
            first_failure in {None, "nav", "task"}):
        return {"plan": 0, "loop": 0}
    if mode == "loop":
        return {"plan": 0, "loop": max(0, actions - 1) + int(reason.startswith("driver "))}
    calls = int(actions > 0) * (1 + int(budgets.get("replans", 0)) +
                                int(reason.startswith("replanner ")))
    return {"plan": calls, "loop": 0}


def accounting(row: dict) -> tuple[dict, list[str]]:
    rec = row.get("record") or {}
    records = [rec, *(rec.get("legs") or [])]
    errors = []
    for record in records:
        budgets = record.get("budgets_spent") or {}
        missing = ACCOUNTING_KEYS - set(budgets)
        if missing:
            errors.append(f"accounting keys missing: {sorted(missing)}")
        for key in ACCOUNTING_KEYS - missing:
            value = budgets[key]
            if (not isinstance(value, (int, float)) or isinstance(value, bool) or
                    not math.isfinite(value) or value < 0 or
                    (key in ACCOUNTING_COUNTS and not float(value).is_integer())):
                errors.append(f"accounting {key} is not a nonnegative finite count/value")
    empty = {"plan": 0, "loop": 0, "total": 0}
    if errors:
        return empty, errors
    if rec.get("mode") == "escalate":
        legs = rec.get("legs") or []
        parts = [_leg_calls(leg) for leg in legs]
        if not legs:
            errors.append("escalate accounting has no legs")
        for key in ACCOUNTING_KEYS:
            top = (rec.get("budgets_spent") or {}).get(key)
            values = [(leg.get("budgets_spent") or {}).get(key) for leg in legs]
            if top is not None and all(value is not None for value in values):
                if not math.isclose(float(top), sum(map(float, values)),
                                    rel_tol=1e-9, abs_tol=1e-12):
                    errors.append(f"escalate {key} differs from leg sum")
    else:
        parts = [_leg_calls(rec, (rec.get("evidence") or {}).get("trace"))]
    if errors:
        return empty, errors
    calls = {mode: sum(p[mode] for p in parts) for mode in ("plan", "loop")}
    calls["total"] = calls["plan"] + calls["loop"]
    return calls, errors


ALLOWED_EVENTS = {"campaign_start", "campaign_builds", "truth_snapshot", "accepted",
                  "terminal_observed", "terminal", "adjudicated", "submit_unknown",
                  "active_unknown", "abort", "campaign_end"}
ADJUDICATION_KEYS = {"registry_sha256", "truth_snapshot_sha256", "label",
                     "evidence", "source", "adjudicated_at"}


def _cell(row: dict) -> tuple:
    return tuple(row.get(k) for k in ("probe_id", "language", "mode", "rep"))


def _adjudication_errors(data: dict, terminal: dict,
                         *, allowed_models=ADJUDICATOR_MODELS,
                         now: datetime | None = None) -> list[str]:
    run_id = terminal.get("run_id")
    if not isinstance(data, dict) or set(data) != {run_id} or not isinstance(data.get(run_id), dict):
        return ["adjudication must be keyed by exactly the pending run_id"]
    decision = data[run_id]
    errors = []
    if set(decision) != ADJUDICATION_KEYS:
        errors.append("adjudication keys differ from the strict contract")
    if decision.get("registry_sha256") != terminal.get("registry_sha256"):
        errors.append("adjudication registry hash mismatch")
    if decision.get("truth_snapshot_sha256") != (terminal.get("truth_snapshot") or {}).get("sha256"):
        errors.append("adjudication truth snapshot hash mismatch")
    if decision.get("label") not in {"correct", "wrong_success"}:
        errors.append("adjudication label must be correct or wrong_success")
    if not isinstance(decision.get("evidence"), str) or not decision.get("evidence", "").strip():
        errors.append("adjudication evidence is empty")
    source = decision.get("source")
    model = _normalize_model((terminal.get("record") or {}).get("model"))
    allowed = {_normalize_model(value) for value in allowed_models}
    if (not isinstance(source, dict) or source.get("kind") not in {"human", "model"} or
            (source.get("kind") == "human" and
             (set(source) != {"kind", "identity"} or not str(source.get("identity", "")).strip())) or
            (source.get("kind") == "model" and
             (set(source) != {"kind", "model"} or not str(source.get("model", "")).strip() or
              _normalize_model(source.get("model")) not in allowed or not model or
              _normalize_model(source.get("model")) == model))):
        errors.append("adjudication source is invalid or self-adjudicating")
    try:
        decided = _parse_time(decision.get("adjudicated_at"))
        observed = _parse_time(terminal.get("terminal_at"))
        if decided < observed or decided > (now or datetime.now(timezone.utc)) + timedelta(minutes=5):
            errors.append("adjudication timestamp is stale or in the future")
    except (TypeError, ValueError):
        errors.append("adjudication timestamp is invalid")
    return errors


def _campaign_builds_for(spec: dict, builds: dict) -> dict:
    builds = builds if isinstance(builds, dict) else {}
    expected = {key: builds.get(key) for key in ("browser", "browser_source")}
    if str(spec.get("url", "")).startswith(SEC_BASE):
        expected["sec"] = builds.get("sec")
    return expected


def _matching_builds(base: str, spec: dict, campaign_builds: dict) -> dict:
    current = _builds(base, str(spec.get("url", "")).startswith(SEC_BASE))
    expected = _campaign_builds_for(spec, campaign_builds)
    if current != expected:
        raise RuntimeError(f"campaign build changed: {current} != {expected}")
    return current


def _adjudications(events: list[dict], terminals: dict[str, dict],
                    allowed_models) -> tuple[dict, list[dict]]:
    decisions, invalid, seen, errors = {}, set(), set(), []
    for i, event in enumerate(events):
        if event.get("event") != "adjudicated":
            continue
        run_id, decision = event.get("run_id"), event.get("decision")
        terminal = terminals.get(run_id) or {}
        why = _adjudication_errors({run_id: decision}, terminal,
                                   allowed_models=allowed_models)
        if run_id in seen:
            why.append("duplicate or conflicting adjudication")
        if terminal.get("classification") != "needs_adjudication":
            why.append("adjudication has no matching pending text terminal")
        seen.add(run_id)
        if why:
            invalid.add(run_id)
            decisions.pop(run_id, None)
            errors.append({"event_index": i, "run_id": run_id,
                           "error": f"invalid adjudication: {why}"})
        elif run_id not in invalid:
            decisions[run_id] = decision
    return decisions, errors


def _journal_errors(events: list[dict]) -> list[dict]:
    errors, accepted, observed, terminals, cells = [], {}, set(), {}, set()
    observations = {}
    expected = {_cell(spec): spec for spec in campaign_rows()}
    if events and events[0].get("event") != "campaign_start":
        errors.append({"error": "campaign_start is not the first event"})
    start = events[0] if events else {}
    try:
        started_at_valid = bool(_parse_time(start.get("started_at")))
    except (TypeError, ValueError):
        started_at_valid = False
    if (start.get("registry_sha256") != FROZEN_REGISTRY_SHA256 or
            start.get("max_runs") != DEFAULT_MAX_RUNS or not started_at_valid or
            not all(_positive_finite(start.get(key)) for key in (
                "max_usd_completed_stop", "max_wall_seconds_client", "run_timeout_client")) or
            start.get("limitations") != LIMITATIONS or
            start.get("adjudicator_models") != list(ADJUDICATOR_MODELS)):
        errors.append({"error": "campaign_start metadata does not match frozen campaign"})
    initial = events[1] if len(events) > 1 else {}
    if (initial.get("event") != "truth_snapshot" or
            initial.get("scope") != "campaign_start" or
            initial.get("truth_snapshot") != start.get("truth_snapshot") or
            not (initial.get("truth_snapshot") or {}).get("sha256") or
            not (initial.get("truth_snapshot") or {}).get("captured_at") or
            set(initial.get("tasks") or {}) != {p["id"] for p in PROBES}):
        errors.append({"error": "campaign_start truth snapshot chain is missing or inconsistent"})
    build_events = [(i, e) for i, e in enumerate(events)
                    if e.get("event") == "campaign_builds"]
    campaign_builds = build_events[0][1].get("builds") if len(build_events) == 1 else {}
    if (len(build_events) != 1 or build_events[0][0] != 2 or
            set(build_events[0][1]) != {"event", "builds", "campaign_elapsed_seconds"} or
            _build_errors(campaign_builds, True) or
            not _nonnegative_finite(
                build_events[0][1].get("campaign_elapsed_seconds"))):
        errors.append({"error": "exactly one strict campaign_builds must precede all runs"})
    for i, event in enumerate(events):
        kind, run_id = event.get("event"), event.get("run_id")
        if ("campaign_elapsed_seconds" in event and
                not _nonnegative_finite(event["campaign_elapsed_seconds"])):
            errors.append({"event_index": i,
                           "error": "campaign elapsed time must be finite and nonnegative"})
        if kind not in ALLOWED_EVENTS:
            errors.append({"event_index": i, "error": f"unknown journal event {kind!r}"})
        if kind == "truth_snapshot":
            scope = event.get("scope")
            next_event = events[i + 1] if i + 1 < len(events) else {}
            if scope == "campaign_start":
                valid = i == 1
            elif scope == "run":
                valid = (next_event.get("event") in {"accepted", "submit_unknown"} and
                         next_event.get("spec") == event.get("spec") and
                         (event.get("truth_snapshot") or {}).get("sha256") and
                         isinstance(event.get("ground_truth"), dict))
            else:
                valid = False
            if not valid:
                errors.append({"event_index": i, "error": "invalid truth snapshot chain"})
        if kind == "accepted":
            spec, cell = event.get("spec") or {}, _cell(event.get("spec") or {})
            prior = events[i - 1] if i else {}
            expected_payload = {key: spec.get(key) for key in ("task", "url", "mode")}
            probe_id = spec.get("probe_id")
            if (not run_id or run_id in accepted or cell in cells or
                    cell not in expected or spec != expected.get(cell) or
                    event.get("payload") != expected_payload or
                    prior.get("event") != "truth_snapshot" or
                    prior.get("scope") != "run" or prior.get("spec") != spec or
                    prior.get("truth_snapshot") != event.get("truth_snapshot") or
                    prior.get("ground_truth") != event.get("ground_truth") or
                    not (event.get("truth_snapshot") or {}).get("sha256") or
                    not isinstance(event.get("ground_truth"), dict) or
                    event.get("builds_before") != _campaign_builds_for(spec, campaign_builds)):
                errors.append({"event_index": i, "error": "duplicate/invalid accepted event"})
            probe = next((p for p in PROBES if p["id"] == probe_id), None)
            if probe and not probe["mutable"] and (
                    event.get("truth_snapshot") != initial.get("truth_snapshot") or
                    event.get("ground_truth") != (initial.get("tasks") or {}).get(probe_id)):
                errors.append({"event_index": i,
                               "error": "immutable truth differs from campaign snapshot"})
            accepted[run_id], cells = event, cells | {cell}
        elif kind == "submit_unknown":
            prior = events[i - 1] if i else {}
            spec = event.get("spec") or {}
            if (prior.get("event") != "truth_snapshot" or prior.get("scope") != "run" or
                    prior.get("spec") != spec or event.get("payload") != {
                        key: spec.get(key) for key in ("task", "url", "mode")}):
                errors.append({"event_index": i, "error": "invalid unknown submission chain"})
        elif kind == "terminal_observed":
            prior = accepted.get(run_id) or {}
            if (run_id not in accepted or run_id in observed or not isinstance(event.get("record"), dict)
                    or event.get("spec") != prior.get("spec")
                    or event.get("builds_before") != prior.get("builds_before")
                    or event.get("builds_before") != _campaign_builds_for(
                        event.get("spec") or {}, campaign_builds)
                    or event.get("truth_snapshot") != prior.get("truth_snapshot")
                    or event.get("ground_truth") != prior.get("ground_truth")):
                errors.append({"event_index": i, "error": "orphan/duplicate terminal_observed"})
            observed.add(run_id)
            observations[run_id] = event
        elif kind == "terminal":
            prior = observations.get(run_id) or {}
            record = event.get("record") or {}
            if (run_id not in observed or run_id in terminals or not record.get("model") or
                    record.get("mode") != (prior.get("spec") or {}).get("mode") or
                    _cell(event) != _cell(prior.get("spec") or {}) or
                    event.get("record") != prior.get("record") or
                    event.get("builds_before") != prior.get("builds_before") or
                    event.get("builds_after") != prior.get("builds_before") or
                    event.get("truth_snapshot") != prior.get("truth_snapshot") or
                    event.get("ground_truth") != prior.get("ground_truth") or
                    not event.get("terminal_at")):
                errors.append({"event_index": i, "error": "terminal lacks one prior observation"})
            probe = next((p for p in PROBES if p["id"] == event.get("probe_id")), None)
            try:
                reproducible = bool(probe and classify(
                    record, event.get("ground_truth") or {}, probe["match"]) ==
                    event.get("classification"))
            except (KeyError, TypeError, ValueError):
                reproducible = False
            _, accounting_errors = accounting({"record": record})
            if not reproducible:
                errors.append({"event_index": i,
                               "error": "terminal classification is not reproducible"})
            errors.extend({"event_index": i, "error": error} for error in accounting_errors)
            terminals[run_id] = event
    _, adjudication_errors = _adjudications(events, terminals,
                                             start.get("adjudicator_models") or ())
    errors.extend(adjudication_errors)
    if sum(e.get("event") == "campaign_start" for e in events) != 1:
        errors.append({"error": "journal must contain exactly one campaign_start"})
    return errors


def _unresolved(events: list[dict]) -> list[dict]:
    terminal = {e.get("run_id") for e in events if e.get("event") == "terminal"}
    return [e for e in events if e.get("event") == "accepted" and e.get("run_id") not in terminal]


def _remaining_specs(events: list[dict]) -> list[dict]:
    if _journal_errors(events) or _unresolved(events) or _pending_adjudications(events) or any(
            e.get("event") == "submit_unknown" for e in events):
        return []
    complete = {_cell(e) for e in events if e.get("event") == "terminal"}
    return [spec for spec in campaign_rows() if _cell(spec) not in complete]


def _pending_adjudications(events: list[dict]) -> list[dict]:
    terminals = {e.get("run_id"): e for e in events if e.get("event") == "terminal"}
    start = events[0] if events else {}
    decided = set(_adjudications(events, terminals,
                                 start.get("adjudicator_models") or ())[0])
    return [e for e in events if e.get("event") == "terminal" and
            e.get("classification") == "needs_adjudication" and e.get("run_id") not in decided]


def summarize(events: list[dict], *, validate_matrix: bool = True) -> dict:
    rows = [e for e in events if e.get("event") == "terminal"]
    terminal_map = {e.get("run_id"): e for e in rows}
    start = events[0] if events else {}
    decisions = _adjudications(events, terminal_map,
                                start.get("adjudicator_models") or ())[0]
    pending_adjudications = _pending_adjudications(events)
    starts = [e for e in events if e.get("event") == "campaign_start"]
    unresolved = _unresolved(events)
    terminal_ids = {e.get("run_id") for e in rows}
    partial = [e for e in events if e.get("event") in {"submit_unknown"} or
               (e.get("event") == "active_unknown" and e.get("run_id") not in terminal_ids)]
    partial.extend({"event": "orphaned_accepted", "run_id": e.get("run_id"),
                    "spec": e.get("spec")} for e in unresolved)
    partial.extend({"event": "needs_adjudication", "run_id": e.get("run_id"),
                    "spec": {key: e.get(key) for key in ("probe_id", "language", "mode", "rep")}}
                   for e in pending_adjudications)
    totals = {"usd": 0.0, "tokens": 0, "wall_ms": 0, "client_seconds": 0.0,
              "plan_calls": 0, "loop_calls": 0, "planner_calls": 0}
    by_mode = {mode: {k: 0 for k in
                      ("runs", "correct", "wrong_success", "loud_failure", "refusal",
                       "needs_adjudication", "tokens", "wall_ms", "plan_calls", "loop_calls",
                       "planner_calls")}
               for mode in MODES}
    for metrics in by_mode.values():
        metrics.update({"usd": 0.0, "client_seconds": 0.0})
    errors = _journal_errors(events)
    if validate_matrix and len(starts) != 1:
        errors.append({"error": f"expected one campaign_start, found {len(starts)}"})
    if starts and (starts[0].get("registry_sha256") != registry_sha256() or
                   starts[0].get("max_runs") != DEFAULT_MAX_RUNS):
        errors.append({"error": "campaign_start does not match frozen matrix"})
    run_ids, cells, triggers = set(), set(), {}
    probes = {p["id"]: p for p in PROBES}
    for row in rows:
        rec, mode, run_id = row.get("record") or {}, row.get("mode"), row.get("run_id")
        budgets = rec.get("budgets_spent") or {}
        if rec.get("mode") != mode or not rec.get("model") or not run_id:
            errors.append({"run_id": run_id, "error": "run is not self-attributing"})
        if run_id in run_ids:
            errors.append({"run_id": run_id, "error": "duplicate run id"})
        if run_id:
            run_ids.add(run_id)
        cell = _cell(row)
        if cell in cells:
            errors.append({"run_id": run_id, "error": f"duplicate campaign cell {cell}"})
        cells.add(cell)
        probe, lang = probes.get(row.get("probe_id")), row.get("language")
        if (not probe or lang not in {"en", "zh"} or row.get("task") != probe.get(lang) or
                row.get("url") != probe.get("url") or row.get("registry_sha256") != registry_sha256()):
            errors.append({"run_id": run_id, "error": "run does not match frozen registry"})
        before, after = row.get("builds_before") or {}, row.get("builds_after") or {}
        if before.get("browser_source") != "image" or after.get("browser_source") != "image":
            errors.append({"run_id": run_id, "error": "browser build source is not image"})
        if not before.get("browser") or not after.get("browser"):
            errors.append({"run_id": run_id, "error": "browser build SHA missing"})
        if str(row.get("url", "")).startswith(SEC_BASE) and (
                not before.get("sec") or not after.get("sec")):
            errors.append({"run_id": run_id, "error": "SEC build SHA missing"})
        if before != after:
            errors.append({"run_id": run_id, "error": "build changed during run"})
        if not isinstance(row.get("campaign_elapsed_seconds"), (int, float)):
            errors.append({"run_id": run_id, "error": "actual campaign elapsed time missing"})
        snapshot, truth = row.get("truth_snapshot") or {}, row.get("ground_truth")
        if not snapshot.get("sha256") or not snapshot.get("captured_at"):
            errors.append({"run_id": run_id, "error": "truth snapshot binding missing"})
        original_cls = row.get("classification")
        if original_cls not in by_mode.get(mode, {}):
            errors.append({"run_id": run_id, "error": f"bad class {original_cls!r}"})
            continue
        try:
            reproducible = bool(truth and probe and
                                classify(rec, truth, probe["match"]) == original_cls)
        except (KeyError, TypeError, ValueError):
            reproducible = False
        if not reproducible:
            errors.append({"run_id": run_id, "error": "classification is not reproducible"})
        decision = decisions.get(run_id)
        cls = decision["label"] if decision else original_cls
        if decision:
            row["adjudication"] = decision
        calls, accounting_errors = accounting(row)
        errors.extend({"run_id": run_id, "error": error} for error in accounting_errors)
        row["planner_calls"] = calls
        if accounting_errors:
            usd = tokens = wall_ms = 0
        else:
            usd = float(budgets["llm_usd"]) + float(budgets["judge_usd"])
            tokens = int(budgets["llm_tokens"]) + int(budgets["judge_tokens"])
            wall_ms = int(budgets["ms"])
        client_seconds = float(row.get("client_seconds", 0))
        by_mode[mode]["runs"] += 1
        by_mode[mode][cls] += 1
        for key, value in (("usd", usd), ("tokens", tokens), ("wall_ms", wall_ms),
                           ("client_seconds", client_seconds), ("plan_calls", calls["plan"]),
                           ("loop_calls", calls["loop"]), ("planner_calls", calls["total"])):
            totals[key] += value
            by_mode[mode][key] += value
        if mode == "escalate":
            legs = rec.get("legs") or []
            trigger = legs[0].get("status") if legs else "missing-first-leg"
            stats = triggers.setdefault(trigger, {"runs": 0, "escalated": 0})
            stats["runs"] += 1
            stats["escalated"] += int(len(legs) > 1)
    if validate_matrix:
        expected_cells = {_cell(r) for r in campaign_rows()}
        if cells != expected_cells:
            errors.append({"error": "campaign cells differ from frozen matrix",
                           "missing": len(expected_cells - cells),
                           "unexpected": len(cells - expected_cells)})
    browser_builds = {b.get("browser") for row in rows
                      for b in (row.get("builds_before"), row.get("builds_after"))
                      if isinstance(b, dict) and isinstance(b.get("browser"), str)}
    sec_builds = {b.get("sec") for row in rows
                  for b in (row.get("builds_before"), row.get("builds_after"))
                  if isinstance(b, dict) and isinstance(b.get("sec"), str)}
    if len(browser_builds) > 1 or len(sec_builds) > 1:
        errors.append({"error": "campaign spans more than one deployed build",
                       "browser": sorted(browser_builds), "sec": sorted(sec_builds)})
    for metrics in by_mode.values():
        runs = metrics["runs"]
        for key in ("usd", "tokens", "wall_ms"):
            metrics[key + "_per_task"] = metrics[key] / runs if runs else None
    for stats in triggers.values():
        stats["rate"] = stats["escalated"] / stats["runs"]
    esc_runs = by_mode["escalate"]["runs"]
    escalated = sum(v["escalated"] for v in triggers.values())
    elapsed_values = [e["campaign_elapsed_seconds"] for e in events
                      if "campaign_elapsed_seconds" in e]
    campaign_elapsed = (max(elapsed_values, default=0.0)
                        if all(map(_nonnegative_finite, elapsed_values)) else None)
    return {
        "campaign": "M44", "registry_sha256": registry_sha256(),
        "registry": registry_payload(), "run_ids": sorted(run_ids),
        "builds": {"browser": sorted(browser_builds), "sec": sorted(sec_builds)},
        "parameters": starts[0] if len(starts) == 1 else None,
        "campaign_elapsed_seconds": campaign_elapsed,
        "expected_runs": DEFAULT_MAX_RUNS,
        "completed_runs": len(rows) - len(pending_adjudications),
        "complete": len(rows) == DEFAULT_MAX_RUNS and not pending_adjudications and
                    not partial and not errors,
        "partial_evidence": partial, "interruptions": [e for e in events if e.get("event") in
                                                          {"abort", "active_unknown"}],
        "terminal_observed_pending": [e for e in events if e.get("event") == "terminal_observed"
                                      and e.get("run_id") not in terminal_ids],
        "pending_adjudications": pending_adjudications,
        "validation_errors": errors,
        "stop_ship": any(v["wrong_success"] for v in by_mode.values()),
        "by_mode": by_mode, "totals": totals,
        "escalation_rate": {"count": escalated, "denominator": esc_runs,
                            "rate": escalated / esc_runs if esc_runs else None},
        "escalation_by_trigger": triggers, "limitations": LIMITATIONS, "results": rows,
    }


def _load_events(path: Path) -> list[dict]:
    return [_strict_loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _elapsed(events: list[dict]) -> float:
    started = next(e["started_at"] for e in events if e.get("event") == "campaign_start")
    return max(0.0, time.time() - _parse_time(started).timestamp())


def _poll_terminal(base: str, accepted: dict, journal: Path, events: list[dict],
                   run_timeout: int) -> dict | None:
    run_id = accepted["run_id"]
    deadline = time.monotonic() + run_timeout
    try:
        while time.monotonic() < deadline:
            record = _json(base + f"/tasks/{run_id}")
            if record.get("status") != "running":
                observed = {"event": "terminal_observed", "run_id": run_id,
                            "spec": accepted["spec"], "record": record,
                            "builds_before": accepted["builds_before"],
                            "truth_snapshot": accepted["truth_snapshot"],
                            "ground_truth": accepted["ground_truth"],
                            "accepted_elapsed_seconds": accepted["accepted_elapsed_seconds"],
                            "campaign_elapsed_seconds": _elapsed(events)}
                _append(journal, observed)  # full paid result is durable before provenance reads
                return observed
            time.sleep(2)
    except Exception as exc:
        reason = f"terminal poll failed: {type(exc).__name__}: {exc}"
    else:
        reason = f"still running after client timeout {run_timeout}s"
    _append(journal, {"event": "active_unknown", "run_id": run_id,
                      "spec": accepted["spec"], "reason": reason,
                      "campaign_elapsed_seconds": _elapsed(events)})
    return None


def _finish_terminal(base: str, observed: dict, journal: Path, events: list[dict]) -> bool:
    spec, record = observed["spec"], observed["record"]
    try:
        after = _builds(base, spec["url"].startswith(SEC_BASE))
    except Exception as exc:
        _append(journal, {"event": "active_unknown", "run_id": observed["run_id"],
                          "spec": spec, "reason":
                          f"terminal saved; provenance read pending: {type(exc).__name__}: {exc}",
                          "campaign_elapsed_seconds": _elapsed(events)})
        return False
    probe = next(p for p in PROBES if p["id"] == spec["probe_id"])
    row = {"event": "terminal", "run_id": observed["run_id"], **spec,
           "registry_sha256": registry_sha256(), "record": record,
           "builds_before": observed["builds_before"], "builds_after": after,
           "truth_snapshot": observed["truth_snapshot"],
           "ground_truth": observed["ground_truth"],
           "client_seconds": max(0.0, _elapsed(events) -
                                 float(observed.get("accepted_elapsed_seconds", 0))),
           "campaign_elapsed_seconds": _elapsed(events),
           "terminal_at": datetime.now(timezone.utc).isoformat(),
           "classification": classify(record, observed["ground_truth"], probe["match"])}
    _append(journal, row)
    if _journal_errors(_load_events(journal)):
        _append(journal, {"event": "abort", "run_id": observed["run_id"],
                          "reason": "invalid terminal evidence",
                          "campaign_elapsed_seconds": _elapsed(events)})
        return False
    if row["classification"] == "needs_adjudication":
        return False
    if (record.get("mode") != spec["mode"] or not record.get("model") or
            row["builds_before"] != after or row["classification"] in {"wrong_success", "partial"}):
        _append(journal, {"event": "abort", "run_id": observed["run_id"],
                          "reason": "stop-ship or unattributable evidence",
                          "campaign_elapsed_seconds": _elapsed(events)})
        return False
    return True


def _resolve_unfinished(base: str, journal: Path, events: list[dict], run_timeout: int) -> bool:
    observed = {e["run_id"]: e for e in events if e.get("event") == "terminal_observed"}
    for accepted in _unresolved(events):
        saved = observed.get(accepted["run_id"]) or _poll_terminal(
            base, accepted, journal, events, run_timeout)
        if not saved or not _finish_terminal(base, saved, journal, events):
            return False
        events[:] = _load_events(journal)
    return True


def _apply_adjudication(events: list[dict], path: Path | None, journal: Path) -> bool:
    journal_errors = _journal_errors(events)
    if journal_errors:
        raise ValueError(f"hostile or corrupt journal: {journal_errors}")
    pending = _pending_adjudications(events)
    if not pending:
        if path:
            raise ValueError("adjudication supplied with no pending run")
        return True
    if not path:
        return False
    if path.suffix != ".json" or path == journal:
        raise ValueError("adjudication must be a distinct .json artifact")
    data = _strict_loads(path.read_bytes())
    terminal = pending[0]
    errors = _adjudication_errors(data, terminal,
                                  allowed_models=events[0]["adjudicator_models"])
    if errors:
        raise ValueError(f"invalid adjudication: {errors}")
    run_id = terminal["run_id"]
    decision = data[run_id]
    _append(journal, {"event": "adjudicated", "run_id": run_id, "decision": decision,
                      "campaign_elapsed_seconds": _elapsed(events)})
    if decision["label"] == "wrong_success":
        _append(journal, {"event": "abort", "run_id": run_id,
                          "reason": "adjudicated wrong-success stop-ship",
                          "campaign_elapsed_seconds": _elapsed(events)})
        return False
    return True


def execute(base: str, truth_path: Path, journal: Path, *, recover: bool,
            max_usd: float, max_wall_seconds: int, run_timeout: int,
            adjudication_path: Path | None = None) -> dict:
    if not all(map(_positive_finite, (max_usd, max_wall_seconds, run_timeout))):
        raise ValueError("USD and time stop lines must be finite and positive")
    if recover:
        events = _load_events(journal)
        errors = _journal_errors(events)
        if errors:
            raise ValueError(f"hostile or corrupt journal: {errors}")
        start = events[0]
        if (start.get("max_usd_completed_stop") != max_usd or
                start.get("max_wall_seconds_client") != max_wall_seconds or
                start.get("run_timeout_client") != run_timeout):
            raise ValueError("recovery limits must match campaign_start")
        initial_event = events[1]
        initial_truth = {**initial_event["truth_snapshot"], "tasks": initial_event["tasks"]}
    else:
        initial_truth = _truth_snapshot(truth_path)
        started_at = datetime.now(timezone.utc).isoformat()
        snapshot_id = {k: initial_truth[k] for k in ("sha256", "captured_at")}
        start = {"event": "campaign_start", "started_at": started_at,
                 "registry_sha256": registry_sha256(), "max_runs": DEFAULT_MAX_RUNS,
                 "max_usd_completed_stop": max_usd,
                 "max_wall_seconds_client": max_wall_seconds,
                 "run_timeout_client": run_timeout,
                 "truth_snapshot": snapshot_id,
                 "limitations": LIMITATIONS,
                 "adjudicator_models": list(ADJUDICATOR_MODELS)}
        _create_journal(journal, start)
        _append(journal, {"event": "truth_snapshot", "scope": "campaign_start",
                          "truth_snapshot": snapshot_id, "tasks": initial_truth["tasks"],
                          "campaign_elapsed_seconds": _elapsed([start])})
        events = _load_events(journal)
    build_events = [e for e in events if e.get("event") == "campaign_builds"]
    if build_events:
        campaign_builds = build_events[0]["builds"]
    else:
        try:
            campaign_builds = _builds(base, True)
        except Exception as exc:
            _append(journal, {"event": "abort", "reason":
                              f"campaign build preflight: {type(exc).__name__}: {exc}",
                              "campaign_elapsed_seconds": _elapsed(events)})
            return summarize(_load_events(journal))
        _append(journal, {"event": "campaign_builds", "builds": campaign_builds,
                          "campaign_elapsed_seconds": _elapsed(events)})
        events = _load_events(journal)
    # Recovery is GET-only until every accepted run has a durable terminal row.
    if not _resolve_unfinished(base, journal, events, run_timeout):
        return summarize(_load_events(journal))
    events = _load_events(journal)
    if not _apply_adjudication(events, adjudication_path, journal):
        return summarize(_load_events(journal))
    events = _load_events(journal)
    report = summarize(events, validate_matrix=False)
    if report["validation_errors"] or report["stop_ship"] or any(
            e.get("event") == "submit_unknown" for e in events):
        return report
    for spec in _remaining_specs(events):
        probe = next(p for p in PROBES if p["id"] == spec["probe_id"])
        spent, elapsed = summarize(events, validate_matrix=False)["totals"]["usd"], _elapsed(events)
        if spent >= max_usd or elapsed >= max_wall_seconds:
            _append(journal, {"event": "abort", "reason": "completed stop line reached",
                              "completed_usd": spent, "campaign_elapsed_seconds": elapsed})
            break
        try:
            _matching_builds(base, spec, campaign_builds)
            _wait_ready(base)
        except Exception as exc:
            _append(journal, {"event": "abort", "reason": f"preflight: {type(exc).__name__}: {exc}",
                              "spec": spec, "campaign_elapsed_seconds": _elapsed(events)})
            break
        if _elapsed(events) >= max_wall_seconds:
            _append(journal, {"event": "abort", "reason": "client time stop before submit",
                              "spec": spec, "campaign_elapsed_seconds": _elapsed(events)})
            break
        # This is intentionally the last read before every POST. Mutable truth
        # cannot age across a cohort; immutable truth survives recovery from the
        # campaign_start snapshot rather than silently following a changed file.
        try:
            snapshot = _truth_for_post(truth_path, probe, initial_truth)
        except Exception as exc:
            _append(journal, {"event": "abort", "reason": f"truth pre-submit: {exc}",
                              "spec": spec, "campaign_elapsed_seconds": _elapsed(events)})
            break
        snapshot_id = {k: snapshot[k] for k in ("sha256", "captured_at")}
        _append(journal, {"event": "truth_snapshot", "scope": "run", "spec": spec,
                          "truth_snapshot": snapshot_id,
                          "ground_truth": snapshot["tasks"][probe["id"]],
                          "campaign_elapsed_seconds": _elapsed(events)})
        events = _load_events(journal)
        payload = {"task": spec["task"], "url": spec["url"], "mode": spec["mode"]}
        try:
            before = _matching_builds(base, spec, campaign_builds)
        except Exception as exc:
            _append(journal, {"event": "abort", "reason": f"pre-submit build: {exc}",
                              "spec": spec, "campaign_elapsed_seconds": _elapsed(events)})
            break
        if _elapsed(events) >= max_wall_seconds:
            _append(journal, {"event": "abort", "reason": "client time stop before submit",
                              "spec": spec, "campaign_elapsed_seconds": _elapsed(events)})
            break
        try:
            submitted = _json(base + "/tasks", payload, timeout=30)
        except Exception as exc:
            _append(journal, {"event": "submit_unknown", "spec": spec, "payload": payload,
                              "error": f"{type(exc).__name__}: {exc}",
                              "campaign_elapsed_seconds": _elapsed(events)})
            break
        run_id = submitted.get("run_id")
        if not run_id:
            _append(journal, {"event": "submit_unknown", "spec": spec, "payload": payload,
                              "response": submitted, "error": "200 response had no run_id",
                              "campaign_elapsed_seconds": _elapsed(events)})
            break
        accepted = {"event": "accepted", "run_id": run_id, "spec": spec,
                    "payload": payload, "builds_before": before,
                    "truth_snapshot": snapshot_id, "ground_truth": snapshot["tasks"][probe["id"]],
                    "accepted_elapsed_seconds": _elapsed(events)}
        _append(journal, accepted)
        events = _load_events(journal)
        observed = _poll_terminal(base, accepted, journal, events, run_timeout)
        if not observed or not _finish_terminal(base, observed, journal, events):
            break
        events = _load_events(journal)
    _append(journal, {"event": "campaign_end", "campaign_elapsed_seconds": _elapsed(events)})
    return summarize(_load_events(journal))


def self_check(check: str) -> dict:
    wrong = {}
    if check == "registry":
        rows = campaign_rows()
        identities = {(r["task"], r["url"], r["language"]) for r in rows}
        source_counts = {s: sum(s in p["sources"] for p in PROBES)
                         for s in ("D28", "M40-card", "ADR-030", "interviewer-INTC")}
        got = {"probes": len(PROBES), "identities": len(identities), "runs": len(rows),
               "modes": sorted({r["mode"] for r in rows}), "reps": max(r["rep"] for r in rows),
               "source_counts": source_counts, "sha256": registry_sha256(),
               "typed_match_rules": all(p["match"] and all(
                   rule["kind"] in {"number", "integer", "text", "status"} and
                   isinstance(rule["fields"], tuple) for rule in p["match"])
                   and isinstance(p["mutable"], bool) for p in PROBES),
               "boundary_safe_matches": (
                   not _matches(_rule("integer", "items", "extracted"), 18, "180 extracted") and
                   not _matches(_rule("number", "rate"), "2.25", "12.25%") and
                   not _matches(_rule("status", "status"), "success", "not success") and
                   not _matches(_rule("status", "status"), "success", "not successful") and
                   _matches(_rule("status", "status"), "success_with_warning",
                            "status: success_with_warning") and
                   _matches(_rule("integer", "items", "extracted"), 19,
                            "19 extracted items")),
               "assertion_safe_matches": (
                   not _matches(_rule("status", "status"), "success",
                                "success was not achieved") and
                   not _matches(_rule("integer", "items", "extracted"), 18,
                                "Expected 18, but 17 items were extracted") and
                   not _matches(_rule("number", "rate"), "2.25",
                                "The old rate was 2.25%; the current rate is 3.00%"))}
        text_truth = {"values": ["Leo Tolstoy"],
                      "accepted_exact": ["Leo Tolstoy", "Author: Leo Tolstoy"]}
        got["text_tri_state"] = (
            classify({"status": "success", "answer": "  LEO TOLSTOY  "}, text_truth,
                     (_rule("text"),)) == "correct" and
            classify({"status": "success", "answer": "Author: Leo Tolstoy"}, text_truth,
                     (_rule("text"),)) == "correct" and
            all(classify({"status": "success", "answer": answer}, text_truth,
                         (_rule("text"),)) == "needs_adjudication" for answer in (
                             "The author is Leo Tolstoy", "The author is not Leo Tolstoy",
                             "Leo Tolstoy was formerly the author", "Title: Leo Tolstoy")))
        want = {"probes": 14, "identities": 28, "runs": 252,
                "modes": sorted(MODES), "reps": 3,
                "source_counts": {"D28": 6, "M40-card": 8, "ADR-030": 2,
                                  "interviewer-INTC": 1},
                "sha256": FROZEN_REGISTRY_SHA256, "typed_match_rules": True,
                "boundary_safe_matches": True, "assertion_safe_matches": True,
                "text_tri_state": True}
        wrong = {k: {"want": want[k], "got": got[k]} for k in want if got[k] != want[k]}
        return {"passed": not wrong, "wrong": wrong, "got": got}
    if check != "safety":
        return {"passed": False, "wrong": {"unknown_check": check}}

    def budgets(actions=2, replans=0):
        return {"actions": actions, "replans": replans, "llm_tokens": 10,
                "llm_usd": .01, "judge_calls": 1, "judge_tokens": 2,
                "judge_usd": .001, "ms": 100}

    def rec(mode, status="success", answer="42", actions=2, replans=0, legs=None,
            failure=None):
        out = {"mode": mode, "model": "model", "status": status, "answer": answer,
               "reason": failure, "budgets_spent": budgets(actions, replans),
               "evidence": {"trace": [{"failure_class": None}]}}
        if legs is not None:
            out["legs"] = legs
            out["budgets_spent"] = {key: sum(
                leg["budgets_spent"][key] for leg in legs) for key in ACCOUNTING_KEYS}
        return out

    same = {"browser": "abc", "browser_source": "image"}
    truth, snapshot = {"verified_at": "2026-08-29T00:00:00+00:00", "source": "fixture",
                       "values": ["42"]}, {"sha256": "truth-sha", "captured_at":
                                                       "2026-08-29T00:00:00+00:00"}
    start = {"event": "campaign_start", "started_at": "2026-08-29T00:00:00+00:00",
             "registry_sha256": registry_sha256(), "max_runs": DEFAULT_MAX_RUNS,
             "max_usd_completed_stop": DEFAULT_MAX_USD,
             "max_wall_seconds_client": DEFAULT_MAX_WALL_SECONDS,
             "run_timeout_client": DEFAULT_RUN_TIMEOUT,
             "truth_snapshot": snapshot, "limitations": LIMITATIONS,
             "adjudicator_models": ["deepseek/deepseek-v4-flash-0731"]}
    initial = {"event": "truth_snapshot", "scope": "campaign_start",
               "truth_snapshot": snapshot,
               "tasks": {p["id"]: {**truth, "values": ["42"] * len(p["match"])}
                         for p in PROBES}}
    records = {
        "plan": rec("plan", replans=1),
        "loop": rec("loop", answer="41", actions=6),
        "escalate": rec("escalate", status="failure:env", answer=None, actions=8, legs=[
            {"mode": "plan", "status": "failure:locate", "reason": "locate", "steps": 2,
             "budgets_spent": budgets(2)},
            {"mode": "loop", "status": "failure:env", "reason": "budget", "steps": 6,
             "budgets_spent": budgets(6)}]),
    }
    campaign_builds = {"event": "campaign_builds",
                       "builds": {**same, "sec": "sec-sha"},
                       "campaign_elapsed_seconds": 0.5}
    events = [start, initial, campaign_builds]
    for mode, run_id in zip(MODES, ("p", "l", "e")):
        spec = next(r for r in campaign_rows() if r["mode"] == mode and r["rep"] == 1)
        before = same
        after = same
        accepted = {"event": "accepted", "run_id": run_id, "spec": spec,
                    "payload": {key: spec[key] for key in ("task", "url", "mode")},
                    "builds_before": before, "truth_snapshot": snapshot,
                    "ground_truth": truth, "accepted_elapsed_seconds": 1.0}
        run_snapshot = {"event": "truth_snapshot", "scope": "run", "spec": spec,
                        "truth_snapshot": snapshot, "ground_truth": truth}
        observed = {"event": "terminal_observed", "run_id": run_id, "spec": spec,
                    "record": records[mode], "builds_before": before,
                    "truth_snapshot": snapshot, "ground_truth": truth,
                    "accepted_elapsed_seconds": 1.0, "campaign_elapsed_seconds": 2.0}
        cls = ("correct" if mode == "plan" else
               "wrong_success" if mode == "loop" else "loud_failure")
        terminal = {"event": "terminal", "run_id": run_id, **spec,
                    "registry_sha256": registry_sha256(), "record": records[mode],
                    "builds_before": before, "builds_after": after,
                    "truth_snapshot": snapshot, "ground_truth": truth,
                    "client_seconds": 1.0, "campaign_elapsed_seconds": 2.0,
                    "terminal_at": "2026-08-29T00:00:01+00:00",
                    "classification": cls}
        events.extend((run_snapshot, accepted, observed, terminal))
    events.append({"event": "active_unknown", "run_id": "known", "reason": "client timeout"})
    report = summarize(events, validate_matrix=False)
    drift_events = _strict_loads(json.dumps(events, allow_nan=False))
    next(e for e in reversed(drift_events) if e.get("event") == "terminal")["builds_after"] = {
        "browser": "def", "browser_source": "image"}
    drift_report = summarize(drift_events, validate_matrix=False)
    missing_events = _strict_loads(json.dumps(events, allow_nan=False))
    next(e for e in missing_events if e.get("event") == "terminal")["record"]["model"] = None
    missing_attr = summarize(missing_events, validate_matrix=False)
    first_accepted = next(e for e in events if e.get("event") == "accepted")
    first_observed = next(e for e in events if e.get("event") == "terminal_observed")
    first_snapshot = events[events.index(first_accepted) - 1]
    orphan_events = [start, initial, campaign_builds, first_snapshot,
                     {**first_accepted, "run_id": "paid-but-not-terminal"}]
    orphan = summarize(orphan_events)
    calls = [r.get("planner_calls") for r in report["results"]]

    accepted_only = [start, initial, campaign_builds, first_snapshot,
                     first_accepted, first_observed]
    duplicate = [start, initial, campaign_builds, first_snapshot,
                 first_accepted, {**first_accepted}]
    zero = rec("plan", status="unsupported", answer=None, actions=0)
    zero["budgets_spent"] = {key: 0 for key in ACCOUNTING_KEYS}
    nav = rec("plan", status="failure:nav", answer=None, actions=1)
    nav["evidence"]["trace"][0]["failure_class"] = "nav"
    missing = rec("plan")
    missing["budgets_spent"].pop("judge_usd")
    spending_legs = records["escalate"]["legs"]
    bad_escalate = rec("escalate", legs=spending_legs)
    bad_escalate["budgets_spent"] = {key: 0 for key in ACCOUNTING_KEYS}

    artifact_ok = truth_ok = stale_refused = suffix_refused = json_standard = strict_reads = False
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        journal_path, report_path = folder / "run.jsonl", folder / "run.json"
        _create_journal(journal_path, start)
        _write_report(report_path, journal_path, {"complete": False})
        try:
            _create_journal(folder / "run.txt", start)
        except ValueError:
            suffix_refused = True
        try:
            _create_journal(journal_path, start)
        except FileExistsError:
            try:
                _write_report(report_path, journal_path, {})
            except FileExistsError:
                artifact_ok = suffix_refused
        now = datetime.now(timezone.utc)
        truth_data = {"registry_sha256": registry_sha256(), "captured_at": now.isoformat(),
                      "tasks": {p["id"]: {"verified_at": now.isoformat(), "source": "manual",
                                           "values": ["42"] * len(p["match"]),
                                           **({"accepted_exact": ["42"]} if any(
                                               rule["kind"] == "text" for rule in p["match"])
                                              else {})} for p in PROBES}}
        truth_data["tasks"][PROBES[0]["id"]]["verified_at"] = "1970-01-01T00:00:00+00:00"
        truth_path = folder / "truth.json"
        truth_path.write_text(json.dumps(truth_data, allow_nan=False), encoding="utf-8")
        try:
            _truth_for_post(truth_path, PROBES[0], initial)
        except ValueError:
            stale_refused = True
            truth_data["tasks"][PROBES[0]["id"]]["verified_at"] = now.isoformat()
            truth_path.write_text(json.dumps(truth_data, allow_nan=False), encoding="utf-8")
            fresh = _truth_for_post(truth_path, PROBES[0], initial)
            truth_ok = bool(fresh["sha256"] and fresh["captured_at"])
        before_json = journal_path.read_text()
        refused = []
        for write in (
                lambda: _append(journal_path, {"bad": float("nan")}),
                lambda: _create_journal(folder / "nonfinite.jsonl", {"bad": float("inf")}),
                lambda: _write_report(folder / "nonfinite.json", journal_path,
                                      {"bad": float("-inf")})):
            try:
                write()
            except ValueError:
                refused.append(True)
        json_standard = (len(refused) == 3 and journal_path.read_text() == before_json and
                         not (folder / "nonfinite.jsonl").exists() and
                         not (folder / "nonfinite.json").exists())
        bad_truth = folder / "bad-truth.json"
        bad_truth.write_text('{"captured_at": NaN}', encoding="utf-8")
        bad_journal = folder / "bad-journal.jsonl"
        bad_journal.write_text('{"event":"campaign_start","max_usd_completed_stop":NaN}\n',
                               encoding="utf-8")

        class BadResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return b'{"ready":NaN}'

        duplicate_truth = folder / "duplicate-truth.json"
        duplicate_truth.write_text('{"registry_sha256":"one","registry_sha256":"two"}')
        duplicate_journal = folder / "duplicate-journal.jsonl"
        duplicate_journal.write_text('{"event":"abort","event":"campaign_start"}\n')
        read_refusals = []
        for read in (lambda: _strict_loads('{"value":NaN}'),
                     lambda: _strict_loads('{"value":1,"value":2}'),
                     lambda: _truth_snapshot(bad_truth),
                     lambda: _truth_snapshot(duplicate_truth),
                     lambda: _load_events(bad_journal),
                     lambda: _load_events(duplicate_journal),
                     lambda: _json("https://invalid", opener=lambda *a, **k: BadResponse()),
                     lambda: _json("https://invalid", opener=lambda *a, **k:
                                   type("R", (), {"__enter__": lambda s: s,
                                                  "__exit__": lambda *a: None,
                                                  "read": lambda s: b'{"ready":true,"ready":false}'})())):
            try:
                read()
            except ValueError:
                read_refusals.append(True)
        strict_reads = len(read_refusals) == 8

    corrupt_start = _strict_loads(json.dumps(events, allow_nan=False))
    corrupt_start[1]["truth_snapshot"]["sha256"] = "other"
    wrong_registry = _strict_loads(json.dumps(events, allow_nan=False))
    wrong_registry[0]["registry_sha256"] = "other"
    wrong_run_count = _strict_loads(json.dumps(events, allow_nan=False))
    wrong_run_count[0]["max_runs"] = 1
    wrong_start_fields = []
    for key, value in (("started_at", "not-a-time"),
                       ("max_usd_completed_stop", 0),
                       ("max_wall_seconds_client", 0),
                       ("run_timeout_client", 0),
                       ("limitations", {}),
                       ("adjudicator_models", ["unlisted/model"])):
        hostile = _strict_loads(json.dumps(events, allow_nan=False))
        hostile[0][key] = value
        wrong_start_fields.append(bool(_journal_errors(hostile)))
    nonfinite_starts = [
        [{**events[0], key: value}, *events[1:]]
        for key in ("max_usd_completed_stop", "max_wall_seconds_client", "run_timeout_client")
        for value in (float("nan"), float("inf"), float("-inf"))]
    missing_run_snapshot = [e for i, e in enumerate(events)
                            if i != events.index(first_snapshot)]
    payload_mutations = []
    for payload in (
            {**first_accepted["payload"], "model": "override"},
            {"task": first_accepted["spec"]["task"],
             "url": first_accepted["spec"]["url"]},
            {**first_accepted["payload"], "mode": "loop"},
            {**first_accepted["payload"], "task": "different"},
            {**first_accepted["payload"], "url": "https://invalid"},
            {**first_accepted["payload"], "extra": True}):
        hostile = _strict_loads(json.dumps(events, allow_nan=False))
        next(e for e in hostile if e.get("event") == "accepted")["payload"] = payload
        payload_mutations.append(bool(_journal_errors(hostile)))
    bad_build_events = _strict_loads(json.dumps(events, allow_nan=False))
    next(e for e in bad_build_events if e.get("event") == "terminal")["builds_before"] = {
        "browser": "abc", "browser_source": "runtime"}
    missing_build_event = [e for e in events if e.get("event") != "campaign_builds"]
    duplicate_build_event = [*events[:3], campaign_builds, *events[3:]]
    unbound_builds = _strict_loads(json.dumps(events, allow_nan=False))
    for event in unbound_builds:
        if event.get("event") in {"accepted", "terminal_observed", "terminal"}:
            event["builds_before"] = {"browser": "other", "browser_source": "image"}
            if event.get("event") == "terminal":
                event["builds_after"] = event["builds_before"]
    sec_events = _strict_loads(json.dumps(events, allow_nan=False))
    sec_spec = next(r for r in campaign_rows()
                    if r["probe_id"] == "sec-aapl-count" and r["language"] == "en" and
                    r["mode"] == "plan" and r["rep"] == 1)
    for event in sec_events:
        if event.get("run_id") == "p" or (event.get("spec") or {}).get("mode") == "plan" and (
                event.get("spec") or {}).get("probe_id") == "x-rates-eur-usd":
            if "spec" in event:
                event["spec"] = sec_spec
            if event.get("event") == "accepted":
                event["payload"] = {key: sec_spec[key] for key in ("task", "url", "mode")}
            if event.get("event") == "terminal":
                event.update(sec_spec)
            for key in ("builds_before", "builds_after"):
                if key in event:
                    event[key]["sec"] = "sec-sha"
    sec_unbound = _strict_loads(json.dumps(sec_events, allow_nan=False))
    for event in sec_unbound:
        if event.get("run_id") == "p":
            for key in ("builds_before", "builds_after"):
                (event.get(key) or {}).pop("sec", None)
    bad_classification = _strict_loads(json.dumps(events, allow_nan=False))
    next(e for e in bad_classification if e.get("event") == "terminal")["classification"] = "refusal"
    bad_terminal_accounting = _strict_loads(json.dumps(events, allow_nan=False))
    next(e for e in bad_terminal_accounting if e.get("event") == "terminal")["record"][
        "budgets_spent"].pop("judge_usd")
    invalid_build_events = []
    for key in ("browser", "sec"):
        for value in (123, ["sha"], {"sha": "x"}, True, " ", "abc def"):
            hostile = _strict_loads(json.dumps(events, allow_nan=False))
            next(e for e in hostile if e.get("event") == "campaign_builds")["builds"][key] = value
            invalid_build_events.append(hostile)
    invalid_build_containers = []
    for value in (123, ["sha"], True, "sha"):
        hostile = _strict_loads(json.dumps(events, allow_nan=False))
        next(e for e in hostile if e.get("event") == "campaign_builds")["builds"] = value
        invalid_build_containers.append(hostile)
    invalid_elapsed_events = []
    elapsed_reports_are_loud = True
    for value in (-1, float("nan"), [], {}, True, "0"):
        hostile = _strict_loads(json.dumps(events, allow_nan=False))
        next(e for e in hostile if e.get("event") == "campaign_builds")[
            "campaign_elapsed_seconds"] = value
        invalid_elapsed_events.append(hostile)
        try:
            poison = summarize(hostile[:3], validate_matrix=False)
            elapsed_reports_are_loud &= (poison["campaign_elapsed_seconds"] is None and
                                         bool(poison["validation_errors"]))
        except (TypeError, ValueError):
            elapsed_reports_are_loud = False

    original_json = globals()["_json"]
    invalid_build_reads = valid_build_reads = 0
    try:
        for browser, sec in [(123, "sec"), (["sha"], "sec"), ({"sha": "x"}, "sec"),
                             (True, "sec"), (" ", "sec"), ("abc def", "sec"),
                             ("abc1234", 123),
                             ("abc1234", ["sec"]), ("abc1234", {"sha": "sec"}),
                             ("abc1234", True), ("abc1234", " "),
                             ("abc1234", "sec sha")]:
            globals()["_json"] = lambda url, b=browser, s=sec: (
                {"sha": b, "source": "image"} if url.endswith("/version") else {"git_sha": s})
            try:
                _builds("https://invalid", True)
            except RuntimeError:
                invalid_build_reads += 1
        for browser, sec in [("abc1234", "sec-sha"), ("a" * 40, "deadbeef")]:
            globals()["_json"] = lambda url, b=browser, s=sec: (
                {"sha": b, "source": "image"} if url.endswith("/version") else {"git_sha": s})
            valid_build_reads += int(_builds("https://invalid", True)["browser"] == browser)
    finally:
        globals()["_json"] = original_json

    text_spec = next(r for r in campaign_rows()
                     if r["probe_id"] == "openlibrary-author" and
                     r["language"] == "en" and r["mode"] == "plan" and r["rep"] == 1)
    text_truth = {"verified_at": "2026-08-29T00:00:00+00:00", "source": "fixture",
                  "values": ["Leo Tolstoy"],
                  "accepted_exact": ["Leo Tolstoy", "Author: Leo Tolstoy"]}
    text_initial = {**initial, "tasks": {**initial["tasks"],
                                          "openlibrary-author": text_truth}}
    text_record = rec("plan", answer="The author is Leo Tolstoy")
    text_terminal_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    text_snapshot = {"event": "truth_snapshot", "scope": "run", "spec": text_spec,
                     "truth_snapshot": snapshot, "ground_truth": text_truth}
    text_accepted = {"event": "accepted", "run_id": "text-run", "spec": text_spec,
                     "payload": {key: text_spec[key] for key in ("task", "url", "mode")},
                     "builds_before": same, "truth_snapshot": snapshot,
                     "ground_truth": text_truth, "accepted_elapsed_seconds": 1.0}
    text_observed = {"event": "terminal_observed", "run_id": "text-run", "spec": text_spec,
                     "record": text_record, "builds_before": same,
                     "truth_snapshot": snapshot, "ground_truth": text_truth,
                     "accepted_elapsed_seconds": 1.0, "campaign_elapsed_seconds": 2.0}
    text_terminal = {"event": "terminal", "run_id": "text-run", **text_spec,
                     "registry_sha256": registry_sha256(), "record": text_record,
                     "builds_before": same, "builds_after": same,
                     "truth_snapshot": snapshot, "ground_truth": text_truth,
                     "client_seconds": 1.0, "campaign_elapsed_seconds": 2.0,
                     "terminal_at": text_terminal_at.isoformat(),
                     "classification": "needs_adjudication"}
    pending_events = [start, text_initial, campaign_builds, text_snapshot, text_accepted,
                      text_observed, text_terminal]
    decision = {"registry_sha256": registry_sha256(),
                "truth_snapshot_sha256": snapshot["sha256"], "label": "correct",
                "evidence": "human checked the cited page evidence",
                "source": {"kind": "human", "identity": "reviewer"},
                "adjudicated_at": datetime.now(timezone.utc).isoformat()}
    hostile_decisions = [
        {"other-run": decision},
        {"text-run": {**decision, "registry_sha256": "forged"}},
        {"text-run": {**decision, "truth_snapshot_sha256": "stale-truth"}},
        {"text-run": {**decision,
                       "source": {"kind": "model", "model": "unlisted/model"}}},
        {"text-run": {**decision, "source": {"kind": "model", "model": "model"}}},
        {"text-run": {**decision,
                       "adjudicated_at": (text_terminal_at - timedelta(seconds=1)).isoformat()}},
    ]
    adjudication_state = (not _journal_errors(pending_events) and
                          len(_pending_adjudications(pending_events)) == 1 and
                          not _adjudication_errors(
                              {"text-run": {**decision,
                                            "source": {"kind": "model", "model":
                                                       ADJUDICATOR_MODELS[0]}}},
                              text_terminal) and
                          all(_adjudication_errors(value, text_terminal)
                              for value in hostile_decisions) and
                          bool(_adjudication_errors(
                              {"text-run": {**decision,
                                            "source": {"kind": "model", "model": "other"}}},
                              {**text_terminal, "record": {**text_record, "model": None}})) and
                          bool(_adjudication_errors(
                              {"text-run": {**decision,
                                            "source": {"kind": "model", "model": "model"}}},
                              {**text_terminal, "record": {**text_record,
                                                            "model": " ＭＯＤＥＬ "}})) and
                          bool(_journal_errors([
                              *pending_events[:-1],
                              {**text_terminal,
                               "builds_after": {"browser": "changed",
                                                "browser_source": "image"}}])))
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)

        def journal_with_pending(name):
            path = folder / name
            _create_journal(path, pending_events[0])
            for event in pending_events[1:]:
                _append(path, event)
            return path

        correct_path, correct_artifact = journal_with_pending("correct.jsonl"), folder / "correct.json"
        correct_artifact.write_text(json.dumps({"text-run": decision}, allow_nan=False))
        artifact_before = correct_artifact.read_bytes()
        correct_applied = _apply_adjudication(_load_events(correct_path), correct_artifact,
                                              correct_path)
        correct_events = _load_events(correct_path)
        duplicate_refused = False
        try:
            _apply_adjudication(correct_events, correct_artifact, correct_path)
        except ValueError:
            duplicate_refused = True
        wrong_path, wrong_artifact = journal_with_pending("wrong.jsonl"), folder / "wrong.json"
        wrong_artifact.write_text(json.dumps({"text-run": {**decision,
                                                           "label": "wrong_success"}},
                                             allow_nan=False))
        wrong_applied = _apply_adjudication(_load_events(wrong_path), wrong_artifact, wrong_path)
        wrong_report = summarize(_load_events(wrong_path), validate_matrix=False)
        pending_report = summarize(pending_events, validate_matrix=False)
        conflicting_events = [*correct_events,
                              {**correct_events[-1], "decision": {**decision,
                                                                   "label": "wrong_success"}}]
        conflicting_report = summarize(conflicting_events, validate_matrix=False)
        adjudication_state = (adjudication_state and correct_applied and not wrong_applied and
                              duplicate_refused and correct_artifact.read_bytes() == artifact_before and
                              not _pending_adjudications(correct_events) and
                              len(_remaining_specs(correct_events)) == DEFAULT_MAX_RUNS - 1 and
                              len([e for e in correct_events if e.get("event") == "accepted"]) == 1 and
                              wrong_report["stop_ship"] and
                              bool(conflicting_report["validation_errors"]) and
                              conflicting_report["pending_adjudications"] and
                              not conflicting_report["stop_ship"] and
                              pending_report["completed_runs"] == 0 and
                              pending_report["by_mode"]["plan"]["needs_adjudication"] == 1)
    with tempfile.TemporaryDirectory() as td:
        hostile_journal = Path(td) / "hostile.jsonl"
        _create_journal(hostile_journal, bad_classification[0])
        for event in bad_classification[1:]:
            _append(hostile_journal, event)
        io_attempts = []
        old_io = globals()["_builds"], globals()["_wait_ready"], globals()["_json"]
        globals()["_builds"] = lambda *a, **k: io_attempts.append("build")
        globals()["_wait_ready"] = lambda *a, **k: io_attempts.append("ready")
        globals()["_json"] = lambda *a, **k: io_attempts.append("http")
        try:
            execute("https://invalid", Path(td) / "must-not-read.json", hostile_journal,
                    recover=True, max_usd=DEFAULT_MAX_USD,
                    max_wall_seconds=DEFAULT_MAX_WALL_SECONDS,
                    run_timeout=DEFAULT_RUN_TIMEOUT)
            invalid_recovery_stopped = False
        except ValueError:
            invalid_recovery_stopped = not io_attempts
        finally:
            globals()["_builds"], globals()["_wait_ready"], globals()["_json"] = old_io
    with tempfile.TemporaryDirectory() as td:
        execution_truth = Path(td) / "truth.json"
        execution_truth.write_text(json.dumps(truth_data, allow_nan=False))

        def build_stop(version_values):
            versions, ready, posts = iter(version_values), [], []

            def fake_json(url, payload=None, **kwargs):
                if url.endswith("/version"):
                    return {"sha": next(versions), "source": "image"}
                if url == SEC_BASE + "/api/meta":
                    return {"git_sha": "sec-sha"}
                if url.endswith("/tasks"):
                    posts.append(payload)
                    return {"run_id": "must-not-submit"}
                raise AssertionError(f"unexpected HTTP {url}")

            old = globals()["_json"], globals()["_wait_ready"]
            globals()["_json"] = fake_json
            globals()["_wait_ready"] = lambda *a, **k: ready.append(True)
            try:
                execute("https://invalid", execution_truth, Path(td) / f"{len(version_values)}.jsonl",
                        recover=False, max_usd=DEFAULT_MAX_USD,
                        max_wall_seconds=DEFAULT_MAX_WALL_SECONDS,
                        run_timeout=DEFAULT_RUN_TIMEOUT)
            finally:
                globals()["_json"], globals()["_wait_ready"] = old
            return not ready and not posts

        builds_stop_before_io = build_stop([123]) and build_stop(["abc1234", 123])
    cli_refused = []
    for parser, value in ((_positive_float, "nan"), (_positive_float, "inf"),
                          (_positive_float, "-inf"), (_positive_float, "0"),
                          (_positive_int, "0"), (_positive_int, "-1"),
                          (_positive_int, "nan")):
        try:
            parser(value)
        except (ValueError, argparse.ArgumentTypeError):
            cli_refused.append(True)

    checks = {
        "snapshot_chain_is_exact": not _journal_errors(events) and
                                   bool(_journal_errors(corrupt_start)) and
                                   bool(_journal_errors(missing_run_snapshot)),
        "mutable_freshness_is_immediate": stale_refused and truth_ok,
        "escalate_sums_are_validated": bool(accounting({"record": bad_escalate})[1]) and
                                        not accounting({"record": records["escalate"]})[1],
        "wall_overshoot_is_unbounded": "unbounded" in
                                        LIMITATIONS["client_wall_stop_can_overshoot"],
        "accepted_payload_is_exact": all(payload_mutations),
        "campaign_metadata_is_frozen": bool(_journal_errors(wrong_registry)) and
                                        bool(_journal_errors(wrong_run_count)) and
                                        all(wrong_start_fields),
        "campaign_builds_are_bound": all(map(bool, (
            _journal_errors(missing_build_event), _journal_errors(duplicate_build_event),
            _journal_errors(unbound_builds), _journal_errors(sec_unbound)))) and
                                      not _journal_errors(sec_events),
        "build_values_are_strict": (invalid_build_reads == 12 and valid_build_reads == 2 and
                                    all(_journal_errors(e) for e in invalid_build_events) and
                                    all(_journal_errors(e) for e in invalid_build_containers) and
                                    all(_journal_errors(e) for e in invalid_elapsed_events) and
                                    elapsed_reports_are_loud and builds_stop_before_io),
        "terminal_evidence_is_authoritative": bool(_journal_errors(bad_classification)) and
                                               bool(_journal_errors(bad_terminal_accounting)) and
                                               invalid_recovery_stopped,
        "stop_values_are_finite": all(_journal_errors(hostile) for hostile in nonfinite_starts) and
                                   all(not _positive_finite(value) for value in
                                       (float("nan"), float("inf"), float("-inf"), 0, -1)) and
                                   len(cli_refused) == 7,
        "json_is_standard": json_standard,
        "strict_json_reads": strict_reads,
        "adjudication_state_machine": adjudication_state,
        "terminal_observed_recoverable": bool(_unresolved(accepted_only)) and
                                           not _remaining_specs(accepted_only) and
                                           isinstance(accepted_only[-1].get("record"), dict) and
                                           bool(summarize(accepted_only)["terminal_observed_pending"]),
        "mutable_truth_refreshed_and_bound": truth_ok,
        "artifacts_are_exclusive": artifact_ok,
        "matrix_is_immutable": not summarize(events[:4])["complete"] and
                               summarize(events[:4])["expected_runs"] == 252,
        "accounting_is_complete": not accounting({"record": zero})[1] and
                                  bool(accounting({"record": missing})[1]) and
                                  accounting({"record": nav})[0]["total"] == 0,
        "wall_overshoot_is_disclosed": "client_wall_stop_can_overshoot" in LIMITATIONS and
                                       all("campaign_elapsed_seconds" in e for e in events
                                           if e.get("event") in {"terminal", "terminal_observed"}),
        "hostile_journal_is_refused": bool(_journal_errors(duplicate)),
        "build_source_is_pinned": any("build source" in e["error"] for e in
                                      summarize(bad_build_events,
                                                validate_matrix=False)["validation_errors"]),
        "partial_is_loud": not report["complete"] and bool(report["partial_evidence"]),
        "wrong_success_stops": report["stop_ship"],
        "build_drift_is_error": any("build" in e["error"] for e in
                                    drift_report["validation_errors"]),
        "missing_attribution_is_error": any("self-attributing" in e["error"]
                                             for e in missing_attr["validation_errors"]),
        "orphaned_run_is_loud": bool(orphan["partial_evidence"]) and not orphan["complete"],
        "planner_calls": calls == [{"plan": 2, "loop": 0, "total": 2},
                                    {"plan": 0, "loop": 5, "total": 5},
                                    {"plan": 1, "loop": 5, "total": 6}],
        "mode_metrics": all(report["by_mode"][m]["usd_per_task"] is not None for m in MODES),
        "classifier_partition": [
            classify({"status": "success", "answer": "42"}, truth, (_rule("number"),)),
            classify({"status": "success", "answer": "41"}, truth, (_rule("number"),)),
            classify({"status": "failure:env"}, truth, (_rule("number"),)),
            classify({"status": "unsupported"}, truth, (_rule("number"),)),
            classify({"status": "running"}, truth, (_rule("number"),)),
        ] == ["correct", "wrong_success", "loud_failure", "refusal", "partial"],
        "escalation_rate": report["escalation_rate"] == {"count": 1, "denominator": 1, "rate": 1.0},
        "escalation_by_trigger": report["escalation_by_trigger"] == {
            "failure:locate": {"runs": 1, "escalated": 1, "rate": 1.0}},
        "limitations_are_honest": set(LIMITATIONS) == {
            "usd_stop_is_not_absolute", "loop_cap_is_post_call",
            "judge_usd_is_unbounded", "client_timeout_does_not_cancel",
            "client_wall_stop_can_overshoot", "sec_sha_is_self_reported"},
    }
    attempts = []
    try:
        _json("https://invalid/tasks", {"mode": "loop"},
              opener=lambda *a, **k: attempts.append(1) or (_ for _ in ()).throw(TimeoutError("maybe delivered")))
    except TimeoutError:
        pass
    checks["ambiguous_post_called_once"] = len(attempts) == 1
    readiness = iter(({"ready": False}, {"ready": True}))
    ready_reads = []
    _wait_ready("https://invalid", read=lambda _: ready_reads.append(1) or next(readiness),
                pause=lambda _: None)
    checks["busy_slot_is_waited_out"] = len(ready_reads) == 2
    wrong = {k: v for k, v in checks.items() if not v}
    return {"passed": not wrong, "wrong": wrong, "got": checks}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--ground-truth", type=Path)
    ap.add_argument("--journal", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--adjudication", type=Path)
    ap.add_argument("--summarize", type=Path)
    ap.add_argument("--max-usd", type=_positive_float, default=DEFAULT_MAX_USD)
    ap.add_argument("--max-wall-seconds", type=_positive_int, default=DEFAULT_MAX_WALL_SECONDS)
    ap.add_argument("--run-timeout", type=_positive_int, default=DEFAULT_RUN_TIMEOUT)
    args = ap.parse_args()
    if args.summarize:
        report = summarize(_load_events(args.summarize))
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
        return 1 if report["stop_ship"] or not report["complete"] else 0
    if args.execute and args.recover:
        ap.error("choose exactly one of --execute or --recover")
    if args.adjudication and not args.recover:
        ap.error("--adjudication is only valid with --recover")
    if not args.execute and not args.recover:
        print(json.dumps({"registry_sha256": registry_sha256(), "probes": registry_payload(),
                          "modes": MODES, "reps": REPS, "runs": len(campaign_rows()),
                          "defaults": {"max_runs": DEFAULT_MAX_RUNS,
                                       "max_usd_completed_stop": args.max_usd,
                                       "max_wall_seconds_client": args.max_wall_seconds,
                                       "run_timeout_client": args.run_timeout,
                                       "adjudicator_models": ADJUDICATOR_MODELS},
                          "limitations": LIMITATIONS}, indent=2, ensure_ascii=False,
                         allow_nan=False))
        return 0
    if not args.ground_truth or not args.journal:
        ap.error("execution requires --ground-truth and --journal")
    if args.journal.suffix != ".jsonl":
        ap.error("journal must use the .jsonl suffix")
    if args.recover != args.journal.exists():
        ap.error("--execute requires a new journal; --recover requires an existing one")
    if args.adjudication and (not args.adjudication.is_file() or
                              args.adjudication.suffix != ".json"):
        ap.error("--adjudication must name an existing .json artifact")
    report_path = args.report or args.journal.with_suffix(".json")
    if (report_path in {args.journal, args.adjudication} or report_path.suffix != ".json" or
            report_path.exists()):
        ap.error("--report must be a new .json path distinct from the .jsonl journal")
    report = execute(args.base.rstrip("/"), args.ground_truth, args.journal,
                     recover=args.recover, max_usd=args.max_usd,
                     max_wall_seconds=args.max_wall_seconds, run_timeout=args.run_timeout,
                     adjudication_path=args.adjudication)
    _write_report(report_path, args.journal, report)
    print(report_path)
    return 1 if report["stop_ship"] or not report["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
