#!/usr/bin/env python3
"""Token-cheap answers about the vault, for agents (and light LLMs) that would otherwise grep and
read whole folders. Every command prints a few compact lines; nothing is written. stdlib only.

    python scripts/gtd_query.py brief                 # inbox, projects, review, top next actions
    python scripts/gtd_query.py next [--ctx phone] [--limit 10]
    python scripts/gtd_query.py waiting [--stale 14]
    python scripts/gtd_query.py inbox                 # one line per inbox item (oldest first)
    python scripts/gtd_query.py projects [--status active|someday|done|all]
    python scripts/gtd_query.py health                # stuck/stale/overdue/archive candidates
    python scripts/gtd_query.py meetings              # pending transcription / summary
    python scripts/gtd_query.py find <text> [--limit 15]   # tasks + note names matching text
    python scripts/gtd_query.py sizes [--top 10]      # biggest notes (what to avoid reading whole)

Output lines point at `file:line` so an agent can open just that line instead of the file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_parser as P  # noqa: E402

CONTEXT_TAGS = ("computer", "phone", "errands", "home", "office", "anywhere", "agenda", "unknown")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today() -> dt.date:
    return dt.date.today()


def _date(s: str | None) -> dt.date | None:
    s = (s or "").strip()
    if not _DATE.match(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def _vault(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    return Path(__file__).resolve().parents[1]


def _tasks(vault: Path) -> list[dict]:
    """Open/closed task lines with their 1-based line number."""
    out = list(P.iter_tasks_with_location(vault))
    # iter_tasks_with_location gives each task's exact line text; recover its line number
    lines: dict[str, list[str]] = {}
    used: dict[str, set[int]] = {}
    for t in out:
        f = t["file"]
        if f not in lines:
            lines[f] = [l.rstrip() for l in (vault / f).read_text(encoding="utf-8").splitlines()]
            used[f] = set()
        n = next((i for i, l in enumerate(lines[f]) if l == t["line_text"] and i not in used[f]), -1)
        used[f].add(n)
        t["line"] = n + 1
    return out


def _where(t: dict) -> str:
    return t.get("project") or t.get("area") or t.get("meeting") or Path(t["file"]).stem


def _ctx(t: dict) -> str:
    return next((c for c in CONTEXT_TAGS if "#" + c in t["tags"]), "-")


def _line(t: dict) -> str:
    bits = [t["text"] or "(no text)", f"[{_where(t)}]", "@" + _ctx(t)]
    f = t["fields"]
    if f.get("due"):
        bits.append("due " + f["due"])
    if f.get("scheduled"):
        bits.append("sched " + f["scheduled"])
    if f.get("since"):
        bits.append("since " + f["since"])
    if t["links"]:
        bits.append("→ " + ", ".join(t["links"]))
    return " · ".join(bits) + f"  ({t['file']}:{t['line']})"


def _open_next(tasks: list[dict], ctx: str | None = None) -> list[dict]:
    today = _today()
    out = []
    for t in tasks:
        if t["done"] or "#next" not in t["tags"] or "#waiting" in t["tags"]:
            continue
        s = _date(t["fields"].get("scheduled"))
        if s and s > today:
            continue
        if ctx and ("#" + ctx.lstrip("#@")) not in t["tags"]:
            continue
        out.append(t)

    def key(t):
        d = _date(t["fields"].get("due"))
        return (0 if d else 1, d or dt.date.max, _ctx(t), t["file"])

    return sorted(out, key=key)


def _notes(vault: Path, folder: str) -> list[Path]:
    base = vault / folder
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if p.name != "README.md")


def _fm(p: Path) -> dict:
    return P._parse_frontmatter(p.read_text(encoding="utf-8"))


def _inbox(vault: Path) -> list[Path]:
    base = vault / "00 Inbox"
    if not base.is_dir():
        return []
    items = [p for p in base.iterdir() if p.is_file() and p.suffix == ".md" and p.name != "README.md"]
    return sorted(items, key=lambda p: (p.stem[:10] if _DATE.match(p.stem[:10]) else "9999", p.stat().st_mtime))


def _last_review(vault: Path) -> tuple[Path | None, int | None]:
    best = None
    for p in _notes(vault, "Journal"):
        if "weekly-review" in p.read_text(encoding="utf-8"):
            if best is None or p.stat().st_mtime > best.stat().st_mtime:
                best = p
    if best is None:
        return None, None
    age = (dt.datetime.now() - dt.datetime.fromtimestamp(best.stat().st_mtime)).days
    return best, age


# ---- commands -----------------------------------------------------------------------------------

def cmd_brief(vault: Path, a) -> list[str]:
    tasks = _tasks(vault)
    active = [p for p in _notes(vault, "10 Projects") if _fm(p).get("status") == "active"]
    nxt = _open_next(tasks)
    best, age = _last_review(vault)
    review = "none yet — run /gtd-weekly-review" if best is None else (
        f"{age}d ago" + (" ⚠ due" if age >= 7 else ""))
    out = [f"Inbox {len(_inbox(vault))} · active projects {len(active)} · open #next {len(nxt)} · "
           f"weekly review {review}"]
    out += ["  • " + _line(t) for t in nxt[: a.limit]]
    return out


def cmd_next(vault: Path, a) -> list[str]:
    nxt = _open_next(_tasks(vault), a.ctx)
    head = f"{len(nxt)} open #next" + (f" @{a.ctx.lstrip('#@')}" if a.ctx else "")
    return [head] + ["  • " + _line(t) for t in nxt[: a.limit]] + (
        [f"  … {len(nxt) - a.limit} more (--limit)"] if len(nxt) > a.limit else [])


def cmd_waiting(vault: Path, a) -> list[str]:
    today = _today()
    w = [t for t in _tasks(vault) if not t["done"] and "#waiting" in t["tags"]]
    out = [f"{len(w)} waiting-for"]
    for t in sorted(w, key=lambda t: t["fields"].get("since") or ""):
        s = _date(t["fields"].get("since"))
        stale = s is not None and (today - s).days > a.stale
        out.append(("  ⚠ " if stale else "  • ") + _line(t))
    return out[: a.limit + 1]


def cmd_inbox(vault: Path, a) -> list[str]:
    items = _inbox(vault)
    out = [f"{len(items)} inbox item(s), oldest first"]
    for p in items[: a.limit]:
        text = p.read_text(encoding="utf-8")
        first = P._inbox_note(vault, p, text)["text"]
        out.append(f"  • {first[:100]}  ({p.relative_to(vault).as_posix()}, {len(text)} chars)")
    return out


def cmd_projects(vault: Path, a) -> list[str]:
    tasks = _tasks(vault)
    out = []
    for p in _notes(vault, "10 Projects"):
        fm = _fm(p)
        st = fm.get("status", "?")
        if a.status != "all" and st != a.status:
            continue
        mine = [t for t in tasks if t["file"] == p.relative_to(vault).as_posix() and not t["done"]]
        n = sum("#next" in t["tags"] and "#waiting" not in t["tags"] for t in mine)
        w = sum("#waiting" in t["tags"] for t in mine)
        out.append(f"  • {p.stem} [{st}] next {n} · waiting {w} · review {fm.get('review') or '-'}")
    return [f"{len(out)} project(s) ({a.status})"] + out[: a.limit]


def cmd_health(vault: Path, a) -> list[str]:
    today = _today()
    tasks = _tasks(vault)
    out = []
    for p in _notes(vault, "10 Projects"):
        fm = _fm(p)
        rel = p.relative_to(vault).as_posix()
        st = fm.get("status")
        if st == "active":
            if not any(t["file"] == rel and not t["done"] and "#next" in t["tags"]
                       and "#waiting" not in t["tags"] for t in tasks):
                out.append(f"  STUCK     {rel} — no open #next")
            r = _date(fm.get("review"))
            if r and r < today:
                out.append(f"  REVIEW    {rel} — review: {r} passed")
        if st == "done":
            out.append(f"  ARCHIVE   {rel} — status: done, still outside 40 Archive/")
    for t in tasks:
        s = _date(t["fields"].get("since"))
        if not t["done"] and "#waiting" in t["tags"] and s and (today - s).days > a.stale:
            out.append(f"  STALE     {t['file']}:{t['line']} — waiting {(today - s).days}d: {t['text'][:60]}")
        d = _date(t["fields"].get("due"))
        if not t["done"] and d and d < today:
            out.append(f"  OVERDUE   {t['file']}:{t['line']} — due {d}: {t['text'][:60]}")
    n = len(_inbox(vault))
    if n:
        out.append(f"  INBOX     {n} item(s) waiting — /gtd-process-inbox")
    best, age = _last_review(vault)
    if best is None or age >= 7:
        out.append("  WEEKLY    weekly review " + ("never done" if best is None else f"{age}d old"))
    return [f"{len(out)} issue(s)"] + out[: a.limit]


def cmd_meetings(vault: Path, a) -> list[str]:
    out = []
    base = vault / "Meetings"
    if base.is_dir():
        for p in sorted(base.glob("*.md")):
            if p.name == "README.md":
                continue
            fm = _fm(p)
            ts, ss = fm.get("transcription_status") or "-", fm.get("summary_status") or "-"
            if ts == "pending" or ts == "failed" or (ts == "done" and ss != "done"):
                size = len(p.read_text(encoding="utf-8"))
                out.append(f"  • {p.stem} transcription={ts} summary={ss} ({size} chars)")
    return [f"{len(out)} meeting(s) needing work"] + out[: a.limit]


def cmd_find(vault: Path, a) -> list[str]:
    q = " ".join(a.text).lower()
    hits = [("  • " + _line(t)) for t in _tasks(vault) if not t["done"] and q in t["line_text"].lower()]
    for folder in P.BD.CONTENT + ["30 Resources", "40 Archive"]:
        for p in _notes(vault, folder):
            if q in p.stem.lower():
                hits.append(f"  ▸ note {p.relative_to(vault).as_posix()}")
    return [f"{len(hits)} match(es) for '{q}'"] + hits[: a.limit]


def cmd_sizes(vault: Path, a) -> list[str]:
    files = []
    for folder in P.BD.CONTENT + ["30 Resources", "40 Archive"]:
        files += [(p.stat().st_size, p) for p in _notes(vault, folder)]
    files.sort(reverse=True)
    return [f"largest notes (≈tokens = bytes/4)"] + [
        f"  {s:>8} B  ≈{s // 4:>6} tok  {p.relative_to(vault).as_posix()}" for s, p in files[: a.top]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vault", help="vault root (default: this repo)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **extra):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        sp.add_argument("--limit", type=int, default=extra.pop("limit", 10))
        for k, v in extra.items():
            sp.add_argument("--" + k, **v)
        return sp

    add("brief", cmd_brief, limit=5)
    add("next", cmd_next, ctx={"default": None})
    add("waiting", cmd_waiting, limit=20, stale={"type": int, "default": 14})
    add("inbox", cmd_inbox, limit=20)
    add("projects", cmd_projects, limit=30, status={"default": "active"})
    add("health", cmd_health, limit=40, stale={"type": int, "default": 14})
    add("meetings", cmd_meetings, limit=20)
    add("find", cmd_find, limit=15).add_argument("text", nargs="+")
    add("sizes", cmd_sizes, top={"type": int, "default": 10})

    a = ap.parse_args(argv)
    vault = _vault(a.vault)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles
    except Exception:
        pass
    print("\n".join(a.fn(vault, a)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
