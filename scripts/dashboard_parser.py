#!/usr/bin/env python3
"""Parse vault task/project state for the local dashboard server. stdlib only."""
from __future__ import annotations
import datetime as _dt
import re as _re
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard as BD


def _clean_no_links(body: str) -> str:
    """Like build_dashboard._clean, but drops [[wikilinks]] entirely instead of flattening
    them to their link text. Task text here is displayed/edited standalone from its
    project/meeting pill (see collect_state), so the link text must not also live inside it —
    unlike build_dashboard.py's own read-only static export, which has no separate pill and
    should keep flattening."""
    t = BD.FIELD_RE.sub("", body)
    t = BD.LINK_RE.sub("", t)
    t = BD.TAG_RE.sub("", t)
    return _re.sub(r"\s+", " ", t).strip()


def _links_except_self(body: str, own_stem: str) -> list[str]:
    """Display names of a task's [[wikilinks]] (e.g. the person on a #waiting item), skipping
    the backlink to the note the task lives in, which the project/meeting pill already shows."""
    out = []
    for raw in BD.LINK_RE.findall(body):
        target, _, alias = raw.partition("|")
        if target.split("#")[0].strip() == own_stem:
            continue
        out.append((alias or target).strip())
    return out


def iter_tasks_with_location(vault: Path):
    """Yield one dict per task checkbox line across all CONTENT folders (README excluded)."""
    vault = Path(vault)
    for d in BD.CONTENT:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            rel = str(p.relative_to(vault)).replace("\\", "/")
            for raw_line in p.read_text(encoding="utf-8").splitlines():
                m = BD.TASK_RE.match(raw_line)
                if not m:
                    continue
                body = m.group("b")
                tags = ["#" + t for t in BD.TAG_RE.findall(body)]
                fields = {k: v.strip() for k, v in BD.FIELD_RE.findall(body)}
                yield {
                    "file": rel,
                    "line_text": raw_line.rstrip(),
                    "done": m.group("m").lower() == "x",
                    "text": _clean_no_links(body),
                    "links": _links_except_self(body, p.stem),
                    "tags": tags,
                    "fields": fields,
                    "project": p.stem if d == "10 Projects" else None,
                    "meeting": p.stem if d == "Meetings" else None,
                }


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"')
    return fm


def _project_frontmatter(p: Path) -> dict:
    return _parse_frontmatter(p.read_text(encoding="utf-8"))


_OUTCOME_RE = _re.compile(r"^\*\*Outcome:\*\*\s*(.*)$", _re.MULTILINE)


def _extract_outcome(text: str) -> str | None:
    """Pull the '**Outcome:** ...' line's text, or None if absent/still the
    template's italic placeholder (e.g. `_What does "done" look like?_`)."""
    m = _OUTCOME_RE.search(text)
    if not m:
        return None
    outcome = m.group(1).strip()
    if outcome.startswith("_") and outcome.endswith("_") and len(outcome) > 1:
        return None
    return outcome or None


def collect_state(vault: Path) -> dict:
    vault = Path(vault)
    today = _dt.date.today()

    inbox_count = 0
    ib = vault / "00 Inbox"
    if ib.is_dir():
        inbox_count = len([p for p in ib.glob("*.md") if p.name != "README.md"])

    active_projects, someday_projects = [], []
    pj = vault / "10 Projects"
    if pj.is_dir():
        for p in sorted(pj.rglob("*.md")):
            if p.name == "README.md":
                continue
            text = p.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            outcome = _extract_outcome(text)
            status = fm.get("status", "")
            rel = str(p.relative_to(vault)).replace("\\", "/")
            if status == "active":
                review = fm.get("review")
                review_overdue = False
                if review:
                    try:
                        review_overdue = _dt.date.fromisoformat(review) <= today
                    except ValueError:
                        pass
                active_projects.append({
                    "name": p.stem, "file": rel, "review": review, "review_overdue": review_overdue,
                    "outcome": outcome,
                })
            elif status == "someday":
                someday_projects.append({"name": p.stem, "file": rel, "outcome": outcome})

    tasks_by_context: dict[str, list[dict]] = {}
    waiting: list[dict] = []
    due_soon: list[dict] = []
    for t in iter_tasks_with_location(vault):
        if t["done"]:
            continue
        tags, fields = t["tags"], t["fields"]
        if "#waiting" in tags:
            waiting.append({
                "text": t["text"], "file": t["file"], "line_text": t["line_text"],
                "project": t["project"], "meeting": t["meeting"], "since": fields.get("since"),
                "links": t["links"],
            })
            continue
        if "#next" not in tags:
            continue
        sched = fields.get("scheduled")
        if sched:
            try:
                if _dt.date.fromisoformat(sched) > today:
                    continue
            except ValueError:
                pass
        ctx = next((c for c in BD.CONTEXTS if c in tags), "#anywhere")
        due = fields.get("due")
        entry = {
            "text": t["text"], "file": t["file"], "line_text": t["line_text"],
            "project": t["project"], "meeting": t["meeting"], "context": ctx, "due": due,
            "links": t["links"],
        }
        tasks_by_context.setdefault(ctx, []).append(entry)
        if due:
            try:
                due_date = _dt.date.fromisoformat(due)
                if due_date <= today + _dt.timedelta(days=7):
                    due_soon.append({**entry, "overdue": due_date < today})
            except ValueError:
                pass

    meetings: list[dict] = []
    mt = vault / "Meetings"
    if mt.is_dir():
        for p in sorted(mt.glob("*.md")):
            if p.name == "README.md":
                continue
            fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
            rel = str(p.relative_to(vault)).replace("\\", "/")
            meetings.append({
                "name": p.stem, "file": rel, "date": fm.get("date"),
                "transcription_status": fm.get("transcription_status"),
                "summary_status": fm.get("summary_status"),
            })
        meetings.sort(key=lambda m: m["date"] or "", reverse=True)
        meetings = meetings[:8]

    return {
        "vault_name": vault.resolve().name,
        "inbox_count": inbox_count,
        "tasks_by_context": tasks_by_context,
        "waiting": waiting,
        "due_soon": due_soon,
        "active_projects": active_projects,
        "someday_projects": someday_projects,
        "meetings": meetings,
    }
