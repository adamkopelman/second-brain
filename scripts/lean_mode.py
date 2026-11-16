#!/usr/bin/env python3
"""Lean mode: make the vault cheap to run on small-context / light LLMs (DeepSeek Flash, Haiku-class,
local models). Reversible and idempotent. stdlib only.

    python scripts/lean_mode.py status
    python scripts/lean_mode.py on  [--keep-outlook]
    python scripts/lean_mode.py off

`on` does three things:
  1. Parks the 14 vendored *developer* skills (Superpowers: brainstorming, TDD, writing-skills, …)
     in `.claude/skills-dev/`. Their descriptions load into EVERY session and `using-superpowers`
     tells the model to open skills before any reply — on a light model that alone can burn
     tens of thousands of tokens before any GTD work. The GTD skills stay.
     In a git checkout the parked files are marked skip-worktree, so `git status` stays clean.
  2. Writes `.claude/settings.local.json` (per-machine, not committed): deny Read on folders an
     agent never needs for GTD work (vendor/, plugin code, dev docs, recordings, dashboard build
     output), and caps on Bash / MCP output so one noisy command can't flood the context.
  3. Disables the Outlook MCP server for the project (its tool schemas cost context every turn)
     unless --keep-outlook. Turn it back on for a session with `/mcp`, or run `off`.
`off` undoes exactly what `on` recorded in `.claude/lean-mode.json`.
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
ENV = {"BASH_MAX_OUTPUT_LENGTH": "12000", "MAX_MCP_OUTPUT_TOKENS": "6000"}


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


def cmd_on(root: Path, keep_outlook: bool) -> None:
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
    perms = s.setdefault("permissions", {})
    deny = perms.setdefault("deny", [])
    added_deny = [d for d in DENY if d not in deny]
    deny.extend(added_deny)
    env = s.setdefault("env", {})
    added_env = {k: v for k, v in ENV.items() if k not in env}
    env.update(added_env)
    added_mcp = []
    if not keep_outlook:
        dis = s.setdefault("disabledMcpjsonServers", [])
        if "outlook" not in dis:
            dis.append("outlook")
            added_mcp.append("outlook")
    save(local, s)
    prev = state.get("added", {})
    state = {
        "parked_skills": moved,
        "added": {
            "deny": sorted(set(prev.get("deny", [])) | set(added_deny)),
            "env": {**prev.get("env", {}), **added_env},
            "disabledMcpjsonServers": sorted(set(prev.get("disabledMcpjsonServers", [])) | set(added_mcp)),
        },
    }
    save(state_p, state)
    print(f"settings       .claude/settings.local.json (+{len(added_deny)} deny, +{len(added_env)} env"
          + (", outlook MCP off" if added_mcp else "") + ")")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Toggle lean mode for light LLMs.")
    ap.add_argument("cmd", choices=["on", "off", "status"])
    ap.add_argument("--keep-outlook", action="store_true", help="on: leave the Outlook MCP enabled")
    ap.add_argument("--root", help="vault root (default: this repo)")
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    {"on": lambda: cmd_on(root, a.keep_outlook), "off": lambda: cmd_off(root),
     "status": lambda: cmd_status(root)}[a.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
