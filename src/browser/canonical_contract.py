"""Pure contracts for the future canonical browser-agent graph (ADR-046).

This module validates envelopes only. M49 supplies evidence extraction and M50
supplies graph execution; neither behaviour belongs here.
"""

from __future__ import annotations

import math
import re
from html.parser import HTMLParser


NODES = ("observe", "route", "evidence", "plan", "act", "evaluate", "decide")
ROUTES = ("route", "evidence", "plan", "act", "evaluate", "decide", "publish", "review_required", "failure")
STATUSES = ("running", "accepted", "retryable", "review_required", "failure:env",
            "failure:locate", "failure:act", "failure:extract", "failure:semantic",
            "failure:task", "failure:nav")
EVIDENCE_KINDS = ("text", "table", "live_region", "export", "vision")
TERMINAL_LIVE_STATES = ("complete", "success", "error", "failed")
VERDICTS = ("PENDING", "PASS", "FAIL")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_NEXT_ROUTE = {
    "observe": "route", "route": "evidence", "evidence": "plan",
    "plan": "act", "act": "evaluate", "evaluate": "decide",
}


class _CanonicalText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def canonical_text(source: bytes) -> str:
    """UTF-8 HTML text nodes, document order, collapsed to one-space joins."""
    parser = _CanonicalText()
    parser.feed(source.decode("utf-8"))
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _nonnegative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_evidence_packet(packet: dict) -> list[str]:
    """Return contract violations; no page parsing, network, or model work."""
    if not isinstance(packet, dict):
        return ["invalid:packet"]
    wrong = []
    for key in ("document_id", "url"):
        if not isinstance(packet.get(key), str) or not packet[key]:
            wrong.append(f"missing:{key}")
    for key in ("snapshot_sha256", "source_sha256"):
        if not _is_hash(packet.get(key)):
            wrong.append(f"invalid:{key}")
    items = packet.get("items")
    if not isinstance(items, list) or not items:
        return wrong + ["missing:items"]
    for i, item in enumerate(items):
        prefix = f"items[{i}]"
        if not isinstance(item, dict) or item.get("kind") not in EVIDENCE_KINDS:
            wrong.append(f"invalid:{prefix}.kind")
            continue
        if not isinstance(item.get("value"), str) or not item["value"]:
            wrong.append(f"missing:{prefix}.value")
        if item["kind"] == "text":
            offset = item.get("text_offset")
            if not (isinstance(offset, dict) and _nonnegative_int(offset.get("start"))
                    and _nonnegative_int(offset.get("end")) and offset["start"] < offset["end"]):
                wrong.append(f"invalid:{prefix}.text_offset")
        if item["kind"] == "table":
            cell = item.get("table_cell")
            if not (isinstance(cell, dict) and isinstance(cell.get("headers"), list)
                    and all(isinstance(h, str) and h for h in cell["headers"])
                    and _nonnegative_int(cell.get("row")) and _nonnegative_int(cell.get("column"))):
                wrong.append(f"invalid:{prefix}.table_cell")
        if item["kind"] == "live_region":
            state = item.get("live_state")
            if state not in ("running", *TERMINAL_LIVE_STATES):
                wrong.append(f"invalid:{prefix}.live_state")
    return wrong


def validate_state(state: dict) -> list[str]:
    """Validate graph routing, retry, budget, and evidence-envelope invariants."""
    if not isinstance(state, dict):
        return ["invalid:state"]
    wrong = []
    if state.get("node") not in NODES:
        wrong.append("invalid:node")
    if state.get("route") not in ROUTES:
        wrong.append("invalid:route")
    if state.get("status") not in STATUSES:
        wrong.append("invalid:status")
    retry = state.get("retry")
    if not (isinstance(retry, dict) and _nonnegative_int(retry.get("used"))
            and _nonnegative_int(retry.get("limit")) and retry["used"] <= retry["limit"]):
        wrong.append("invalid:retry")
    budgets = state.get("budgets")
    if not (isinstance(budgets, dict) and _nonnegative_int(budgets.get("calls"))
            and _nonnegative_int(budgets.get("tokens"))
            and _nonnegative_number(budgets.get("usd"))
            and _nonnegative_number(budgets.get("ms"))):
        wrong.append("invalid:budgets")
    packets = state.get("evidence", [])
    if not isinstance(packets, list):
        wrong.append("invalid:evidence")
        packets = []
    for packet in packets:
        wrong.extend(f"evidence.{value}" for value in validate_evidence_packet(packet))
    node, route, status = state.get("node"), state.get("route"), state.get("status")
    verifier = state.get("verifier")
    if not (isinstance(verifier, dict) and verifier.get("authority") == "deterministic"
            and verifier.get("verdict") in VERDICTS):
        wrong.append("invalid:verifier")
    deterministic_pass = verifier == {"authority": "deterministic", "verdict": "PASS"}
    deterministic_fail = verifier == {"authority": "deterministic", "verdict": "FAIL"}
    if node in _NEXT_ROUTE:
        if route != _NEXT_ROUTE[node]:
            wrong.append("invalid:transition")
        if status != "running":
            wrong.append("invalid:intermediate-status")
        if verifier != {"authority": "deterministic", "verdict": "PENDING"}:
            wrong.append("invalid:intermediate-verifier")
    if node == "decide":
        if route == "publish":
            if status != "accepted" or not deterministic_pass:
                wrong.append("invalid:publish-authority")
        elif route == "plan":
            if status != "retryable" or not deterministic_fail or not (
                    isinstance(retry, dict) and retry.get("used", 0) < retry.get("limit", 0)):
                wrong.append("invalid:retry")
        elif route == "review_required":
            if status != "review_required" or not deterministic_fail:
                wrong.append("invalid:review")
        elif route == "failure":
            if not (isinstance(status, str) and status.startswith("failure:") and deterministic_fail):
                wrong.append("invalid:failure")
        else:
            wrong.append("invalid:decide-route")
    elif route in ("publish", "review_required"):
        wrong.append("invalid:terminal-route")
    return wrong


def budget_stop_before_next_run(spent: dict, limits: dict) -> str | None:
    """Generic aggregate stop line, deliberately post-completed-run not absolute."""
    if not isinstance(spent, dict):
        return "invalid spent accounting"
    if not isinstance(limits, dict):
        return "invalid budget limits"
    keys = ("calls", "tokens", "usd", "ms")
    if (not _nonnegative_int(spent.get("calls")) or not _nonnegative_int(spent.get("tokens"))
            or any(not _nonnegative_number(spent.get(key)) for key in ("usd", "ms"))):
        return "invalid spent accounting"
    if (not isinstance(limits.get("calls"), int) or isinstance(limits.get("calls"), bool)
            or limits["calls"] <= 0 or not isinstance(limits.get("tokens"), int)
            or isinstance(limits.get("tokens"), bool) or limits["tokens"] <= 0
            or any(not _nonnegative_number(limits.get(key)) or limits[key] <= 0 for key in ("usd", "ms"))):
        return "invalid budget limits"
    reached = [key for key in keys if spent[key] >= limits[key]]
    return f"budget exhausted: {', '.join(reached)}" if reached else None
