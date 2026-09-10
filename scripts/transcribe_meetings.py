#!/usr/bin/env python3
"""Transcribe pending meeting recordings. Mechanical only — stdlib only.

Summarization and action-item extraction happen separately, in Claude Code (see the
`gtd-summarize-meetings` skill) — a regex can't read Hebrew or unstructured speech, so this script's
job stops at getting a transcript into the note.
"""
from __future__ import annotations
import argparse, datetime as _dt, json, re, subprocess, sys, tempfile, urllib.request
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

PENDING_SUMMARY_NOTE = (
    "_Pending summary — run /gtd-transcribe-meeting or /gtd-summarize-meetings in Claude Code._"
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        fm_m = FIELD_RE.match(line)
        if fm_m:
            fm[fm_m.group(1)] = fm_m.group(2).strip()
    return fm, m.group(2)


def render_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Returns (raw frontmatter block contents without the --- delimiters, or None if no
    frontmatter, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def _join_frontmatter(raw: str | None, body: str) -> str:
    if raw is None:
        return body
    return f"---\n{raw}\n---\n{body}"


def set_frontmatter_fields(text: str, **updates: str) -> str:
    """Set/replace the given top-level scalar frontmatter keys, preserving every other line
    (including YAML block lists, comments, blank lines) byte-for-byte. Appends keys that don't
    already exist."""
    raw, body = _split_frontmatter(text)
    lines = raw.splitlines() if raw else []
    remaining = dict(updates)
    out_lines = []
    for line in lines:
        m = FIELD_RE.match(line)
        if m and m.group(1) in remaining:
            out_lines.append(f"{m.group(1)}: {remaining.pop(m.group(1))}")
        else:
            out_lines.append(line)
    for k, v in remaining.items():
        out_lines.append(f"{k}: {v}")
    new_raw = "\n".join(out_lines)
    return _join_frontmatter(new_raw, body)


def find_pending(vault: Path) -> list[Path]:
    meetings = vault / "Meetings"
    if not meetings.is_dir():
        return []
    out = []
    for p in sorted(meetings.glob("*.md")):
        if p.name == "README.md":
            continue
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        if fm.get("transcription_status") == "pending":
            out.append(p)
    return out


def resolve_recording(vault: Path, fm: dict) -> Path | None:
    raw = fm.get("recording", "")
    m = WIKILINK_RE.search(raw)
    rel = m.group(1) if m else raw.strip()
    if not rel:
        return None
    p = vault / rel
    return p if p.is_file() else None


def transcribe_local(wav: Path, whisper_bin: Path, model: Path) -> str:
    with tempfile.TemporaryDirectory() as td:
        out_base = Path(td) / "out"
        subprocess.run(
            [str(whisper_bin), "-m", str(model), "-f", str(wav),
             "-oj", "-of", str(out_base), "-np", "-l", "auto"],
            check=True, capture_output=True, timeout=1800,
        )
        data = json.loads(out_base.with_suffix(".json").read_text(encoding="utf-8"))
    segments = data.get("transcription", [])
    return " ".join(s.get("text", "").strip() for s in segments).strip()


def transcribe_remote(wav: Path, url: str, api_key: str | None) -> str:
    boundary = "----wsboundary"
    parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n',
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{wav.name}"\r\n'.encode(),
        b"Content-Type: audio/wav\r\n\r\n",
        wav.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    payload = b"".join(parts)
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("text", "").strip()


def _replace_section(body: str, heading: str, content: str) -> str:
    pattern = re.compile(rf"{re.escape(heading)}\n.*?(?=\n## |\Z)", re.DOTALL)
    replacement = f"{heading}\n{content}\n"
    if pattern.search(body):
        return pattern.sub(replacement, body)
    return body + f"\n{replacement}"


def apply_transcript(note_text: str, transcript: str, note_stem: str) -> str:
    _, body = parse_frontmatter(note_text)

    transcript_block = transcript if transcript else "_No speech detected._"
    body = _replace_section(body, "## Transcript", transcript_block)
    body = _replace_section(body, "## Action items", PENDING_SUMMARY_NOTE)

    raw, _ = _split_frontmatter(note_text)
    joined = _join_frontmatter(raw, body)
    return set_frontmatter_fields(
        joined,
        transcription_status="done",
        transcribed=_dt.date.today().isoformat(),
        summary_status="pending",
    )


def mark_failed(note_text: str, reason: str) -> str:
    _, body = parse_frontmatter(note_text)
    body += f"\n> [!fail] Transcription failed: {reason}\n"
    raw, _ = _split_frontmatter(note_text)
    joined = _join_frontmatter(raw, body)
    return set_frontmatter_fields(joined, transcription_status="failed")


def process(vault: Path, whisper_bin: Path, model: Path, remote_url: str | None,
            api_key: str | None) -> list[str]:
    results = []
    for note_path in find_pending(vault):
        note_text = note_path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(note_text)
        wav = resolve_recording(vault, fm)
        if wav is None:
            note_path.write_text(mark_failed(note_text, "recording file not found"), encoding="utf-8")
            results.append(f"FAILED (no recording): {note_path.name}")
            continue
        try:
            transcript = (transcribe_remote(wav, remote_url, api_key) if remote_url
                          else transcribe_local(wav, whisper_bin, model))
        except Exception as e:  # noqa: BLE001 - report any failure into the note, don't crash the batch
            note_path.write_text(mark_failed(note_text, str(e)), encoding="utf-8")
            results.append(f"FAILED ({e}): {note_path.name}")
            continue
        note_path.write_text(apply_transcript(note_text, transcript, note_path.stem), encoding="utf-8")
        results.append(f"OK (transcribed): {note_path.name}")
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", nargs="?", default=".", help="Path to the vault root")
    ap.add_argument("--whisper-bin", default=None, help="Path to whisper-cli(.exe)")
    ap.add_argument("--model", default=None, help="Path to a ggml .bin model")
    ap.add_argument("--remote-url", default=None,
                     help="OpenAI-compatible /v1/audio/transcriptions URL; if set, skips local whisper")
    ap.add_argument("--api-key", default=None, help="Bearer token for --remote-url")
    args = ap.parse_args(argv)

    vault = Path(args.vault).resolve()
    whisper_bin = (Path(args.whisper_bin) if args.whisper_bin
                   else vault / "vendor" / "whisper-cpp" / "whisper-cli.exe")
    model = (Path(args.model) if args.model
             else vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.bin")

    if not args.remote_url and not whisper_bin.is_file():
        print(f"error: whisper binary not found at {whisper_bin} "
              "(pass --remote-url to use a remote model instead)", file=sys.stderr)
        return 1

    results = process(vault, whisper_bin, model, args.remote_url, args.api_key)
    if not results:
        print("No pending meeting recordings.")
        return 0
    for r in results:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
