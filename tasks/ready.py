#!/usr/bin/env python3
"""List pr-loop tasks that are ready to run (status todo, all Depends done).

Usage: python3 tasks/ready.py [--selftest]

ponytail: line-regex parser over the block format the pr-loop skill defines,
not a markdown parser — upgrade only if the format ever outgrows it.
"""
import pathlib
import re
import sys

TODO = pathlib.Path(__file__).parent / "TODO.md"
HEAD = re.compile(r"^#{2,3}\s+([A-Z]+\d+)\s+—.*\[status:\s*([a-z-]+)\]")
DEPS = re.compile(r"^Depends:\s*(.+)")


def parse(text):
    tasks, cur, section = {}, None, ""
    for line in text.splitlines():
        if line.startswith("## "):
            section, cur = line[3:].strip().lower(), None
        elif m := HEAD.match(line):
            cur = m.group(1)
            tasks[cur] = {"status": m.group(2), "deps": [], "section": section}
        elif cur and (m := DEPS.match(line)):
            tasks[cur]["deps"] = re.findall(r"[A-Z]+\d+", m.group(1))
    return tasks


def main():
    tasks = parse(TODO.read_text())
    if not tasks:
        print("no tasks found in tasks/TODO.md")
        return
    for tid, t in tasks.items():
        # ponytail: only Queue blocks are candidates — Debt is parked by definition
        if t["status"] != "todo" or t["section"] != "queue":
            continue
        missing = [d for d in t["deps"] if tasks.get(d, {}).get("status") != "done"]
        if missing:
            print(f"blocked {tid}  needs {', '.join(missing)}")
        else:
            print(f"ready   {tid}")


def selftest():
    t = parse(
        "## Queue\n"
        "### T1 — a [status: done]\n"
        "### T2 — b [status: todo]\nDepends: T1\n"
        "### T3 — c [status: todo]\nDepends: T2, T9\n"
        "### T4 — d [status: in-progress]\n"
        "### M8 — e [status: todo]\nDepends: T1\n"
    )
    assert t["T1"]["status"] == "done" and t["T2"]["deps"] == ["T1"]
    assert [d for d in t["T2"]["deps"] if t.get(d, {}).get("status") != "done"] == []
    assert [d for d in t["T3"]["deps"] if t.get(d, {}).get("status") != "done"] == ["T2", "T9"]
    assert t["T4"]["status"] == "in-progress"
    assert t["M8"]["deps"] == ["T1"]
    t2 = parse("## Queue\n### T1 — a [status: todo]\n## Debt\n### T2 — b [status: todo]\n")
    assert t2["T1"]["section"] == "queue" and t2["T2"]["section"] == "debt"
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
