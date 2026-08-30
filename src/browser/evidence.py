"""Deterministic, site-agnostic evidence extraction for the canonical graph.

This module only turns already-acquired bytes into cited evidence. It does not
fetch pages, use models, or encode a site's DOM path.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlsplit

from .canonical_contract import canonical_text


_PERCENT = re.compile(r"\b\d+(?:\.\d+)?%")
_DATE_WORDS = re.compile(
    r"\b(?:effective\s+from\s+)?\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    re.I,
)
_TERMINAL = re.compile(r"\b(success|complete|error|failed)\b", re.I)
_NON_RENDERED = {"head", "title", "script", "style", "template"}


def _text(value: str) -> str:
    return " ".join(value.split())


@dataclass
class _Element:
    tag: str
    attrs: dict[str, str]
    children: list["_Element"] = field(default_factory=list)
    data: list[str] = field(default_factory=list)


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Element(tag.lower(), {key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(_Element(tag.lower(), {key.lower(): value or "" for key, value in attrs}))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].data.append(data)


def _parse(source: bytes) -> _Element:
    parser = _Tree()
    parser.feed(source.decode("utf-8"))
    parser.close()
    return parser.root


def _walk(node: _Element):
    for child in node.children:
        yield child
        yield from _walk(child)


def _hidden(node: _Element) -> bool:
    style = node.attrs.get("style", "")
    return (node.tag in _NON_RENDERED or "hidden" in node.attrs
            or node.attrs.get("aria-hidden", "").lower() == "true"
            or bool(re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", style, re.I)))


def _visible_walk(node: _Element):
    for child in node.children:
        if _hidden(child):
            continue
        yield child
        yield from _visible_walk(child)


def _node_text(node: _Element) -> str:
    if _hidden(node):
        return ""
    parts = list(node.data)
    for child in node.children:
        if not _hidden(child):
            parts.append(_node_text(child))
    return _text(" ".join(parts))


def _accessible_text(node: _Element) -> str:
    """Prefer an explicit accessible name, otherwise deterministic DOM text."""
    return _text(node.attrs.get("aria-label") or node.attrs.get("alt") or _node_text(node))


def _offset_item(value: str, text: str, start: int) -> tuple[dict, int]:
    offset = text.find(value, start)
    if offset < 0:
        raise ValueError(f"evidence value absent from canonical text: {value!r}")
    return {"kind": "text", "value": value,
            "text_offset": {"start": offset, "end": offset + len(value)}}, offset + len(value)


def _leaf_texts(root: _Element) -> list[str]:
    values = []
    for node in _visible_walk(root):
        if node.children:
            continue
        value = _accessible_text(node)
        if value:
            values.append(value)
    return values


def _dated_text_items(root: _Element, text: str) -> list[dict]:
    values = []
    for value in _leaf_texts(root):
        if _PERCENT.search(value) or _DATE_WORDS.search(value):
            values.append(value)
    items, start = [], 0
    for value in values:
        item, start = _offset_item(value, text, start)
        items.append(item)
    return items


def _chart_text_items(root: _Element, text: str) -> list[dict]:
    labels, values = [], []
    for node in _visible_walk(root):
        if node.children:
            continue
        value = _accessible_text(node)
        if not value:
            continue
        if node.tag in ("figcaption", "caption", "legend"):
            labels.append(value)
        if _PERCENT.search(value):
            values.append(value)
    selected = labels[:1] + values[:1]
    items, start = [], 0
    for value in selected:
        item, start = _offset_item(value, text, start)
        items.append(item)
    return items


def _row_cells(row: _Element) -> list[tuple[str, str]]:
    return [(cell.tag, _node_text(cell)) for cell in row.children
            if cell.tag in ("th", "td") and not _hidden(cell)]


def _semantic_tables(root: _Element) -> list[tuple[str, list[str], list[list[str]]]]:
    tables = []
    for table in (node for node in _visible_walk(root) if node.tag == "table"):
        rows = [_row_cells(row) for row in _visible_walk(table) if row.tag == "tr"]
        header_index = next((index for index, row in enumerate(rows) if row and any(tag == "th" for tag, _ in row)), None)
        if header_index is None:
            continue
        headers = [value for _, value in rows[header_index]]
        data = [[value for _, value in row] for row in rows[header_index + 1:] if any(tag == "td" for tag, _ in row)]
        if headers and data:
            caption = next((_node_text(node) for node in _visible_walk(table) if node.tag == "caption"), "")
            tables.append((caption, headers, data))
    return tables


def _date_in(value: str) -> date | None:
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group())
    except ValueError:
        return None


def _question_tokens(question: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    if "year" in tokens:
        tokens.add("yr")
    if "yr" in tokens:
        tokens.add("year")
    return tokens


def _table_item(root: _Element, question: str) -> list[dict]:
    tables = _semantic_tables(root)
    if not tables:
        return []
    question_tokens = _question_tokens(question)
    def relevance(table: tuple[str, list[str], list[list[str]]]) -> tuple[int, int]:
        caption, headers, _ = table
        terms = _question_tokens(" ".join((caption, *headers)))
        numeric = sum(bool(set(re.findall(r"\d+", header)) & question_tokens) for header in headers)
        return len(terms & question_tokens) + numeric, numeric

    _, headers, rows = max(tables, key=relevance)
    scores = [len(_question_tokens(header) & question_tokens) for header in headers]
    numeric_matches = [index for index, header in enumerate(headers)
                       if set(re.findall(r"\d+", header)) & question_tokens]
    column = numeric_matches[0] if numeric_matches else max(range(len(headers)), key=lambda index: (scores[index], index))
    dated = [(max((found for found in (_date_in(cell) for cell in row) if found), default=None), index)
             for index, row in enumerate(rows)]
    row = max(dated, key=lambda item: (item[0] is not None, item[0] or date.min, -item[1]))[1]
    return [{"kind": "table", "value": rows[row][column],
             "table_cell": {"headers": headers, "row": row, "column": column}}]


def _live_region_items(root: _Element) -> list[dict]:
    regions = [_accessible_text(node) for node in _visible_walk(root) if "aria-live" in node.attrs]
    regions = [value for value in regions if value]
    if not regions:
        return []
    terminal = [(value, _TERMINAL.search(value)) for value in regions]
    value, match = next(((value, match) for value, match in reversed(terminal) if match), terminal[-1])
    return [{"kind": "live_region", "value": value,
             "live_state": match.group(1).lower() if match else "running"}]


def extract_evidence(*, source_bytes: bytes, url: str, document_id: str, request: dict) -> dict:
    """Return cited evidence for an acquired document; callers own acquisition."""
    text = canonical_text(source_bytes)
    root = _parse(source_bytes)
    capability = request.get("capability") if isinstance(request, dict) else ""
    question = request.get("question", "") if isinstance(request, dict) else ""
    if capability == "terminal-live-region":
        items = _live_region_items(root)
    elif capability == "dated-text-evidence":
        items = _dated_text_items(root, text)
    elif capability == "chart-context-text-evidence":
        items = _chart_text_items(root, text)
    elif capability in ("temporal-effective-date", "latest-dated-table-cell", "semantic-table-normalization"):
        items = _table_item(root, question)
    else:
        raise ValueError(f"unsupported evidence capability: {capability!r}")
    return {"document_id": document_id, "url": url,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "snapshot_sha256": hashlib.sha256(text.encode()).hexdigest(), "items": items}


def snapshot_evidence(*, source_bytes: bytes, url: str, document_id: str) -> dict:
    """Cite the first offset-bound visible text from already-acquired page bytes."""
    text = canonical_text(source_bytes)
    if not text:
        raise ValueError("empty canonical snapshot text")
    value = ""
    offset = -1
    for node in _visible_walk(_parse(source_bytes)):
        if node.children:
            continue
        candidate = _node_text(node)[:1_500]
        if candidate and (found := text.find(candidate)) >= 0:
            value, offset = candidate, found
            break
    if not value:
        raise ValueError("no visible offset-bound snapshot text")
    return {"document_id": document_id, "url": url,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "snapshot_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "items": [{"kind": "text", "value": value,
                       "text_offset": {"start": offset, "end": offset + len(value)}}]}


def read_same_origin_export(*, page_url: str, export_url: str,
                            fetch: Callable[[str], bytes]) -> dict:
    """Read an injected HTTP(S) CSV/XML export only when it is same-origin."""
    resolved_url = urljoin(page_url, export_url)
    page, export = urlsplit(page_url), urlsplit(resolved_url)

    def origin(parts):
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        try:
            port = parts.port
        except ValueError:
            return None
        return parts.scheme.lower(), parts.hostname.lower(), port or {"http": 80, "https": 443}[parts.scheme.lower()]

    if origin(page) is None or origin(page) != origin(export):
        raise ValueError("export must be same-origin http(s)")
    if export.path.lower().endswith(".csv"):
        body = fetch(resolved_url).decode("utf-8")
        rows = [[_text(value) for value in row] for row in csv.reader(io.StringIO(body)) if any(_text(value) for value in row)]
        if not rows:
            raise ValueError("empty csv export")
        return {"headers": rows[0], "rows": rows[1:]}
    if export.path.lower().endswith(".xml"):
        body = fetch(resolved_url).decode("utf-8")
        root = ET.fromstring(body)
        records = [list(row) for row in list(root) if list(row)]
        if not records:
            raise ValueError("empty xml export")
        headers = [child.tag.rsplit("}", 1)[-1] for child in records[0]]
        return {"headers": headers,
                "rows": [[_text(next((child.text or "" for child in row if child.tag.rsplit("}", 1)[-1] == header), ""))
                          for header in headers] for row in records]}
    raise ValueError("unsupported export format")
