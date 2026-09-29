#!/usr/bin/env python3
"""Write-back operations for the local dashboard server. stdlib only."""
from __future__ import annotations
import datetime as _dt
import json as _json
import re as _re
import subprocess as _subprocess
import sys as _sys
import threading as _threading
import wave as _wave
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard as BD
import dashboard_parser as DP


class LineNotFoundError(Exception):
    pass


class AmbiguousLineError(Exception):
    pass


class PathEscapesVaultError(Exception):
    pass


def _resolve(vault: Path, rel: str) -> Path:
    root = Path(vault).resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathEscapesVaultError(f"path escapes vault: {rel!r}")
    return candidate


def _find_line_index(lines: list[str], line_text: str) -> int:
    matches = [i for i, l in enumerate(lines) if l.rstrip() == line_text]
    if not matches:
        raise LineNotFoundError(f"line not found: {line_text!r}")
    if len(matches) > 1:
        raise AmbiguousLineError(f"line matched {len(matches)} times: {line_text!r}")
    return matches[0]


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _split_body(body: str):
    """A task body as (text, tags without '#', fields, links) — what _join_body puts back."""
    return (DP._clean_no_links(body), BD.TAG_RE.findall(body), dict(BD.FIELD_RE.findall(body)),
            BD.LINK_RE.findall(body))


def _join_body(text: str, tags: list[str], fields: dict, links: list[str]) -> str:
    parts = [text] + [f"#{t}" for t in tags] + [f"[{k}:: {v.strip()}]" for k, v in fields.items()]
    parts += [f"[[{l}]]" for l in links]
    return " ".join(p for p in parts if p)


def _task_parts(line: str):
    m = _re.match(r"^(\s*-\s*\[[ xX]\]\s*)(.*)$", line)
    if not m:
        raise LineNotFoundError(f"not a task checkbox line: {line!r}")
    return m.group(1), m.group(2)


STATUSES = ("next", "waiting", "someday")


def _set_status(tags: list[str], status: str) -> list[str]:
    return [t for t in tags if t not in STATUSES] + [status]


def _apply_when(tags: list[str], fields: dict, when: str, today: _dt.date) -> list[str]:
    """Things' When for one task: "today", "evening" (This Evening), an ISO date, "someday", or
    "anytime"/"" (no date). Dates live in [scheduled:: ], This Evening is #evening; anything given
    a date or Anytime comes back from #someday as a #next action."""
    if when is None:
        return tags
    tags = [t for t in tags if t != "evening"]
    fields.pop("scheduled", None)
    if when == "someday":
        return _set_status(tags, "someday")
    if when in ("today", "evening"):
        fields["scheduled"] = today.isoformat()
        if when == "evening":
            tags.append("evening")
    elif when and when != "anytime":
        fields["scheduled"] = _dt.date.fromisoformat(when).isoformat()  # ValueError on junk -> 400
    return _set_status(tags, "next") if "someday" in tags or not any(t in STATUSES for t in tags) else tags


def complete_task(vault: Path, file: str, line_text: str) -> str:
    """Tick the box and stamp [completion:: today], which is what files it in the Logbook."""
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    prefix, body = _task_parts(lines[i])
    text, tags, fields, links = _split_body(body)
    fields["completion"] = _dt.date.today().isoformat()
    lines[i] = _re.sub(r"\[ \]", "[x]", prefix, count=1) + _join_body(text, tags, fields, links)
    _write_lines(path, lines)
    return lines[i]


def uncomplete_task(vault: Path, file: str, line_text: str) -> str:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    prefix, body = _task_parts(lines[i])
    text, tags, fields, links = _split_body(body)
    fields.pop("completion", None)
    text = _re.sub(r"\s*✅\s*\d{4}-\d{2}-\d{2}", "", text).strip()
    lines[i] = _re.sub(r"\[[xX]\]", "[ ]", prefix, count=1) + _join_body(text, tags, fields, links)
    _write_lines(path, lines)
    return lines[i]


def _is_blank_capture(lines: list[str]) -> bool:
    """An inbox file with nothing left but its frontmatter."""
    body = "\n".join(lines)
    if body.startswith("---"):
        end = body.find("\n---", 3)
        body = body[end + 4:] if end != -1 else body
    return not body.strip()


def _remove_line(vault: Path, file: str, line_text: str) -> str:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    removed = lines.pop(i)
    # an inbox capture is one file per item: once its only line is gone, so is the capture
    if file.startswith("00 Inbox/") and _is_blank_capture(lines):
        path.unlink()
    else:
        _write_lines(path, lines)
    return removed


def delete_task(vault: Path, file: str, line_text: str) -> None:
    _remove_line(vault, file, line_text)


def edit_task(vault: Path, file: str, line_text: str,
               new_text: str | None = None, new_due: str | None = None,
               new_context: str | None = None, new_when: str | None = None) -> str:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    prefix, body = _task_parts(lines[i])
    text, tags, fields, links = _split_body(body)
    if new_text is not None:
        text = new_text.strip()

    if new_due:
        fields["due"] = _dt.date.fromisoformat(new_due).isoformat()
    elif new_due == "":  # an emptied date field means "no due date"
        fields.pop("due", None)

    if new_context:
        ctx_bare = new_context.lstrip("#")
        tags = [t for t in tags if f"#{t}" not in BD.CONTEXTS] + [ctx_bare]

    if new_when is not None:
        tags = _apply_when(tags, fields, new_when, _dt.date.today())

    lines[i] = prefix + _join_body(text, tags, fields, links)
    _write_lines(path, lines)
    return lines[i]


# Keep letters in any script (Hebrew captures used to all become "item.md") — \w is Unicode-aware.
_SLUG_RE = _re.compile(r"[\W_]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "item"


NEXT_ACTIONS = "## Next actions"


def _insert_under_heading(lines: list[str], heading: str, new_line: str) -> list[str]:
    """Add a task at the end of the checkbox run under `heading` (creating the heading if absent)."""
    try:
        h_idx = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        return lines + ["", heading, "", new_line]
    insert_at = h_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    j = insert_at
    while j < len(lines) and lines[j].lstrip().startswith("- ["):
        j += 1
    lines.insert(j, new_line)
    return lines


def _container_path(vault: Path, project: str | None, area: str | None) -> Path:
    if project:
        path = _resolve(vault, f"10 Projects/{project}.md")
        if not path.is_file():
            raise FileNotFoundError(f"project not found: {project}")
        return path
    path = _resolve(vault, f"20 Areas/{area}.md")
    if not path.is_file():
        raise FileNotFoundError(f"area not found: {area}")
    return path


def _write_capture(vault: Path, text_for_name: str, line: str) -> dict:
    today = _dt.date.today().isoformat()
    slug = _slugify(DP._clean_no_links(text_for_name))[:40]
    rel = f"00 Inbox/{today} {slug}.md"
    n = 2
    while (Path(vault) / rel).exists():
        rel = f"00 Inbox/{today} {slug}-{n}.md"
        n += 1
    (Path(vault) / "00 Inbox").mkdir(parents=True, exist_ok=True)
    (Path(vault) / rel).write_text(f"---\ntype: inbox\ncaptured: {today}\n---\n{line}\n", encoding="utf-8")
    return {"file": rel, "line_text": line}


def _place(vault: Path, line: str, project: str | None, area: str | None,
           heading: str | None = None) -> dict:
    """Put a task line in a project or area note (under `heading`, default Next actions), or,
    with neither, capture it to 00 Inbox/ as its own file."""
    if not project and not area:
        return _write_capture(vault, _split_body(_task_parts(line)[1])[0], line)
    path = _container_path(vault, project, area)
    lines = _insert_under_heading(_read_lines(path), f"## {heading}" if heading else NEXT_ACTIONS, line)
    _write_lines(path, lines)
    return {"file": str(path.relative_to(Path(vault).resolve())).replace("\\", "/"), "line_text": line}


def create_task(vault: Path, text: str, context: str | None = "anywhere", project: str | None = None,
                area: str | None = None, when: str | None = None, deadline: str | None = None,
                status: str = "next", heading: str | None = None) -> dict:
    """A new to-do. Tags typed into the text (#phone) are kept; a context is only added when the
    text doesn't already name one. `when` takes the same values as edit_task's new_when."""
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    if project or area:
        _container_path(vault, project, area)  # fail before touching anything
    body_text, tags, fields, links = _split_body(text.strip())
    status = next((t for t in tags if t in STATUSES), status)  # a status typed into the text wins
    tags = [t for t in tags if t not in STATUSES] + [status]
    ctx = (context or "").lstrip("#")
    if ctx and not any(f"#{t}" in BD.CONTEXTS for t in tags):
        tags.append(ctx)
    if status == "waiting":
        fields.setdefault("since", _dt.date.today().isoformat())
    if when:
        tags = _apply_when(tags, fields, when, _dt.date.today())
    if deadline:
        fields["due"] = _dt.date.fromisoformat(deadline).isoformat()
    line = "- [ ] " + _join_body(body_text, tags, fields, links)
    return _place(vault, line, project, area, heading)


def move_task(vault: Path, file: str, line_text: str, project: str | None = None,
              area: str | None = None) -> dict:
    """Things' Quick Move: the line leaves its note and lands under the target project's (or
    area's) Next actions — or back in the inbox, with neither. Moving the last line out of an
    inbox capture removes that capture: the item has been processed."""
    if project or area:
        target = _container_path(vault, project, area)
        if target == _resolve(vault, file):
            return {"file": file, "line_text": line_text}
    elif file.startswith("00 Inbox/"):
        return {"file": file, "line_text": line_text}
    line = _remove_line(vault, file, line_text).strip()
    return _place(vault, line, project, area)


def _update_frontmatter(path: Path, updates: dict) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        text = "---\n---\n" + text
    end = text.find("\n---", 3)
    head, rest = text[3:end].strip("\n").splitlines(), text[end:]
    for key, value in updates.items():
        for i, l in enumerate(head):
            if l.partition(":")[0].strip() == key:
                head[i] = f"{key}: {value}"
                break
        else:
            head.append(f"{key}: {value}")
    path.write_text("---\n" + "\n".join(head) + rest, encoding="utf-8")


def set_project_status(vault: Path, name: str, status: str) -> None:
    """active | someday | done — Complete Project, or move it to/from Someday."""
    if status not in ("active", "someday", "done"):
        raise ValueError(f"unknown project status: {status}")
    path = _container_path(vault, name, None)
    updates = {"status": status}
    if status == "done":
        updates["completed"] = _dt.date.today().isoformat()
    _update_frontmatter(path, updates)


def mark_project_reviewed(vault: Path, name: str, days: int = 7) -> str:
    """Push the project's next review out `days` from today; returns the new review date."""
    nxt = (_dt.date.today() + _dt.timedelta(days=days)).isoformat()
    _update_frontmatter(_container_path(vault, name, None), {"review": nxt})
    return nxt


def create_project(vault: Path, title: str, area: str | None = None) -> str:
    vault = Path(vault)
    template = (vault / "_templates" / "Project.md").read_text(encoding="utf-8")
    today = _dt.date.today().isoformat()
    content = template.replace("{{title}}", title)
    content = _re.sub(r"\{\{date:YYYY-MM-DD\}\}", today, content)
    if area:
        content = _re.sub(r"(?m)^area:.*$", f'area: "[[{area}]]"', content, count=1)
    dest = _resolve(vault, f"10 Projects/{title}.md")
    if dest.exists():
        raise FileExistsError(f"project already exists: {title}")
    dest.write_text(content, encoding="utf-8")
    if area and "area:" not in content:
        _update_frontmatter(dest, {"area": f'"[[{area}]]"'})
    return str(dest.relative_to(Path(vault).resolve())).replace("\\", "/")


RECORDINGS_DIR = "Meetings/recordings"
SAMPLE_RATE = 16000
_UNSAFE_NAME_RE = _re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]+')
_TRANSCRIBE_LOCK = _threading.Lock()


def _one_line(s: str | None) -> str:
    return " ".join((s or "").split())


def _safe_title(title: str | None) -> str:
    """A meeting title usable as (part of) a file name on Windows and in Obsidian links."""
    t = _one_line(_UNSAFE_NAME_RE.sub(" ", title or "")).strip(".")
    return t[:80].strip() or "Meeting"


def meeting_note_content(date_str: str, recording_rel: str, heading: str, attendees: str = "") -> str:
    """Same note the record-meeting Obsidian plugin writes (.obsidian/plugins/record-meeting/lib.js
    meetingNoteContent), plus a real heading/attendees when the recording came from a calendar event."""
    return (
        "---\n"
        "type: meeting\n"
        f"date: {date_str}\n"
        f"attendees: {_json.dumps(attendees, ensure_ascii=False) if attendees else ''}\n"
        f'recording: "[[{recording_rel}]]"\n'
        "transcription_status: pending\n"
        "---\n\n"
        f"# {heading}\n\n"
        f"**Date:** {date_str}\n"
        f"**Attendees:** {attendees}\n\n"
        "## Notes\n\n"
        "## Decisions\n\n"
        "## Transcript\n\n"
        "## Action items\n- [ ]  #next\n"
    )


def save_meeting_recording(vault: Path, pcm16: bytes, started: _dt.datetime, title: str | None = None,
                           attendees: str = "", sample_rate: int = SAMPLE_RATE) -> dict:
    """Write mono 16-bit PCM as Meetings/recordings/<stamp>.wav plus a linked meeting note with
    transcription_status: pending — exactly what the transcription script picks up."""
    if not pcm16:
        raise ValueError("empty recording")
    if len(pcm16) % 2:
        pcm16 = pcm16[:-1]
    vault = Path(vault)
    slug = started.strftime("%Y-%m-%d_%H-%M-%S")
    rec_rel, n = f"{RECORDINGS_DIR}/{slug}.wav", 2
    while _resolve(vault, rec_rel).exists():
        rec_rel, n = f"{RECORDINGS_DIR}/{slug}-{n}.wav", n + 1
    rec_path = _resolve(vault, rec_rel)
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    with _wave.open(str(rec_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16)

    name = _safe_title(title)
    note_rel, n = f"Meetings/{slug} {name}.md", 2
    while _resolve(vault, note_rel).exists():
        note_rel, n = f"Meetings/{slug} {name} {n}.md", n + 1
    date_str = started.date().isoformat()
    heading = _one_line(title) or f"Meeting {date_str}"
    _resolve(vault, note_rel).write_text(
        meeting_note_content(date_str, rec_rel, heading, _one_line(attendees)), encoding="utf-8")
    return {"note": note_rel, "recording": rec_rel}


def run_transcription(vault: Path) -> str:
    # one run at a time: two concurrent runs would both pick up the same pending note
    with _TRANSCRIBE_LOCK:
        vault = Path(vault)
        script = Path(__file__).resolve().parent / "transcribe_meetings.py"
        result = _subprocess.run(
            [_sys.executable, str(script), str(vault)],
            capture_output=True, text=True, timeout=1800,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "transcription failed")
    return result.stdout.strip()


def start_background_transcription(vault: Path) -> _threading.Thread:
    """Transcribe pending recordings without making the caller wait (a meeting can take minutes)."""
    def work():
        try:
            run_transcription(vault)
        except Exception as e:  # noqa: BLE001 - per-note failures are written into the note itself
            print(f"background transcription failed: {e}", file=_sys.stderr)
    t = _threading.Thread(target=work, daemon=True, name="transcribe")
    t.start()
    return t
