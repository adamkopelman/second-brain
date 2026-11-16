#!/usr/bin/env python3
"""Lean mode: make the vault cheap to run on small-context / light LLMs (DeepSeek Flash, Haiku-class,
local models). Reversible and idempotent. stdlib only.

    python scripts/lean_mode.py status
    python scripts/lean_mode.py on  [--keep-outlook]
    python scripts/lean_mode.py off

`on` does five things (each reversible):
  1. Parks the 14 vendored *developer* skills (Superpowers: brainstorming, TDD, writing-skills, …)
     in `.claude/skills-dev/`. Their descriptions load into EVERY session and `using-superpowers`
     tells the model to open skills before any reply. The GTD skills stay. In a git checkout the
     parked files are marked skip-worktree, so `git status` stays clean.
  2. Installs the guard hook (`.claude/hooks/lean_guard.py`): blocks whole-file reads, dumps and
     rewrites of big files and points the model at the cheap route. Skip with --no-guard.
  3. Selects the `GTD Lean` output style: short replies, no narration, no echoing tool output, and
     it drops Claude Code's software-engineering instructions from the system prompt. --no-style.
  4. Writes `.claude/settings.local.json` (per-machine): deny Read on folders GTD work never needs,
     caps on Bash / MCP output, and CLAUDE_CODE_MAX_OUTPUT_TOKENS=12000 — for a model ID Claude
     Code doesn't know it reserves 32k of the window for output by default.
     --context N also sets CLAUDE_CODE_MAX_CONTEXT_TOKENS=N (your model's real window, e.g. 256000).
     --no-thinking sets MAX_THINKING_TOKENS=0 (try it if context_report.py shows thinking is big).
  5. Disables the Outlook MCP server unless --keep-outlook.
`off` undoes exactly what `on` recorded in `.claude/lean-mode.json`. Running `on` again with other
flags adds to what is already on.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_SKILLS = [
    "brainstorming", "dispatching-parallel-agents", "executing-plans",
    "finishing-a-development-branch", "receiving-code-review", "requesting-code-review",
    "subagent-driven-development", "systematic-debugging", "test-driven-development",
    "using-git-worktrees", "using-superpowers", "verification-before-completion",
    "writing-plans", "writing-skills",
]
DENY = [
    "Read(./vendor/**)", "Read(./.obsidian/plugins/**)", "Read(./docs/superpowers/**)",
    "Read(./scripts/dashboard_static/**)", "Read(./scripts/quick_capture/**)",
    "Read(./Meetings/recordings/**)", "Read(./dashboard.html)", "Read(./.git/**)",
]
ENV = {"BASH_MAX_OUTPUT_LENGTH": "12000", "MAX_MCP_OUTPUT_TOKENS": "6000",
       "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "12000"}
STYLE = "GTD Lean"
GUARD_CMD = '"$CLAUDE_PROJECT_DIR/.claude/hooks/lean_guard.sh"'
GUARD = {"matcher": "Read|Bash|Write", "hooks": [{"type": "command", "command": GUARD_CMD}]}


def paths(root: Path):
    c = root / ".claude"
    return c / "skills", c / "skills-dev", c / "settings.local.json", c / "lean-mode.json"


def load(p: Path) -> dict:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            sys.exit(f"{p} is not valid JSON — fix it first")
    return {}


def save(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def git_files(root: Path, rel: str) -> list[str]:
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", rel],
                           capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [f for f in r.stdout.split("\0") if f]


def skip_worktree(root: Path, files: list[str], on: bool) -> None:
    if not files:
        return
    flag = "--skip-worktree" if on else "--no-skip-worktree"
    for i in range(0, len(files), 200):
        subprocess.run(["git", "-C", str(root), "update-index", flag, "--", *files[i:i + 200]],
                       capture_output=True)


def cmd_on(root: Path, opts: dict) -> None:
    skills, parked, local, state_p = paths(root)
    state = load(state_p)
    moved = state.get("parked_skills", [])
    for name in DEV_SKILLS:
        src = skills / name
        if src.is_dir() and not (parked / name).exists():
            tracked = git_files(root, f".claude/skills/{name}")
            parked.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(parked / name))
            skip_worktree(root, tracked, True)
            if name not in moved:
                moved.append(name)
            print(f"parked skill   {name}")
    s = load(local)
    prev = state.get("added", {})
    added = {"deny": list(prev.get("deny", [])), "env": dict(prev.get("env", {})),
             "disabledMcpjsonServers": list(prev.get("disabledMcpjsonServers", [])),
             "outputStyle": prev.get("outputStyle"), "guard": prev.get("guard", False)}
    deny = s.setdefault("permissions", {}).setdefault("deny", [])
    for d in DENY:
        if d not in deny:
            deny.append(d)
            added["deny"].append(d)
    want = dict(ENV)
    if opts.get("context"):
        want["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(opts["context"])
    if opts.get("no_thinking"):
        want["MAX_THINKING_TOKENS"] = "0"
    env = s.setdefault("env", {})
    for k, v in want.items():
        if k not in env:
            env[k] = v
            added["env"][k] = v
    if not opts.get("keep_outlook"):
        dis = s.setdefault("disabledMcpjsonServers", [])
        if "outlook" not in dis:
            dis.append("outlook")
            added["disabledMcpjsonServers"].append("outlook")
    if not opts.get("no_style") and "outputStyle" not in s:
        s["outputStyle"] = STYLE
        added["outputStyle"] = STYLE
    if not opts.get("no_guard"):
        pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
        if not any(GUARD_CMD in h.get("command", "") for e in pre for h in e.get("hooks", [])):
            pre.append(GUARD)
            added["guard"] = True
    for k in ("permissions", "env", "hooks"):
        if not s.get(k):
            s.pop(k, None)
    if not s.get("disabledMcpjsonServers"):
        s.pop("disabledMcpjsonServers", None)
    save(local, s)
    save(state_p, {"parked_skills": moved, "added": added})
    print("settings       .claude/settings.local.json — "
          + ", ".join(x for x in [
              f"{len(DENY)} deny rules",
              "env " + " ".join(f"{k}={v}" for k, v in want.items()),
              "outlook MCP off" if "outlook" in s.get("disabledMcpjsonServers", []) else "",
              f"output style '{s.get('outputStyle')}'" if s.get("outputStyle") else "",
              "guard hook on" if added["guard"] else ""] if x))
    print("Lean mode ON. Restart the agent session so it picks up the change.")


def cmd_off(root: Path) -> None:
    skills, parked, local, state_p = paths(root)
    state = load(state_p)
    for name in state.get("parked_skills", []):
        src = parked / name
        if src.is_dir() and not (skills / name).exists():
            shutil.move(str(src), str(skills / name))
            skip_worktree(root, git_files(root, f".claude/skills/{name}"), False)
            print(f"restored skill {name}")
    if parked.is_dir() and not any(parked.iterdir()):
        parked.rmdir()
    if local.exists():
        s = load(local)
        added = state.get("added", {})
        perms = s.get("permissions", {})
        perms["deny"] = [d for d in perms.get("deny", []) if d not in added.get("deny", [])]
        if not perms["deny"]:
            perms.pop("deny")
        if not perms:
            s.pop("permissions", None)
        env = s.get("env", {})
        for k, v in added.get("env", {}).items():
            if env.get(k) == v:
                env.pop(k)
        if not env:
            s.pop("env", None)
        dis = [d for d in s.get("disabledMcpjsonServers", []) if d not in added.get("disabledMcpjsonServers", [])]
        if dis:
            s["disabledMcpjsonServers"] = dis
        else:
            s.pop("disabledMcpjsonServers", None)
        if added.get("outputStyle") and s.get("outputStyle") == added["outputStyle"]:
            s.pop("outputStyle")
        if added.get("guard"):
            hooks = s.get("hooks", {})
            pre = [e for e in hooks.get("PreToolUse", [])
                   if not any(GUARD_CMD in h.get("command", "") for h in e.get("hooks", []))]
            if pre:
                hooks["PreToolUse"] = pre
            else:
                hooks.pop("PreToolUse", None)
            if not hooks:
                s.pop("hooks", None)
        if s:
            save(local, s)
        else:
            local.unlink()
    if state_p.exists():
        state_p.unlink()
    print("Lean mode OFF. Restart the agent session so it picks up the change.")


def cmd_status(root: Path) -> None:
    skills, parked, local, state_p = paths(root)
    active = [n for n in DEV_SKILLS if (skills / n).is_dir()]
    gtd = sorted(p.name for p in skills.glob("gtd-*") if p.is_dir()) if skills.is_dir() else []
    size = sum(f.stat().st_size for n in active for f in (skills / n).rglob("*") if f.is_file())
    print(f"lean mode      {'ON' if state_p.exists() else 'OFF'}")
    print(f"dev skills     {len(active)} loaded ({size // 1024} KB on disk)"
          + (" — run `lean_mode.py on` to park them" if active else ""))
    print(f"gtd skills     {len(gtd)} loaded")
    s = load(local)
    print(f"deny rules     {len(s.get('permissions', {}).get('deny', []))}")
    print(f"outlook MCP    {'disabled' if 'outlook' in s.get('disabledMcpjsonServers', []) else 'enabled'}")
    guard = any(GUARD_CMD in h.get("command", "") for e in s.get("hooks", {}).get("PreToolUse", [])
                for h in e.get("hooks", []))
    print(f"guard hook     {'on' if guard else 'off'}")
    print(f"output style   {s.get('outputStyle', '(default)')}")
    env = s.get("env", {})
    keys = list(ENV) + ["CLAUDE_CODE_MAX_CONTEXT_TOKENS", "MAX_THINKING_TOKENS"]
    print("env            " + (" ".join(f"{k}={env[k]}" for k in keys if k in env) or "(none)"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Toggle lean mode for light LLMs.")
    ap.add_argument("cmd", choices=["on", "off", "status"])
    ap.add_argument("--keep-outlook", action="store_true", help="on: leave the Outlook MCP enabled")
    ap.add_argument("--no-guard", action="store_true", help="on: don't install the guard hook")
    ap.add_argument("--no-style", action="store_true", help="on: don't select the GTD Lean output style")
    ap.add_argument("--no-thinking", action="store_true", help="on: set MAX_THINKING_TOKENS=0")
    ap.add_argument("--context", type=int, help="on: your model's real context window in tokens")
    ap.add_argument("--root", help="vault root (default: this repo)")
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    opts = {k: getattr(a, k) for k in ("keep_outlook", "no_guard", "no_style", "no_thinking", "context")}
    {"on": lambda: cmd_on(root, opts), "off": lambda: cmd_off(root),
     "status": lambda: cmd_status(root)}[a.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
