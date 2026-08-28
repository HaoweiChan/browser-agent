#!/bin/sh
# Shared interpreter resolution for both gate scripts (T-M39-15-D4).
#
# Both used to carry the IDENTICAL line
#   PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
# and a fresh `git worktree` copies no `.venv`, so both degraded to a system
# python without the task deps. That does not produce a worse measurement, it
# produces a NON-measurement: dozens of cases go red on ModuleNotFoundError,
# and the pre-commit hook then WRITES A REPORT for the red run, so a
# non-measurement lands in the ledger with an artifact asserting it happened.
# Hard rule 4 in the red direction. Four incidents on 2026-08-28 alone, the
# last of them this file's own author committing through main's copy of the
# hook and being told "REGRESSION: 0.221 < baseline 1.000" on a tree that
# measured 258/258 -- with `--update-baseline` offered as the remedy, which is
# the one thing CLAUDE.md rule 1 forbids.
#
# Sets PY, or returns non-zero having printed why. Sourced, not executed, so
# the caller decides what a failure means (exit 1 for a commit, exit 2 to hand
# the message back to the agent).
#
# `EVAL_HOOK_PY` is a test seam, not an operator knob:
# `pre-commit-reports-a-broken-interpreter-as-such` points it at an interpreter
# that can import nothing, which is the only way to exercise the message
# without breaking the developer's own environment to do it.
eval_hook_interpreter() {
  PY=${EVAL_HOOK_PY:-python3}
  if [ -z "$EVAL_HOOK_PY" ]; then
    # `.venv` here first; then the MAIN worktree's, because a worktree copies
    # no `.venv` and the one thing it does know is where the shared `.git`
    # lives -- `--git-common-dir`, whose parent is the main working tree.
    COMMON=$(git rev-parse --git-common-dir 2>/dev/null)
    for cand in .venv/bin/python "$(dirname "$COMMON")/.venv/bin/python"; do
      [ -x "$cand" ] && { PY=$cand; break; }
    done
  fi
  "$PY" -c 'import fastapi, playwright, uvicorn' 2>/dev/null && return 0
  echo "This is an ENVIRONMENT problem, not an eval regression."
  echo "  interpreter: $PY"
  "$PY" -c 'import fastapi, playwright, uvicorn' 2>&1 | tail -1 | sed 's/^/  /'
  echo "The eval gate never ran, so nothing is known about the suites — do NOT"
  echo "move the baseline. In a git worktree the usual cause is that no .venv"
  echo "was found here or in the main checkout; point PY at one that has the"
  echo "task deps (a symlink to the main checkout's .venv is enough)."
  return 1
}
