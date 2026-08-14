#!/usr/bin/env python3
"""SessionEnd hook: dump this session's user prompts to prompts/raw/.

Raw material for the curated prompts/ record — noise gets deleted by hand,
the Assumption -> Eval contradiction -> Correction chain gets written by hand.
"""
import json
import os
import sys
import time
from pathlib import Path


def text_of(message):
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def main():
    payload = json.load(sys.stdin)
    transcript = payload.get("transcript_path", "")
    session = payload.get("session_id", "unknown")[:8]
    if not transcript or not os.path.exists(transcript):
        return
    prompts = []
    with open(transcript) as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "user" or entry.get("isMeta"):
                continue
            text = text_of(entry.get("message", {})).strip()
            # skip tool results / empty / slash-command noise
            if text and not text.startswith("<"):
                prompts.append(text)
    if not prompts:
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    out = root / "prompts" / "raw" / f"{time.strftime('%Y-%m-%d')}-{session}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n---\n\n".join(prompts)
    out.write_text(f"# Session {session} — {time.strftime('%Y-%m-%d %H:%M')}\n\n{body}\n")


if __name__ == "__main__":
    main()
