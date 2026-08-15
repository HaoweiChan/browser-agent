"""CLI entry: python3 -m src.browser.cli "task" [--url ...] [--model ...]

Uses the live OpenRouter planner (needs OPENROUTER_API_KEY in the shell env —
no .env files, CLAUDE.md rule 8). Writes trace + screenshots to runs/<ts>/.
"""

import argparse
import asyncio
import json
import time

from .agent import run_task
from .planner import DEFAULT_MODEL, live_planner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--url", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    run_dir = f"runs/{time.strftime('%Y%m%d-%H%M%S')}"
    result = asyncio.run(
        run_task(args.task, args.url, live_planner(args.model), run_dir, headless=not args.headed)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n[trace] {run_dir}/trace.jsonl")


if __name__ == "__main__":
    main()
