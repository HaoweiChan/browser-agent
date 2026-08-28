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
# T-M39-15-D4: shared with `.githooks/pre-commit`. This hook passes
# --no-report so it cannot manufacture an artifact, but a depsless python3
# still hands the agent dozens of ModuleNotFoundError reds as if the edit had
# broken something — a non-measurement dressed as a verdict.
. "$CLAUDE_PROJECT_DIR/.githooks/lib-interpreter.sh"
# Called plainly, NOT as `msg=$(...)`: command substitution runs the function
# in a subshell, so the PY it resolves would be discarded and line below would
# run an unset interpreter — the same class of silent degradation this whole
# block exists to remove.
if ! eval_hook_interpreter >&2; then
  echo "Invariant suite could NOT run after editing $file — that is not a" >&2
  echo "test failure, and nothing about the suites is known." >&2
  exit 2
fi
out=$("$PY" -m evals.run --suite invariant --no-report 2>&1)
status=$?
if [ $status -ne 0 ]; then
  echo "Invariant suite failed after editing $file:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
