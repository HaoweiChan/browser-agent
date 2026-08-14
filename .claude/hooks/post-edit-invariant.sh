#!/bin/bash
# PostToolUse hook: after any Edit/Write under src/, run the invariant suite.
# Exit 2 feeds the failure back to Claude so it fixes it immediately.
input=$(cat)
file=$(printf '%s' "$input" | python3 -c \
  "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$file" in
  */src/*) ;;
  *) exit 0 ;;
esac
cd "$CLAUDE_PROJECT_DIR" || exit 0
[ -f evals/run.py ] || exit 0  # project removed the eval harness — nothing to enforce
out=$(python3 -m evals.run --suite invariant --no-report 2>&1)
status=$?
if [ $status -ne 0 ]; then
  echo "Invariant suite failed after editing $file:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
