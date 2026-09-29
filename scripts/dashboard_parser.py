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


_HEADING_RE = _re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# Obsidian Tasks writes a completion date as "✅ 2026-09-29"; Dataview/this dashboard as [completion:: …]
_DONE_EMOJI_RE = _re.compile(r"\u2705\s*(\d{4}-\d{2}-\d{2})")


def iter_tasks_with_location(vault: Path):
    """Yield one dict per task checkbox line across all CONTENT folders (README excluded), with the
    `## heading` it sits under — a project's headings group its to-dos the way Things' do."""
    vault = Path(vault)
    for d in BD.CONTENT:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            rel = str(p.relative_to(vault)).replace("\\", "/")
            heading = None
            for raw_line in p.read_text(encoding="utf-8").splitlines():
                h = _HEADING_RE.match(raw_line)
                if h:
                    # the H1 is the note's own title, not a heading inside it
                    heading = h.group(2).strip() if len(h.group(1)) > 1 else None
                    continue
                m = BD.TASK_RE.match(raw_line)
                if not m:
                    continue
                body = m.group("b")
                done_emoji = _DONE_EMOJI_RE.search(body)
                text = _DONE_EMOJI_RE.sub("", _clean_no_links(body)).strip()
                links = _links_except_self(body, p.stem)
                if not text and not links:
                    continue  # unfilled template placeholder, e.g. the Daily Note's "- [ ]  #next"
                tags = ["#" + t for t in BD.TAG_RE.findall(body)]
                fields = {k: v.strip() for k, v in BD.FIELD_RE.findall(body)}
                yield {
                    "file": rel,
                    "line_text": raw_line.rstrip(),
                    "done": m.group("m").lower() == "x",
                    "completed": fields.get("completion") or (done_emoji.group(1) if done_emoji else None),
                    "text": text,
                    "links": links,
                    "tags": tags,
                    "fields": fields,
                    "heading": heading,
                    "project": p.stem if d == "10 Projects" else None,
                    "area": p.stem if d == "20 Areas" else None,
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


_DATE_PREFIX_RE = _re.compile(r"^(\d{4}-\d{2}-\d{2})")
STATUS_TAGS = ("#next", "#waiting", "#someday")
EVENING_TAG = "#evening"
LOGBOOK_LIMIT = 300  # completed to-dos sent to the page; progress counts still use every one


def _inbox_note(vault: Path, p: Path, text: str) -> dict:
    """An inbox capture with no checkbox in it (a thought, a link): its first line of text, and
    when it was captured (frontmatter `captured`, else the file name's date prefix)."""
    fm = _parse_frontmatter(text)
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:]
    first = next((l.strip() for l in body.splitlines() if l.strip()), "")
    first = BD._clean(_re.sub(r"^#+\s+", "", first))
    date = _DATE_PREFIX_RE.match(p.stem)
    return {
        "file": str(p.relative_to(vault)).replace("\\", "/"),
        "name": p.stem,
        "text": first or p.stem,
        "captured": fm.get("captured") or (date.group(1) if date else None),
    }


def _link_name(value: str | None) -> str | None:
    """`"[[Career]]"` / `[[Career|Work]]` / `Career` -> `Career`."""
    v = (value or "").strip().strip('"').strip("'").strip()
    m = BD.LINK_RE.search(v)
    if m:
        v = m.group(1).partition("|")[0].split("#")[0]
    return v.strip() or None


def _todo(t: dict, project_areas: dict) -> dict:
    """One task line in the shape the page works with — Things' to-do: a When (the `scheduled`
    field, plus #evening for This Evening), a Deadline (`due`), tags, and where it lives."""
    tags, fields = t["tags"], t["fields"]
    status = next((s[1:] for s in ("#waiting", "#someday", "#next") if s in tags), None)
    ctx = next((c[1:] for c in BD.CONTEXTS if c in tags), None)
    other = [x[1:] for x in tags if x not in BD.CONTEXTS and x not in STATUS_TAGS and x != EVENING_TAG]
    return {
        "file": t["file"],
        "line_text": t["line_text"],
        "text": t["text"],
        "links": t["links"],
        "done": t["done"],
        "completed": t["completed"],
        "status": status,
        "context": ctx,
        "tags": other,
        "when": fields.get("scheduled") or None,
        "evening": EVENING_TAG in tags,
        "deadline": fields.get("due") or None,
        "since": fields.get("since") or None,
        "heading": t["heading"],
        "project": t["project"],
        "area": t["area"] or project_areas.get(t["project"]),
        "meeting": t["meeting"],
        "inbox": t["file"].startswith("00 Inbox/"),
    }


def collect_state(vault: Path) -> dict:
    """Everything the page shows, shaped like Things: to-dos, projects (with progress and
    headings) grouped into areas, the inbox, and meeting follow-ups. Which list a to-do shows
    on (Today, Upcoming, Anytime, …) is decided on the page, against the browser's own date."""
    vault = Path(vault)
    today = _dt.date.today()

    projects: list[dict] = []
    pj = vault / "10 Projects"
    if pj.is_dir():
        for p in sorted(pj.rglob("*.md")):
            if p.name == "README.md":
                continue
            text = p.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            status = fm.get("status", "")
            if status not in ("active", "someday"):
                continue
            review = fm.get("review") or None
            review_overdue = False
            if review and status == "active":
                try:
                    review_overdue = _dt.date.fromisoformat(review) <= today
                except ValueError:
                    pass
            headings = [h.group(2).strip() for h in map(_HEADING_RE.match, text.splitlines())
                        if h and len(h.group(1)) > 1]
            projects.append({
                "name": p.stem, "file": str(p.relative_to(vault)).replace("\\", "/"),
                "status": status, "area": _link_name(fm.get("area")), "outcome": _extract_outcome(text),
                "review": review, "review_overdue": review_overdue, "headings": headings,
                "open": 0, "done": 0,
            })
    by_project = {p["name"]: p for p in projects}
    project_areas = {p["name"]: p["area"] for p in projects}

    area_names = set()
    ar = vault / "20 Areas"
    if ar.is_dir():
        area_names.update(p.stem for p in ar.rglob("*.md") if p.name != "README.md")
    area_files = set(area_names)
    area_names.update(p["area"] for p in projects if p["area"])
    areas = [{"name": n, "file": f"20 Areas/{n}.md" if n in area_files else None}
             for n in sorted(area_names, key=str.lower)]

    todos, logbook = [], []
    task_files = set()
    for t in iter_tasks_with_location(vault):
        task_files.add(t["file"])
        proj = by_project.get(t["project"])
        if proj:
            proj["done" if t["done"] else "open"] += 1
        todo = _todo(t, project_areas)
        if t["done"]:
            logbook.append(todo)
            continue
        # outside projects, areas and the inbox a checkbox is only a GTD action once it's tagged
        if not (todo["status"] or proj or todo["area"] or todo["inbox"]):
            continue
        if t["project"] and not proj:
            continue  # a finished (status: done) project's leftovers
        todos.append(todo)
    logbook.sort(key=lambda x: x["completed"] or "", reverse=True)
    todos.extend(logbook[:LOGBOOK_LIMIT])

    inbox_notes: list[dict] = []
    ib = vault / "00 Inbox"
    if ib.is_dir():
        for p in ib.glob("*.md"):
            rel = str(p.relative_to(vault)).replace("\\", "/")
            if p.name == "README.md" or rel in task_files:
                continue
            inbox_notes.append(_inbox_note(vault, p, p.read_text(encoding="utf-8")))
        inbox_notes.sort(key=lambda i: (i["captured"] or "", i["file"]))

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
        "todos": todos,
        "projects": projects,
        "areas": areas,
        "inbox_notes": inbox_notes,
        "meetings": meetings,
    }
