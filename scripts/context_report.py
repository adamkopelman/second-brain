#!/usr/bin/env python3
"""Where did the context go? Reads a Claude Code session transcript (.jsonl) and shows which
messages filled it: tool results by tool and file, the model's own text and thinking, what it
wrote, repeated reads, compactions, and the biggest jumps in context size. Read-only, stdlib only.

    python scripts/context_report.py              # latest session of this vault
    python scripts/context_report.py --list       # recent sessions to pick from
    python scripts/context_report.py <file.jsonl> # a specific transcript
    python scripts/context_report.py --top 15     # longer lists

Sizes are estimates: tokens ≈ characters ÷ 4 (non-English text runs higher). When the
transcript has the API's usage numbers, the "context per turn" figures are exact.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path


# bookkeeping records Claude Code keeps in the transcript, not conversation the model re-reads
SKIP_ATTACHMENTS = {"prompt_snapshot", "deferred_tools_record"}


def tok(chars: int) -> int:
    return chars // 4


def fmt(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "projects"


def session_dir(project: Path) -> Path | None:
    """Claude Code stores a project's sessions under projects/<path with non-alphanumerics → '-'>."""
    root = projects_dir()
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))
    for cand in (root / slug, root / slug.lower()):
        if cand.is_dir():
            return cand
    if root.is_dir():  # case/format differences between versions: match ignoring case
        for d in root.iterdir():
            if d.is_dir() and d.name.lower() == slug.lower():
                return d
    return None


def sessions(project: Path) -> list[Path]:
    d = session_dir(project)
    if not d:
        return []
    return sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    out.append(c.get("text", ""))
                elif c.get("type") == "image":
                    out.append("x" * 6000)  # an image costs roughly 1.5k tokens
                else:
                    out.append(json.dumps(c))
            else:
                out.append(str(c))
        return "\n".join(out)
    return json.dumps(content) if content is not None else ""


def label(name: str, inp: dict) -> str:
    for k in ("file_path", "notebook_path", "path", "pattern", "command", "url", "query",
              "prompt", "description", "skill", "subagent_type"):
        v = inp.get(k)
        if isinstance(v, str) and v:
            v = v.replace("\n", " ")
            return v if len(v) <= 70 else v[:67] + "…"
    return ""


def short_path(p: str, cwd: str | None) -> str:
    if cwd and p.startswith(cwd):
        p = p[len(cwd):].lstrip("/\\")
    return p


def analyse(path: Path) -> dict:
    uses: dict[str, tuple[str, str]] = {}  # tool_use_id -> (name, label)
    cat = collections.Counter()  # category -> chars
    by_tool_result = collections.Counter()
    by_tool_input = collections.Counter()
    by_attachment = collections.Counter()
    results = []  # (chars, tool, label)
    reads = collections.Counter()
    turns = []  # (context tokens, last tool label before it)
    compactions = 0
    last_label = "(your message)"
    cwd = None
    model = None
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("isSidechain"):
            continue  # subagent work runs in its own context
        cwd = cwd or d.get("cwd")
        t = d.get("type")
        if t == "system" and d.get("subtype") == "compact_boundary":
            compactions += 1
            last_label = "(compaction summary)"
            continue
        if t == "attachment":
            a = d.get("attachment") or {}
            kind = a.get("type", "?")
            if kind in SKIP_ATTACHMENTS:
                continue
            n = len(json.dumps(a))
            cat["attachments (skill list, reminders, hook output, @files)"] += n
            by_attachment[kind] += n
            continue
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        if t == "user":
            if d.get("isCompactSummary"):
                cat["compaction summaries"] += len(text_of(content))
                continue
            if isinstance(content, list) and content and isinstance(content[0], dict) \
                    and content[0].get("type") == "tool_result":
                for c in content:
                    if not isinstance(c, dict) or c.get("type") != "tool_result":
                        continue
                    name, lab = uses.get(c.get("tool_use_id"), ("?", ""))
                    n = len(text_of(c.get("content")))
                    cat["tool results"] += n
                    by_tool_result[name] += n
                    results.append((n, name, lab))
                    last_label = f"{name} {lab}".strip()
            else:
                cat["your messages"] += len(text_of(content))
                last_label = "(your message)"
        elif t == "assistant":
            model = m.get("model") or model
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict):
                    continue
                ct = c.get("type")
                if ct == "text":
                    cat["model replies (text)"] += len(c.get("text", ""))
                elif ct in ("thinking", "redacted_thinking"):
                    cat["model thinking"] += len(c.get("thinking", "") or c.get("data", ""))
                elif ct == "tool_use":
                    name, inp = c.get("name", "?"), c.get("input") or {}
                    lab = label(name, inp)
                    if "file_path" in inp:
                        lab = short_path(lab, cwd)
                    uses[c.get("id")] = (name, lab)
                    n = len(json.dumps(inp))
                    cat["tool calls (what the model sent)"] += n
                    by_tool_input[name] += n
                    if name == "Read":
                        reads[lab] += 1
            u = m.get("usage") or {}
            ctx = sum(int(u.get(k) or 0) for k in
                      ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            if ctx:
                turns.append((ctx, last_label))
    return {"cat": cat, "by_attachment": by_attachment, "by_result": by_tool_result, "by_input": by_tool_input, "results": results,
            "reads": reads, "turns": turns, "compactions": compactions, "model": model, "cwd": cwd}


def report(path: Path, top: int) -> list[str]:
    a = analyse(path)
    cat = a["cat"]
    total = sum(cat.values()) or 1
    out = [f"Session {path.stem[:8]} · {path.stat().st_size // 1024} KB transcript"
           + (f" · model {a['model']}" if a["model"] else "")
           + f" · compactions {a['compactions']}"]
    if a["turns"]:
        peak = max(c for c, _ in a["turns"])
        out.append(f"Context: peak {fmt(peak)} tokens over {len(a['turns'])} model turns (from API usage)")
    out.append("")
    out.append("Where the message tokens went (≈ chars/4, whole session incl. compacted parts)")
    for k, v in cat.most_common():
        out.append(f"  {fmt(tok(v)):>7}  {v * 100 // total:>3}%  {k}")
    big_att = [(k, v) for k, v in a["by_attachment"].most_common(5) if tok(v) >= 200]
    if big_att:
        out.append("")
        out.append("Attachments by kind")
        for k, v in big_att:
            out.append(f"  {fmt(tok(v)):>7}  {k}")
    if a["by_result"]:
        out.append("")
        out.append("Tool results by tool")
        for k, v in a["by_result"].most_common(8):
            n = sum(1 for _, name, _ in a["results"] if name == k)
            out.append(f"  {fmt(tok(v)):>7}  {k} ×{n}")
    big_in = [(k, v) for k, v in a["by_input"].most_common(4) if tok(v) >= 500]
    if big_in:
        out.append("")
        out.append("Tool calls by tool (content the model wrote: Write/Edit bodies, prompts)")
        for k, v in big_in:
            out.append(f"  {fmt(tok(v)):>7}  {k}")
    if a["results"]:
        out.append("")
        out.append(f"Largest tool results (top {top})")
        for n, name, lab in sorted(a["results"], reverse=True)[:top]:
            out.append(f"  {fmt(tok(n)):>7}  {name:<6} {lab}")
    rep = [(k, v) for k, v in a["reads"].most_common() if v > 1]
    if rep:
        out.append("")
        out.append("Files read more than once")
        for k, v in rep[:top]:
            out.append(f"  ×{v}  {k}")
    jumps = []
    for (prev, _), (cur, lab) in zip(a["turns"], a["turns"][1:]):
        if cur > prev:
            jumps.append((cur - prev, lab))
    if jumps:
        out.append("")
        out.append("Biggest jumps in context between two turns (and what came just before)")
        for d, lab in sorted(jumps, reverse=True)[:min(top, 6)]:
            out.append(f"  +{fmt(d):>6}  {lab}")
    out.append("")
    out += ["Suggestions"] + [f"  • {s}" for s in advise(a, total)]
    return out


def advise(a: dict, total: int) -> list[str]:
    cat, tips = a["cat"], []
    share = lambda k: cat.get(k, 0) / total
    if share("model thinking") > 0.2:
        tips.append("Thinking is a big share. Try `lean_mode.py on --no-thinking` (MAX_THINKING_TOKENS=0) "
                    "and see if answers stay good enough.")
    if share("tool results") > 0.4:
        reads = a["by_result"].get("Read", 0) / max(1, cat.get("tool results", 1))
        if reads > 0.4:
            tips.append("Most results are file reads. Lean mode's guard hook blocks whole-file reads "
                        "of big files; gtd_query.py answers most questions without reading notes.")
        else:
            tips.append("Tool output dominates. Check the 'Largest tool results' list for the commands "
                        "to replace with gtd_query.py or a subagent.")
    if a["by_input"].get("Write", 0) > 4 * 4000:
        tips.append("The model rewrote whole files with Write. Edit changes only the lines needed; "
                    "the guard hook blocks Write over big existing files.")
    if any(v > 1 for v in a["reads"].values()):
        tips.append("Some files were read more than once — usually after compaction lost them. "
                    "/clear between tasks, and read narrowly (offset/limit).")
    if share("model replies (text)") > 0.2:
        tips.append("The model's own replies are a big share. The GTD Lean output style keeps them short.")
    if a["compactions"] >= 2:
        tips.append("Several compactions: split the work — one GTD task per session, /clear in between.")
    return tips or ["Nothing stands out. Compare with a session that compacted."]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Show where a Claude Code session's context went.")
    ap.add_argument("transcript", nargs="?", help="path to a .jsonl transcript (default: latest)")
    ap.add_argument("--project", default=".", help="project folder whose sessions to use")
    ap.add_argument("--list", action="store_true", help="list recent sessions")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.transcript:
        path = Path(a.transcript)
    else:
        found = sessions(Path(a.project))
        if a.list:
            if not found:
                print(f"No sessions found under {projects_dir()} for {Path(a.project).resolve()}")
            for p in found[:10]:
                print(f"  {p.stat().st_size // 1024:>6} KB  {p}")
            return 0
        if not found:
            print(f"No sessions found under {projects_dir()} for {Path(a.project).resolve()}. "
                  "Pass the .jsonl path, or --project <vault folder>.")
            return 1
        path = found[0]
    print("\n".join(report(path, a.top)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
