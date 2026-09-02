---
id: DRAFT-99
title: Borrowed-browser context leak on a failed new_page
status: Draft
assignee: []
created_date: '2026-09-02 17:45'
labels:
  - debt
dependencies: []
references:
  - TODO.md T-R5
  - 'PR #20 R5 (LOW'
  - routed debt — unreachable from any committed case)
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`src/browser/agent.py:311-312` creates the `BrowserContext` and its page before the `try:` whose `finally: await ctx.close()` is the only close, so a failure inside `ctx.new_page()` leaks that context for the life of the eval process. The own-browser path is swept by the exit stack; the borrowed path has no `stack.push_async_callback(browser.close)` to fall back on. Not reachable from a committed case — a full `fast` run in reverse case order leaves `len(_BROWSER.contexts) == 0` — and reachable only by making `ctx.new_page()` raise on the shared path. Acceptance: `ctx` created inside the exit stack (`stack.push_async_callback(ctx.close)`) or inside the `try`, so both paths close it on any failure, with a case that leaks before the fix.

Probe: none — migrated from TODO.md
<!-- SECTION:DESCRIPTION:END -->
