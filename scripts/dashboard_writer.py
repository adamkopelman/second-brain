#!/usr/bin/env python3
"""Write-back operations for the local dashboard server. stdlib only."""
from __future__ import annotations
import datetime as _dt
import re as _re
import subprocess as _subprocess
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard as BD


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
    text = new_text.strip() if new_text is not None else BD._clean(body)

    if new_due is not None:
        fields["due"] = new_due

    if new_context is not None:
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


_SLUG_RE = _re.compile(r"[^a-z0-9]+")


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


def run_transcription(vault: Path) -> str:
    vault = Path(vault)
    script = Path(__file__).resolve().parent / "transcribe_meetings.py"
    result = _subprocess.run(
        [_sys.executable, str(script), str(vault)],
        capture_output=True, text=True, timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "transcription failed")
    return result.stdout.strip()
