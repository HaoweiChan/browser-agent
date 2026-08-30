"""CLI entry: python3 -m src.browser.cli "task" [--url ...] [--model ...]

Uses the live OpenRouter planner (needs OPENROUTER_API_KEY in the shell env —
no .env files, CLAUDE.md rule 8). Writes trace + screenshots to runs/<ts>/.
"""

import argparse
import asyncio
import json
import time

from .agent import run_task
from .judge import live_judge
from .planner import DEFAULT_MODEL
from .model_policy import canonical_live_planner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--url", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--allow-llm", action="store_true",
                    help="explicitly allow this trusted local CLI process to use its LLM environment")
    args = ap.parse_args()

    run_dir = f"runs/{time.strftime('%Y%m%d-%H%M%S')}"
    planner = canonical_live_planner(verified_access=args.allow_llm,
                                     model=args.model or DEFAULT_MODEL,
                                     fallback=args.model is None)
    result = asyncio.run(
        run_task(args.task, args.url, planner, run_dir,
                 judge=live_judge(), headless=not args.headed,
                 model=args.model or DEFAULT_MODEL, mode="canonical",
                 verified_access=args.allow_llm)
    )
    served = [call["served_model"] for call in result.get("control_flow", {}).get("node_calls", [])
              if call.get("node") == "plan" and isinstance(call.get("served_model"), str)]
    if served:
        result["model"] = " + ".join(dict.fromkeys(served))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n[trace] {run_dir}/trace.jsonl")


if __name__ == "__main__":
    main()
