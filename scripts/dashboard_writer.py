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


def complete_task(vault: Path, file: str, line_text: str) -> None:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    lines[i] = _re.sub(r"^(\s*-\s*\[)[ ](\].*)$", r"\1x\2", lines[i], count=1)
    _write_lines(path, lines)


def delete_task(vault: Path, file: str, line_text: str) -> None:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    del lines[i]
    _write_lines(path, lines)


def edit_task(vault: Path, file: str, line_text: str,
               new_text: str | None = None, new_due: str | None = None,
               new_context: str | None = None) -> str:
    path = _resolve(vault, file)
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    m = _re.match(r"^(\s*-\s*\[[ xX]\]\s*)(.*)$", lines[i])
    if not m:
        raise LineNotFoundError(f"not a task checkbox line: {lines[i]!r}")
    prefix, body = m.group(1), m.group(2)

    tags = BD.TAG_RE.findall(body)
    fields = dict(BD.FIELD_RE.findall(body))
    links = BD.LINK_RE.findall(body)
    text = new_text.strip() if new_text is not None else DP._clean_no_links(body)

    if new_due:
        fields["due"] = new_due
    elif new_due == "":  # an emptied date field means "no due date"
        fields.pop("due", None)

    if new_context:
        ctx_bare = new_context.lstrip("#")
        tags = [t for t in tags if f"#{t}" not in BD.CONTEXTS] + [ctx_bare]

    parts = [text]
    parts += [f"#{t}" for t in tags]
    parts += [f"[{k}:: {v}]" for k, v in fields.items()]
    parts += [f"[[{l}]]" for l in links]
    new_body = " ".join(p for p in parts if p)
    lines[i] = prefix + new_body
    _write_lines(path, lines)
    return lines[i]


# Keep letters in any script (Hebrew captures used to all become "item.md") — \w is Unicode-aware.
_SLUG_RE = _re.compile(r"[\W_]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "item"


def create_task(vault: Path, text: str, context: str, project: str | None = None) -> dict:
    vault = Path(vault)
    today = _dt.date.today().isoformat()
    ctx = context if context.startswith("#") else f"#{context}"

    if not project:
        slug = _slugify(text)[:40]
        rel = f"00 Inbox/{today} {slug}.md"
        path = vault / rel
        n = 2
        while path.exists():
            rel = f"00 Inbox/{today} {slug}-{n}.md"
            path = vault / rel
            n += 1
        line_text = f"- [ ] {text} #next {ctx}"
        content = f"---\ntype: inbox\ncaptured: {today}\n---\n{line_text}\n"
        path.write_text(content, encoding="utf-8")
        return {"file": rel, "line_text": line_text}

    proj_path = _resolve(vault, f"10 Projects/{project}.md")
    if not proj_path.is_file():
        raise FileNotFoundError(f"project not found: {project}")
    lines = _read_lines(proj_path)
    new_line = f"- [ ] {text} #next {ctx}"
    heading = "## Next actions"
    try:
        h_idx = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        lines = lines + ["", heading, "", new_line]
    else:
        insert_at = h_idx + 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
        j = insert_at
        while j < len(lines) and lines[j].lstrip().startswith("- ["):
            j += 1
        lines.insert(j, new_line)
    _write_lines(proj_path, lines)
    rel = str(proj_path.relative_to(vault)).replace("\\", "/")
    return {"file": rel, "line_text": new_line}


def create_project(vault: Path, title: str) -> str:
    vault = Path(vault)
    template = (vault / "_templates" / "Project.md").read_text(encoding="utf-8")
    today = _dt.date.today().isoformat()
    content = template.replace("{{title}}", title)
    content = _re.sub(r"\{\{date:YYYY-MM-DD\}\}", today, content)
    dest = _resolve(vault, f"10 Projects/{title}.md")
    if dest.exists():
        raise FileExistsError(f"project already exists: {title}")
    dest.write_text(content, encoding="utf-8")
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
