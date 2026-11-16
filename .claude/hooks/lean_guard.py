#!/usr/bin/env python3
"""PreToolUse guard for lean mode: stops the commands that flood a small context, and tells the
model the cheaper way. Installed by `scripts/lean_mode.py on`; removed by `off`. stdlib only.

Blocks (each with a reason the model sees, so it retries the cheap way):
  Read   a text file over LEAN_GUARD_MAX_BYTES (default 12000 ≈ 3k tokens) with no `limit`
         — passing an explicit `limit` (or `pages`) is the deliberate way through.
  Bash   cat / type / Get-Content / more / less of such a file without a pipe; `ls -R`, `tree`.
  Write  over an existing file that big — use Edit for the lines that change.
Never blocks anything else; on any error it allows the call (exit 0, no output).
"""
import json
import os
import re
import shlex
import sys

MAX = int(os.environ.get("LEAN_GUARD_MAX_BYTES", "12000"))
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ipynb", ".wav", ".mp3", ".zip"}
DUMP = re.compile(r"^\s*(cat|type|Get-Content|gc|more|less|bat)\s+(.+)$", re.IGNORECASE)
TREE = re.compile(r"(^|[;&|]\s*)(ls\s+(-\w*R\w*|--recursive)\b|tree\b|Get-ChildItem\b.*-Recurse)", re.IGNORECASE)


def size(path: str, cwd: str) -> int:
    p = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        return os.path.getsize(p) if os.path.isfile(p) else -1
    except OSError:
        return -1


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "[lean mode] " + reason}}))


def check(ev: dict) -> str | None:
    name, inp = ev.get("tool_name"), ev.get("tool_input") or {}
    cwd = ev.get("cwd") or os.getcwd()
    if name == "Read":
        fp = inp.get("file_path", "")
        if inp.get("limit") or inp.get("pages") or os.path.splitext(fp)[1].lower() in BINARY:
            return None
        n = size(fp, cwd)
        if n > MAX:
            return (f"{os.path.basename(fp)} is {n // 1024} KB (≈{n / 4000:.1f}k tokens). Don't read it whole: "
                    "use `python3 scripts/gtd_query.py …`, Grep -n for the part you need, or Read with "
                    "offset/limit (e.g. limit 150). If you truly need all of it, pass an explicit limit.")
    elif name == "Bash":
        cmd = inp.get("command", "")
        if TREE.search(cmd):
            return ("Recursive listings flood the context. Use Glob with a narrow pattern, "
                    "`ls` of one folder, or `python3 scripts/gtd_query.py` (projects/inbox/meetings).")
        m = DUMP.match(cmd)
        if m and "|" not in cmd:
            try:
                args = shlex.split(m.group(2), posix=True)
            except ValueError:
                args = m.group(2).split()
            for a in args:
                if a.startswith("-"):
                    continue
                n = size(a, cwd)
                if n > MAX:
                    return (f"{a} is {n // 1024} KB. Don't print it whole: pipe through head/tail, "
                            "use Grep -n, or Read with offset/limit.")
    elif name == "Write":
        fp = inp.get("file_path", "")
        n = size(fp, cwd)
        if n > MAX:
            return (f"{os.path.basename(fp)} already exists ({n // 1024} KB). Rewriting it puts the whole "
                    "file into the conversation. Use Edit for the lines that change.")
    return None


def main() -> int:
    try:
        reason = check(json.load(sys.stdin))
    except Exception:
        return 0
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
