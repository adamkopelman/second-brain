# Meeting Feature ↔ Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken Hebrew/multilingual meeting transcription, split the meeting pipeline into a
mechanical transcription stage and a Claude-Code-only summarization stage, and wire meetings into the
local dashboard server (meeting-sourced tasks, a "Needs triage" card for `#unknown` context, a
Meetings card with a transcribe button).

**Architecture:** `scripts/transcribe_meetings.py` becomes purely mechanical (vendors a multilingual
Whisper model, drops English-only action-item regex extraction). A new Claude-Code skill
`gtd-summarize-meetings` owns all real summarization/context-inference, callable standalone
(scheduler-safe) or via the updated `gtd-transcribe-meeting` skill. `dashboard_parser.py`/
`dashboard_writer.py`/`dashboard_server.py` gain a `meeting` field on tasks, a `meetings` list, an
editable-context write path, and a transcribe endpoint; `logic.js`/`index.html`/`app.js`/`style.css`
render two new cards and an editable context `<select>` in the task detail overlay.

**Tech Stack:** Python 3 stdlib only (backend), vanilla JS with a dual CommonJS/browser export pattern
(frontend, `node --test` for pure-function coverage), Markdown prompt files (Claude Code skills, no
automated test harness — same as every other skill in this vault).

**Spec:** `docs/superpowers/specs/2026-09-10-meeting-dashboard-integration-design.md`

## Global Constraints

- Vendor the multilingual model from `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin`
  at `vendor/whisper-cpp/models/ggml-tiny.bin` — expect exactly 77,691,713 bytes and sha256
  `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`; remove
  `vendor/whisper-cpp/models/ggml-tiny.en.bin`.
- `transcribe_local`'s whisper-cli invocation changes `-l en` → `-l auto` (per-recording language
  auto-detection, not translation).
- Python: stdlib only, no new dependencies. Every vault-facing filesystem write still goes through the
  existing exact-line-match safety model in `dashboard_writer.py` (re-read, match by current text, else
  refuse) — `edit_task`'s new `new_context` parameter must not weaken that.
- JS: `scripts/dashboard_static/logic.js` stays pure (no DOM, no fetch) and keeps the dual
  `module.exports` / `window.DashboardLogic` export so it runs unchanged under both `node --test` and
  the browser. `app.js` stays the thin, deliberately-untested DOM-wiring layer.
- No dashboard-side audio recording, no changes to the `record-meeting` Obsidian plugin itself, and no
  translation of transcripts or summaries anywhere in this plan.
- No meeting-detail overlay — a meeting pill/link opens the note directly in Obsidian
  (`obsidian://open?path=...`), the same mechanism project links already use to build their href, but
  without going through the app's own detail modal (there is no meeting equivalent of it).
- Not setting up the actual recurring 2-hour schedule for `gtd-summarize-meetings` — that's the user's
  own follow-up step once this plan lands.
- `gtd-setup`'s scaffold (`​.claude/skills/gtd-setup/scaffold/vault/`) must mirror every vault-facing
  template change made in this plan (root `_templates/Meeting.md`), including restoring fields the
  scaffold copy had already drifted out of sync on before this session.
- Test commands used throughout this plan: `python -m pytest scripts/tests/ -v` and
  `node --test scripts/dashboard_static/logic.test.js`. Baseline before Task 1: 49 Python tests, 13 JS
  tests, all passing.

---

### Task 1: Multilingual Whisper model + mechanical-only `transcribe_meetings.py`

**Files:**
- Modify: `vendor/whisper-cpp/models/ggml-tiny.en.bin` (delete), add
  `vendor/whisper-cpp/models/ggml-tiny.bin` (new binary, vendored fresh by you in this task)
- Modify: `vendor/whisper-cpp/README.md`
- Modify: `scripts/transcribe_meetings.py`
- Modify (test): `scripts/tests/test_transcribe_meetings.py`

**Interfaces:**
- Produces: `transcribe_meetings.apply_transcript(note_text: str, transcript: str, note_stem: str) -> str`
  (drops the `action_items` parameter that existed before this task — every later task/skill that
  talks about this script assumes this 3-arg signature and the `summary_status: pending` frontmatter
  field it now sets).
- Produces: `transcribe_meetings.PENDING_SUMMARY_NOTE` constant — the exact placeholder text written
  into `## Action items` (`"_Pending summary — run /gtd-transcribe-meeting or /gtd-summarize-meetings
  in Claude Code._"`). Task 8's skill prose references this placeholder text; keep them in sync if you
  change it.
- Produces: `transcribe_meetings.process(...)` per-note result strings now read
  `"OK (transcribed): {name}"` instead of `"OK ({N} action item(s)): {name}"`.
- Consumes: nothing from other tasks (this task is independent — do it first since the model file is a
  large, deliberate binary swap worth landing on its own).

- [ ] **Step 1: Download and verify the multilingual model**

Run (from the repo root):

```bash
python -c "import urllib.request; urllib.request.urlretrieve('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin', 'vendor/whisper-cpp/models/ggml-tiny.bin')"
python -c "
import hashlib, pathlib
p = pathlib.Path('vendor/whisper-cpp/models/ggml-tiny.bin')
data = p.read_bytes()
print('size:', len(data))
print('sha256:', hashlib.sha256(data).hexdigest())
"
```

Expected: `size: 77691713` and
`sha256: be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`. If either doesn't match,
stop and re-download — do not proceed with a file that doesn't match (this is a binary committed
straight into git, not something a later step can quietly patch).

- [ ] **Step 2: Remove the old English-only model**

```bash
git rm vendor/whisper-cpp/models/ggml-tiny.en.bin
git add vendor/whisper-cpp/models/ggml-tiny.bin
```

- [ ] **Step 3: Update `vendor/whisper-cpp/README.md`**

Replace the file's full contents with:

```markdown
# Vendored: whisper.cpp (Windows x64 CPU build)

Local, fully-offline speech-to-text used by `scripts/transcribe_meetings.py` (and, through it, the
`record-meeting` Obsidian plugin and the `gtd-transcribe-meeting` skill). Committed so the vault is
self-contained for air-gapped machines — no `pip install openai-whisper`, no network, no ffmpeg.

- **Source:** https://github.com/ggml-org/whisper.cpp (release `b4938`, CPU-only Windows x64 build:
  `whisper-bin-x64.zip`)
- **Model:** https://huggingface.co/ggerganov/whisper.cpp `ggml-tiny.bin` (~74MB, **multilingual** —
  swapped in for `ggml-tiny.en.bin` because the vault's real meetings are usually in Hebrew, which an
  English-only model architecturally cannot transcribe; still well under GitHub's 100MB hard
  file-size limit, so no Git LFS needed).
- **Files:** `whisper-cli.exe` + `whisper.dll`, `ggml.dll`, `ggml-base.dll`, and all `ggml-cpu-*.dll`
  variants (the exe auto-detects the running CPU's feature set and loads the matching one — keep all
  of them since the machine this runs on may differ from the machine that vendored these files).
  `SDL2.dll`/`llama.dll`/`parakeet*` from the same release zip are unrelated demo-tool dependencies
  and were intentionally **not** vendored.
- **Platform:** Windows x86-64 only. `scripts/transcribe_meetings.py` fails clearly (not silently) if
  `--remote-url` isn't given and this binary isn't present/runnable — see that script's `main()`.
- **sha256 (whisper-cli.exe):** `800a0fd754afa75e109c7248286ad735670fb6b23d92ca5d12604647ef638a65`
- **sha256 (ggml-tiny.bin):** `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`
- **Usage:** `whisper-cli.exe -m models/ggml-tiny.bin -f <audio> -oj -of <out> -np -l auto` —
  `-l auto` asks whisper.cpp to detect each recording's language itself, rather than assuming
  English — see `scripts/transcribe_meetings.py::transcribe_local` for the exact invocation.
- **Updating:** download a newer `whisper-bin-x64.zip` from
  https://github.com/ggml-org/whisper.cpp/releases and repeat the file list above; swap the model for
  a different `ggml-*.bin` from https://huggingface.co/ggerganov/whisper.cpp if you want better
  accuracy and don't mind a bigger repo (anything ≤~95MB is still LFS-free) — keep it a multilingual
  variant (not an `.en` one) unless every meeting recorded in this vault is guaranteed English.
```

- [ ] **Step 4: Write/update the failing tests first**

Edit `scripts/tests/test_transcribe_meetings.py`:

1. Add `import json` to the top import block (needed by the new test in this step):

```python
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transcribe_meetings as T
```

2. Delete these two tests entirely (the function they test no longer exists after Step 5):
   `test_extract_action_items_matches_action_cues`, `test_extract_action_items_dedupes_and_caps`.

3. Replace `test_apply_transcript_fills_sections_and_marks_done` with:

```python
def test_apply_transcript_fills_sections_and_marks_done():
    note_text = (
        "---\ntranscription_status: pending\nrecording: \"[[x.wav]]\"\n---\n"
        "# Meeting\n\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    )
    out = T.apply_transcript(note_text, "Hello world.", "My Meeting")
    fm, body = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "done"
    assert fm["summary_status"] == "pending"
    assert "transcribed" in fm
    assert "Hello world." in body
    assert T.PENDING_SUMMARY_NOTE in body
```

4. Replace `test_apply_transcript_with_no_action_items_leaves_review_note` with:

```python
def test_apply_transcript_always_leaves_pending_summary_placeholder():
    note_text = "---\ntranscription_status: pending\n---\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    out = T.apply_transcript(note_text, "Nothing actionable here.", "Stem")
    assert T.PENDING_SUMMARY_NOTE in out
```

5. In `test_apply_transcript_preserves_yaml_list_frontmatter`, change the call from
   `T.apply_transcript(note_text, "Hello world.", [], "Stem")` to
   `T.apply_transcript(note_text, "Hello world.", "Stem")`, and add
   `assert fm["summary_status"] == "pending"` next to the existing
   `assert fm["transcription_status"] == "done"` line.

6. In `test_process_marks_failed_when_recording_missing`, change the model-path argument from
   `vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.en.bin"` to
   `vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.bin"`.

7. Replace `test_process_uses_transcribe_local_and_updates_note` with:

```python
def test_process_uses_transcribe_local_and_updates_note(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_local", lambda wav, b, m: "I'll email the vendor tomorrow.")
    results = T.process(vault, Path("fake-bin"), Path("fake-model"), None, None)
    assert len(results) == 1
    assert results[0] == "OK (transcribed): 2026-09-10_10-00-00 Meeting.md"
    note_text = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "I'll email the vendor tomorrow." in note_text
    assert T.PENDING_SUMMARY_NOTE in note_text
```

8. In `test_real_vendored_whisper_binary_runs`, change the model line from
   `model = repo_root / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.en.bin"` to
   `model = repo_root / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.bin"`.

9. Add this new test at the end of the file (it locks in the `-l auto` fix — the whole point of this
   task):

```python
def test_transcribe_local_passes_auto_language_not_english(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out_base = Path(cmd[cmd.index("-of") + 1])
        out_base.with_suffix(".json").write_text(
            json.dumps({"transcription": [{"text": "Shalom"}]}), encoding="utf-8"
        )
        class Result:
            pass
        return Result()

    monkeypatch.setattr(T.subprocess, "run", fake_run)
    text = T.transcribe_local(tmp_path / "a.wav", Path("whisper-cli"), Path("model.bin"))
    assert text == "Shalom"
    assert captured["cmd"][captured["cmd"].index("-l") + 1] == "auto"
```

- [ ] **Step 5: Run the tests to see the expected failures**

Run: `python -m pytest scripts/tests/test_transcribe_meetings.py -v`
Expected: several FAIL (missing `T.PENDING_SUMMARY_NOTE`, `apply_transcript` still requires 4
positional args, `-l en` still hardcoded, etc.) — this confirms the tests are exercising real behavior
before you change the implementation.

- [ ] **Step 6: Rewrite `scripts/transcribe_meetings.py` to be mechanical-only**

Replace the file's full contents with:

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_transcribe_meetings.py -v`
Expected: all PASS (the `test_real_vendored_whisper_binary_runs` test only runs on Windows and only if
the vendored binary/model are present — both are true after Steps 1-2, so it should actually execute
here, not skip).

- [ ] **Step 8: Run the full Python suite to check for regressions**

Run: `python -m pytest scripts/tests/ -v`
Expected: all PASS (49 pre-existing + the net new/changed tests in this task).

- [ ] **Step 9: Commit**

```bash
git add vendor/whisper-cpp/models/ggml-tiny.bin vendor/whisper-cpp/README.md \
        scripts/transcribe_meetings.py scripts/tests/test_transcribe_meetings.py
git commit -m "fix(meetings): vendor multilingual Whisper model, make transcription mechanical-only

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

(the `git rm` from Step 2 is already staged; this commit captures it together with the new model file)

---

### Task 2: Templates & scaffold sync

**Files:**
- Modify: `_templates/Meeting.md`
- Modify: `.claude/skills/gtd-setup/scaffold/vault/_templates/Meeting.md`

**Interfaces:**
- Produces: both files carry identical frontmatter fields (`type`, `date`, `attendees`, `recording`,
  `transcription_status`, `summary_status`) and section headings (`## Notes`, `## Decisions`,
  `## Transcript`, `## Action items`) — this is what makes `record-meeting`'s note-creation and
  `transcribe_meetings.py`'s section-replace logic (Task 1) work the same whether a vault came from a
  fresh `gtd-setup` scaffold or has just been used directly.
- Consumes: nothing (pure content files, no code dependency on other tasks — safe to do any time, but
  ordered right after Task 1 since it's the other meeting-frontmatter change in this plan).

No automated test exists for scaffold-root sync (there's no test harness for template content in this
repo) — this task is a direct content match, not TDD.

- [ ] **Step 1: Update `_templates/Meeting.md`**

Replace the file's full contents with:

```
---
type: meeting
date: {{date:YYYY-MM-DD}}
attendees: 
recording: 
transcription_status: 
summary_status: 
---

# {{title}}

**Date:** {{date:YYYY-MM-DD}}
**Attendees:** 

## Notes

## Decisions

## Transcript

## Action items
- [ ]  #next
```

- [ ] **Step 2: Replace the scaffold copy to match root exactly**

Replace the full contents of `.claude/skills/gtd-setup/scaffold/vault/_templates/Meeting.md` with the
exact same content as Step 1 (this also restores the `recording`/`transcription_status` fields and the
`## Transcript` section the scaffold copy was already missing before this session's other meeting
work — it had drifted out of sync with root).

- [ ] **Step 3: Verify the two files are byte-identical**

Run:

```bash
diff "_templates/Meeting.md" ".claude/skills/gtd-setup/scaffold/vault/_templates/Meeting.md"
```

Expected: no output (files identical).

- [ ] **Step 4: Commit**

```bash
git add "_templates/Meeting.md" ".claude/skills/gtd-setup/scaffold/vault/_templates/Meeting.md"
git commit -m "fix(gtd-setup): restore and sync Meeting.md template, add summary_status field

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 3: `dashboard_parser.py` — `#unknown` context, `meeting` field, `meetings` list

**Files:**
- Modify: `scripts/build_dashboard.py`
- Modify: `scripts/dashboard_parser.py`
- Modify (test): `scripts/tests/test_dashboard_parser.py`

**Interfaces:**
- Produces: `build_dashboard.CONTEXTS` gains `"#unknown"` as its 8th entry.
- Produces: `iter_tasks_with_location()` yields a `"meeting"` key on every task dict — the meeting
  note's filename stem (e.g. `"2026-09-10_10-00-00 Meeting"`) when the task lives under `Meetings/`,
  else `None`. Parallel to the existing `"project"` key.
- Produces: `collect_state()`'s task entries (in `tasks_by_context`, and `waiting`) each carry a
  `"meeting"` key, same semantics.
- Produces: `collect_state()`'s return dict gains a `"meetings"` key: a list of
  `{"name": str, "file": str, "date": str | None, "transcription_status": str | None,
  "summary_status": str | None}` dicts, one per `Meetings/*.md` note (excluding `README.md`,
  non-recursive so `Meetings/recordings/*.wav` is never touched), sorted newest-first by `date`,
  capped at 8 entries.
- Consumes: nothing from other tasks — this can run any time after Task 1/2, and Task 4
  (`dashboard_writer.py`) depends on `build_dashboard.CONTEXTS` already including `"#unknown"`, so this
  task must land before Task 4.

- [ ] **Step 1: Write the failing tests**

Add these three tests to the end of `scripts/tests/test_dashboard_parser.py`:

```python
def test_iter_tasks_with_location_tags_meeting_source(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "2026-09-10 Sync.md").write_text(
        "---\ntype: meeting\ndate: 2026-09-10\ntranscription_status: done\nsummary_status: done\n---\n"
        "# Sync\n\n## Action items\n- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]\n")
    tasks = list(P.iter_tasks_with_location(tmp_path))
    from_meeting = next(t for t in tasks if "Email the vendor" in t["text"])
    assert from_meeting["meeting"] == "2026-09-10 Sync"
    assert from_meeting["project"] is None
    wireframe = next(t for t in tasks if "wireframe" in t["text"])
    assert wireframe["meeting"] is None

def test_collect_state_threads_meeting_field_and_unknown_context(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "2026-09-10 Sync.md").write_text(
        "---\ntype: meeting\ndate: 2026-09-10\ntranscription_status: done\nsummary_status: done\n---\n"
        "# Sync\n\n## Action items\n- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]\n")
    state = P.collect_state(tmp_path)
    assert len(state["tasks_by_context"]["#unknown"]) == 1
    task = state["tasks_by_context"]["#unknown"][0]
    assert task["meeting"] == "2026-09-10 Sync"
    assert task["project"] is None

def test_collect_state_lists_recent_meetings_newest_first_capped(tmp_path):
    (tmp_path / "Meetings").mkdir(parents=True)
    (tmp_path / "Meetings" / "README.md").write_text("# Meetings\n")
    for i in range(10):
        (tmp_path / "Meetings" / f"m{i}.md").write_text(
            f"---\ntype: meeting\ndate: 2026-09-{i+1:02d}\n"
            f"transcription_status: done\nsummary_status: pending\n---\n# m{i}\n")
    state = P.collect_state(tmp_path)
    assert len(state["meetings"]) == 8
    assert state["meetings"][0]["date"] == "2026-09-10"
    assert state["meetings"][0]["transcription_status"] == "done"
    assert state["meetings"][0]["summary_status"] == "pending"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_dashboard_parser.py -v`
Expected: the three new tests FAIL (`KeyError: 'meeting'` / `KeyError: '#unknown'` / `KeyError:
'meetings'`).

- [ ] **Step 3: Add `#unknown` to `build_dashboard.CONTEXTS`**

In `scripts/build_dashboard.py`, change:

```python
CONTEXTS = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"]
```

to:

```python
CONTEXTS = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda", "#unknown"]
```

- [ ] **Step 4: Thread the `meeting` field through `dashboard_parser.py`**

In `scripts/dashboard_parser.py`, in `iter_tasks_with_location`, change the `yield` block from:

```python
                yield {
                    "file": rel,
                    "line_text": raw_line.rstrip(),
                    "done": m.group("m").lower() == "x",
                    "text": BD._clean(body),
                    "tags": tags,
                    "fields": fields,
                    "project": p.stem if d == "10 Projects" else None,
                }
```

to:

```python
                yield {
                    "file": rel,
                    "line_text": raw_line.rstrip(),
                    "done": m.group("m").lower() == "x",
                    "text": BD._clean(body),
                    "tags": tags,
                    "fields": fields,
                    "project": p.stem if d == "10 Projects" else None,
                    "meeting": p.stem if d == "Meetings" else None,
                }
```

- [ ] **Step 5: Thread `meeting` through `collect_state`'s task entries and add the `meetings` list**

In `collect_state`, change the `waiting.append` block from:

```python
        if "#waiting" in tags:
            waiting.append({
                "text": t["text"], "file": t["file"], "line_text": t["line_text"],
                "project": t["project"], "since": fields.get("since"),
            })
            continue
```

to:

```python
        if "#waiting" in tags:
            waiting.append({
                "text": t["text"], "file": t["file"], "line_text": t["line_text"],
                "project": t["project"], "meeting": t["meeting"], "since": fields.get("since"),
            })
            continue
```

Change the `entry = {...}` block from:

```python
        entry = {
            "text": t["text"], "file": t["file"], "line_text": t["line_text"],
            "project": t["project"], "context": ctx, "due": due,
        }
```

to:

```python
        entry = {
            "text": t["text"], "file": t["file"], "line_text": t["line_text"],
            "project": t["project"], "meeting": t["meeting"], "context": ctx, "due": due,
        }
```

Then, right before the final `return {...}` statement, add:

```python
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
```

And change the `return` statement from:

```python
    return {
        "inbox_count": inbox_count,
        "tasks_by_context": tasks_by_context,
        "waiting": waiting,
        "due_soon": due_soon,
        "active_projects": active_projects,
        "someday_projects": someday_projects,
    }
```

to:

```python
    return {
        "inbox_count": inbox_count,
        "tasks_by_context": tasks_by_context,
        "waiting": waiting,
        "due_soon": due_soon,
        "active_projects": active_projects,
        "someday_projects": someday_projects,
        "meetings": meetings,
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_dashboard_parser.py -v`
Expected: all PASS.

- [ ] **Step 7: Run the full Python suite to check for regressions**

Run: `python -m pytest scripts/tests/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_dashboard.py scripts/dashboard_parser.py scripts/tests/test_dashboard_parser.py
git commit -m "feat(dashboard): add #unknown context, meeting field, and meetings list to parser

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 4: `dashboard_writer.py` — editable context, `run_transcription`

**Files:**
- Modify: `scripts/dashboard_writer.py`
- Modify (test): `scripts/tests/test_dashboard_writer.py`

**Interfaces:**
- Produces: `edit_task(vault, file, line_text, new_text=None, new_due=None, new_context=None) -> str`
  — when `new_context` is given, any existing tag that is itself a member of `BD.CONTEXTS` (e.g.
  `#computer`, `#unknown`) is stripped from the rebuilt line and the new context tag is appended;
  non-context tags (`#next`, `#waiting`, ...) are untouched. Task 5 (`dashboard_server.py`) calls this
  with `data.get("new_context")` passed straight through.
- Produces: `run_transcription(vault: Path) -> str` — runs `scripts/transcribe_meetings.py <vault>` as
  a subprocess via `sys.executable` (same script the Obsidian plugin already shells out to) and
  returns its stdout, raising `RuntimeError` on a nonzero exit (`subprocess.run(..., timeout=1800)`
  already raises `TimeoutExpired` on a hang, satisfying the "or timeout" half of this requirement with
  no extra code). Task 5 calls this from the new `/api/transcribe` endpoint.
- Consumes: `build_dashboard.CONTEXTS` including `"#unknown"` (Task 3 — must run first).

- [ ] **Step 1: Write the failing tests**

Add these five tests to the end of `scripts/tests/test_dashboard_writer.py`:

```python
def test_edit_task_replaces_context_tag(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer",
                            new_context="phone")
    assert new_line == "- [ ] Pick SSG #next #phone"

def test_edit_task_sets_unknown_context(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Buy domain #next #computer",
                            new_context="unknown")
    assert new_line == "- [ ] Buy domain #next #unknown"

def test_edit_task_adds_context_when_none_present(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text() + "- [ ] No context yet #next\n")
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] No context yet #next",
                            new_context="errands")
    assert new_line == "- [ ] No context yet #next #errands"

def test_run_transcription_reports_no_pending_meetings(tmp_path):
    (tmp_path / "vendor" / "whisper-cpp").mkdir(parents=True)
    (tmp_path / "vendor" / "whisper-cpp" / "whisper-cli.exe").write_text("stub")
    out = W.run_transcription(tmp_path)
    assert out == "No pending meeting recordings."

def test_run_transcription_raises_on_failure(tmp_path):
    with pytest.raises(RuntimeError):
        W.run_transcription(tmp_path)  # no vendored whisper binary present
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_dashboard_writer.py -v`
Expected: `test_edit_task_*` FAIL with `TypeError: edit_task() got an unexpected keyword argument
'new_context'`; `test_run_transcription_*` FAIL with `AttributeError: module 'dashboard_writer' has no
attribute 'run_transcription'`.

- [ ] **Step 3: Add the `subprocess` import**

At the top of `scripts/dashboard_writer.py`, change:

```python
import datetime as _dt
import re as _re
import sys as _sys
from pathlib import Path
```

to:

```python
import datetime as _dt
import re as _re
import subprocess as _subprocess
import sys as _sys
from pathlib import Path
```

- [ ] **Step 4: Extend `edit_task` with `new_context`**

Replace the `edit_task` function with:

```python
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
```

- [ ] **Step 5: Add `run_transcription`**

Add this function at the end of `scripts/dashboard_writer.py`:

```python
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_dashboard_writer.py -v`
Expected: all PASS.

- [ ] **Step 7: Run the full Python suite to check for regressions**

Run: `python -m pytest scripts/tests/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/dashboard_writer.py scripts/tests/test_dashboard_writer.py
git commit -m "feat(dashboard): editable task context and a run_transcription helper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 5: `dashboard_server.py` — context passthrough, `/api/transcribe`

**Files:**
- Modify: `scripts/dashboard_server.py`
- Modify (test): `scripts/tests/test_dashboard_server.py`

**Interfaces:**
- Produces: `POST /api/edit-task` now reads and forwards `data.get("new_context")` to
  `W.edit_task(...)`.
- Produces: `POST /api/transcribe` — no required body fields; calls `W.run_transcription(vault)` and
  responds `{"ok": true, "output": "<script stdout>"}` on success. `run_transcription`'s `RuntimeError`
  on failure falls through to the handler's existing catch-all `except Exception` branch, returning
  HTTP 500 with `{"error": "internal error: <message>"}` — the message is the script's own stderr, so
  this is already a clear, actionable error without a dedicated except clause.
- Consumes: `W.edit_task`'s `new_context` parameter and `W.run_transcription` (Task 4 — must run
  first).

- [ ] **Step 1: Write the failing tests**

Add these three tests to the end of `scripts/tests/test_dashboard_server.py`:

```python
def test_edit_task_passes_through_new_context(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/edit-task",
                    {"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer",
                     "new_context": "phone"}) as r:
            data = json.loads(r.read())
        assert data["line_text"] == "- [ ] Pick SSG #next #phone"
        text = (tmp_path / "10 Projects" / "P.md").read_text()
        assert "#phone" in text
    finally:
        server.shutdown()


def test_transcribe_endpoint_reports_no_pending_meetings(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "vendor" / "whisper-cpp").mkdir(parents=True)
    (tmp_path / "vendor" / "whisper-cpp" / "whisper-cli.exe").write_text("stub")
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/transcribe", {}) as r:
            data = json.loads(r.read())
        assert data["ok"] is True
        assert "No pending meeting recordings." in data["output"]
    finally:
        server.shutdown()


def test_transcribe_endpoint_returns_500_when_whisper_binary_missing(tmp_path):
    _mk_vault(tmp_path)  # no vendor/ dir at all
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/transcribe", {})
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 500
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_dashboard_server.py -v`
Expected: `test_edit_task_passes_through_new_context` FAILs (the line stays `#computer`, since the
server doesn't forward `new_context` yet); the two `test_transcribe_endpoint_*` tests FAIL with a 404
(no `/api/transcribe` route yet).

- [ ] **Step 3: Wire `new_context` through `/api/edit-task` and add `/api/transcribe`**

In `scripts/dashboard_server.py`, change:

```python
                elif path == "/api/edit-task":
                    new_line = W.edit_task(vault, data["file"], data["line_text"],
                                            data.get("new_text"), data.get("new_due"))
                    self._send_json({"ok": True, "line_text": new_line})
```

to:

```python
                elif path == "/api/edit-task":
                    new_line = W.edit_task(vault, data["file"], data["line_text"],
                                            data.get("new_text"), data.get("new_due"),
                                            data.get("new_context"))
                    self._send_json({"ok": True, "line_text": new_line})
```

Then add a new branch right after the `/api/new-project` branch (before the trailing `else:`):

```python
                elif path == "/api/new-project":
                    rel = W.create_project(vault, data["title"])
                    self._send_json({"ok": True, "file": rel})
                elif path == "/api/transcribe":
                    output = W.run_transcription(vault)
                    self._send_json({"ok": True, "output": output})
                else:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_dashboard_server.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full Python suite to check for regressions**

Run: `python -m pytest scripts/tests/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/dashboard_server.py scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): edit-task context passthrough and a /api/transcribe endpoint

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 6: `logic.js` — editable context select, meeting pill, `renderNeedsTriage`, `renderMeetings`

**Files:**
- Modify: `scripts/dashboard_static/logic.js`
- Modify (test): `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Produces: `taskLine(t, today)` — when `t.project` is falsy and `t.meeting` is truthy, renders
  `<span class="meeting meeting-open" data-name="...">...</span>` instead of an empty project span
  (parallel to the existing `.proj.proj-open` pattern).
- Produces: `taskDetailHtml(t, today)` — the context row is now `<select id="detail-context">` with
  options `computer, phone, errands, home, office, anywhere, agenda, unknown` (the currently-set
  context pre-selected via a `selected` attribute). The "Project" row's label becomes `"Meeting"` and
  its value becomes a `.meeting.meeting-open` span (same pattern as above) whenever `t.project` is
  falsy and `t.meeting` is truthy; otherwise unchanged from before.
- Produces: `renderNeedsTriage(state, today) -> string` — every task in
  `state.tasks_by_context["#unknown"]` rendered via `taskLine`, or an empty-state message.
- Produces: `renderMeetings(meetings) -> string` — one list item per meeting: name, a
  transcription-status pill, a summary-status pill (only shown once transcription is done), and a link
  to `obsidian://open?path=<encoded file>`.
- Produces: `render(state, query, today)`'s returned object gains `needsTriageHtml` and
  `meetingsHtml` keys.
- Produces: the exported `api` object (both `module.exports` and `window.DashboardLogic`) gains
  `renderNeedsTriage` and `renderMeetings`.
- Consumes: `state.tasks_by_context["#unknown"]` and `state.meetings` (Task 3's parser output shape —
  already correct by construction, this task is pure frontend rendering).

- [ ] **Step 1: Write the failing tests**

Add these tests to the end of `scripts/dashboard_static/logic.test.js`:

```js
test("taskDetailHtml renders a context select with the task's context selected", () => {
  const t = { text: "x", file: "f.md", line_text: "x", project: "P", context: "#phone", due: null };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, /<select id="detail-context">/);
  assert.match(html, /<option value="phone" selected>phone<\/option>/);
  assert.match(html, /<option value="unknown">unknown<\/option>/);
});

test("taskDetailHtml shows a meeting pill and 'Meeting' label for a task with no project but a meeting", () => {
  const t = { text: "Email the vendor", file: "Meetings/2026-09-10 Sync.md", line_text: "x",
    project: null, meeting: "2026-09-10 Sync", context: "#unknown", due: null };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, />Meeting<\/span>/);
  assert.match(html, /meeting-open" data-name="2026-09-10 Sync"/);
  assert.doesNotMatch(html, /none — inbox capture/);
});

test("taskLine shows a meeting pill when the task has no project but has a meeting", () => {
  // #unknown tasks live only in the Needs-triage card (renderTasksByContext's ctxOrder excludes
  // "#unknown" by design — see the renderNeedsTriage tests below), so this exercises taskLine's
  // meeting-pill behavior through a normal, already-triaged context instead.
  const t = { text: "Email the vendor", file: "Meetings/2026-09-10 Sync.md",
    line_text: "- [ ] Email the vendor #next #computer", project: null, meeting: "2026-09-10 Sync" };
  const html = L.render(
    { inbox_count: 0, tasks_by_context: { "#computer": [t] }, waiting: [], due_soon: [],
      active_projects: [], someday_projects: [] },
    "", "2026-09-10"
  ).tasksHtml;
  assert.match(html, /meeting-open" data-name="2026-09-10 Sync"/);
});

test("renderNeedsTriage lists every #unknown-context task", () => {
  const state = { tasks_by_context: { "#unknown": [
    { text: "Email the vendor", file: "Meetings/x.md", line_text: "x", project: null, meeting: "Sync" },
  ] } };
  const html = L.renderNeedsTriage(state, "2026-09-10");
  assert.match(html, /Email the vendor/);
  assert.match(html, /meeting-open" data-name="Sync"/);
});

test("renderNeedsTriage shows an empty state when nothing needs triage", () => {
  const html = L.renderNeedsTriage({ tasks_by_context: {} }, "2026-09-10");
  assert.equal(html, '<p class="empty">Nothing to triage.</p>');
});

test("renderMeetings lists meetings with status pills and an Obsidian link", () => {
  const meetings = [
    { name: "2026-09-10 Sync", file: "Meetings/2026-09-10 Sync.md", date: "2026-09-10",
      transcription_status: "done", summary_status: "pending" },
    { name: "2026-09-09 Standup", file: "Meetings/2026-09-09 Standup.md", date: "2026-09-09",
      transcription_status: "pending", summary_status: "pending" },
  ];
  const html = L.renderMeetings(meetings);
  assert.match(html, /2026-09-10 Sync/);
  assert.match(html, /pending summary/);
  assert.match(html, /pending transcription/);
  assert.match(html, /obsidian:\/\/open\?path=Meetings%2F2026-09-10%20Sync\.md/);
});

test("renderMeetings shows an empty state with no meetings", () => {
  assert.equal(L.renderMeetings([]), '<p class="empty">No meetings yet.</p>');
});

test("render includes needsTriageHtml and meetingsHtml", () => {
  const state = {
    inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [],
    meetings: [{ name: "Sync", file: "Meetings/Sync.md", date: "2026-09-10",
      transcription_status: "done", summary_status: "done" }],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.match(out.needsTriageHtml, /Nothing to triage/);
  assert.match(out.meetingsHtml, /Sync/);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: the 8 new tests FAIL (no `<select id="detail-context">`, no `.meeting` handling,
`L.renderNeedsTriage`/`L.renderMeetings` are not functions, `out.needsTriageHtml`/`out.meetingsHtml`
are `undefined`).

- [ ] **Step 3: Update `taskLine`**

In `scripts/dashboard_static/logic.js`, replace the `taskLine` function with:

```js
  function taskLine(t, today) {
    var due = t.due
      ? '<span class="due' + (isOverdue(t.due, today) ? " overdue" : "") + '">' +
        escapeHtml(t.due) + "</span>"
      : "";
    var proj = t.project
      ? '<span class="proj proj-open" data-name="' + escapeHtml(t.project) + '">' + escapeHtml(t.project) + "</span>"
      : (t.meeting
          ? '<span class="meeting meeting-open" data-name="' + escapeHtml(t.meeting) + '">' + escapeHtml(t.meeting) + "</span>"
          : "");
    return '<li class="task" data-file="' + escapeHtml(t.file) + '" data-line="' +
      escapeHtml(t.line_text) + '">' +
      '<input type="checkbox" class="task-check">' +
      '<span class="task-text">' + escapeHtml(t.text) + "</span>" +
      proj + due +
      '<button class="task-delete" title="Delete">×</button>' +
      "</li>";
  }
```

- [ ] **Step 4: Update `taskDetailHtml`**

Replace the `taskDetailHtml` function with:

```js
  function taskDetailHtml(t, today) {
    var overdue = t.due && isOverdue(t.due, today);
    var sourceLabel = (!t.project && t.meeting) ? "Meeting" : "Project";
    var sourceValue = t.project
      ? '<a href="#" class="proj-open" data-name="' + escapeHtml(t.project) + '">' + escapeHtml(t.project) + "</a>"
      : (t.meeting
          ? '<span class="meeting meeting-open" data-name="' + escapeHtml(t.meeting) + '">' + escapeHtml(t.meeting) + "</span>"
          : '<span class="empty">none — inbox capture</span>');
    var ctx = (t.context || "#anywhere").replace(/^#/, "");
    var ctxOptions = ["computer", "phone", "errands", "home", "office", "anywhere", "agenda", "unknown"]
      .map(function (c) {
        return '<option value="' + c + '"' + (c === ctx ? " selected" : "") + ">" + c + "</option>";
      }).join("");
    return (
      '<div class="detail-row"><label for="detail-text">Text</label>' +
      '<input type="text" id="detail-text" value="' + escapeHtml(t.text) + '"></div>' +
      '<div class="detail-row"><label for="detail-due">Due date</label>' +
      '<input type="date" id="detail-due" value="' + escapeHtml(t.due || "") + '">' +
      (overdue ? ' <span class="pill overdue">overdue</span>' : "") + "</div>" +
      '<div class="detail-row"><label for="detail-context">Context</label>' +
      '<select id="detail-context">' + ctxOptions + "</select></div>" +
      '<div class="detail-row"><span class="detail-label">' + sourceLabel + '</span><span>' + sourceValue + "</span></div>" +
      '<div class="detail-actions">' +
      '<button type="button" class="detail-save" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Save</button>' +
      '<button type="button" class="detail-mark-done" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Mark done</button>' +
      '<button type="button" class="detail-delete" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Delete</button>' +
      "</div>"
    );
  }
```

- [ ] **Step 5: Add `renderNeedsTriage` and `renderMeetings`, wire both into `render`, export them**

Add these two functions right before `function render(state, query, today) {`:

```js
  function renderNeedsTriage(state, today) {
    var items = (state.tasks_by_context || {})["#unknown"] || [];
    if (!items.length) return '<p class="empty">Nothing to triage.</p>';
    return '<ul class="task-list">' + items.map(function (t) { return taskLine(t, today); }).join("") + "</ul>";
  }

  function renderMeetings(meetings) {
    if (!meetings || !meetings.length) return '<p class="empty">No meetings yet.</p>';
    return "<ul>" + meetings.map(function (m) {
      var tPill = m.transcription_status === "done"
        ? '<span class="pill">transcribed</span>'
        : (m.transcription_status === "failed"
            ? '<span class="pill overdue">transcription failed</span>'
            : '<span class="pill overdue">pending transcription</span>');
      var sPill = m.transcription_status === "done"
        ? (m.summary_status === "done"
            ? '<span class="pill">summarized</span>'
            : '<span class="pill overdue">pending summary</span>')
        : "";
      return '<li><a href="obsidian://open?path=' + encodeURIComponent(m.file) + '">' +
        escapeHtml(m.name) + "</a>" + tPill + sPill + "</li>";
    }).join("") + "</ul>";
  }
```

Change the `render` function's return statement from:

```js
    return {
      kpis: {
        inbox: state.inbox_count,
        tasks: totalTasks,
        waiting: (state.waiting || []).length,
        due: (state.due_soon || []).length,
      },
      tasksHtml: renderTasksByContext(state.tasks_by_context || {}, query, today),
      dueSoonHtml: renderSimpleList(state.due_soon || [], today),
      waitingHtml: renderSimpleList(state.waiting || [], today),
      projectsHtml: renderProjects(state.active_projects || []),
      somedayHtml: renderProjects(state.someday_projects || []),
    };
```

to:

```js
    return {
      kpis: {
        inbox: state.inbox_count,
        tasks: totalTasks,
        waiting: (state.waiting || []).length,
        due: (state.due_soon || []).length,
      },
      tasksHtml: renderTasksByContext(state.tasks_by_context || {}, query, today),
      dueSoonHtml: renderSimpleList(state.due_soon || [], today),
      waitingHtml: renderSimpleList(state.waiting || [], today),
      projectsHtml: renderProjects(state.active_projects || []),
      somedayHtml: renderProjects(state.someday_projects || []),
      needsTriageHtml: renderNeedsTriage(state, today),
      meetingsHtml: renderMeetings(state.meetings || []),
    };
```

Change the exported `api` object from:

```js
  var api = {
    escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render,
    tasksForProject: tasksForProject, taskDetailHtml: taskDetailHtml, projectDetailHtml: projectDetailHtml,
  };
```

to:

```js
  var api = {
    escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render,
    tasksForProject: tasksForProject, taskDetailHtml: taskDetailHtml, projectDetailHtml: projectDetailHtml,
    renderNeedsTriage: renderNeedsTriage, renderMeetings: renderMeetings,
  };
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/logic.js scripts/dashboard_static/logic.test.js
git commit -m "feat(dashboard): editable context select, meeting pill, needs-triage and meetings rendering

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 7: Frontend wiring — `index.html`, `app.js`, `style.css`

**Files:**
- Modify: `scripts/dashboard_static/index.html`
- Modify: `scripts/dashboard_static/app.js`
- Modify: `scripts/dashboard_static/style.css`

**Interfaces:**
- Produces: two new `<section class="card">` grid cells — `#needs-triage` and `#meetings` (with a
  `#transcribe-btn` button inside the Meetings card) — bringing the 4×2 grid to exactly 8 cells with no
  empty ones.
- Produces: `app.js`'s `renderAll()` populates `#needs-triage` and `#meetings` from
  `out.needsTriageHtml`/`out.meetingsHtml` (Task 6).
- Produces: the document click delegate handles `.meeting-open` (looks the meeting up in
  `state.meetings` by `data-name`, opens `obsidian://open?path=<its file>` directly — no modal,
  matching the "no meeting detail overlay" constraint) and the `.detail-save` handler now also reads
  `#detail-context` and includes `new_context` in its `POST /api/edit-task` body.
- Produces: `#transcribe-btn` posts to `/api/transcribe`, disables itself and shows "Transcribing…"
  while in flight, then refreshes.
- Consumes: `DashboardLogic.render(...)`'s `needsTriageHtml`/`meetingsHtml` keys and
  `taskDetailHtml`'s `#detail-context` select (Task 6); `POST /api/transcribe` and `new_context` on
  `POST /api/edit-task` (Task 5). This is manual/DOM-wiring work with no automated test, matching this
  file's existing pattern — verify with the Step 5 smoke test below instead.

- [ ] **Step 1: Update `index.html`'s grid**

Replace:

```html
  <main class="grid">
    <section class="card span2"><h2>Tasks</h2><div id="tasks"></div></section>
    <section class="card"><h2>Due soon</h2><div id="due-soon"></div></section>
    <section class="card"><h2>Waiting for</h2><div id="waiting"></div></section>
    <section class="card"><h2>Active projects</h2><div id="projects"></div></section>
    <section class="card"><h2>Someday / Maybe</h2><div id="someday"></div></section>
  </main>
```

with:

```html
  <main class="grid">
    <section class="card span2"><h2>Tasks</h2><div id="tasks"></div></section>
    <section class="card"><h2>Due soon</h2><div id="due-soon"></div></section>
    <section class="card"><h2>Waiting for</h2><div id="waiting"></div></section>
    <section class="card"><h2>Active projects</h2><div id="projects"></div></section>
    <section class="card"><h2>Someday / Maybe</h2><div id="someday"></div></section>
    <section class="card card-attn"><h2>Needs triage</h2><div id="needs-triage"></div></section>
    <section class="card">
      <h2>Meetings</h2>
      <button id="transcribe-btn" type="button">Transcribe pending</button>
      <div id="meetings"></div>
    </section>
  </main>
```

- [ ] **Step 2: Update `app.js`'s `renderAll()`**

Replace:

```js
  function renderAll() {
    if (!state) return;
    var out = DashboardLogic.render(state, query, today());
    document.getElementById("kpis").innerHTML =
      ["inbox", "tasks", "waiting", "due"].map(function (k) {
        return '<div class="kpi"><b>' + out.kpis[k] + "</b><div>" + k + "</div></div>";
      }).join("");
    document.getElementById("tasks").innerHTML = out.tasksHtml;
    document.getElementById("due-soon").innerHTML = out.dueSoonHtml;
    document.getElementById("waiting").innerHTML = out.waitingHtml;
    document.getElementById("projects").innerHTML = out.projectsHtml;
    document.getElementById("someday").innerHTML = out.somedayHtml;
  }
```

with:

```js
  function renderAll() {
    if (!state) return;
    var out = DashboardLogic.render(state, query, today());
    document.getElementById("kpis").innerHTML =
      ["inbox", "tasks", "waiting", "due"].map(function (k) {
        return '<div class="kpi"><b>' + out.kpis[k] + "</b><div>" + k + "</div></div>";
      }).join("");
    document.getElementById("tasks").innerHTML = out.tasksHtml;
    document.getElementById("due-soon").innerHTML = out.dueSoonHtml;
    document.getElementById("waiting").innerHTML = out.waitingHtml;
    document.getElementById("projects").innerHTML = out.projectsHtml;
    document.getElementById("someday").innerHTML = out.somedayHtml;
    document.getElementById("needs-triage").innerHTML = out.needsTriageHtml;
    document.getElementById("meetings").innerHTML = out.meetingsHtml;
  }
```

- [ ] **Step 3: Handle `.meeting-open` clicks and the context select in the save flow**

In the document `click` listener, change:

```js
  document.addEventListener("click", function (e) {
    var projTrigger = e.target.closest(".proj-open");
    if (projTrigger) {
      e.preventDefault();
      openProjectDetail(projTrigger.getAttribute("data-name"));
      return;
    }

    var saveBtn = e.target.closest(".detail-save");
    if (saveBtn) {
      var newText = document.getElementById("detail-text").value.trim();
      var newDue = document.getElementById("detail-due").value;
      var editBody = { file: saveBtn.getAttribute("data-file"), line_text: saveBtn.getAttribute("data-line"), new_text: newText };
      if (newDue) editBody.new_due = newDue;
      post("/api/edit-task", editBody).then(function () { closeDetailModal(); refresh(); })
        .catch(function () { closeDetailModal(); refresh(); });
      return;
    }
```

to:

```js
  document.addEventListener("click", function (e) {
    var projTrigger = e.target.closest(".proj-open");
    if (projTrigger) {
      e.preventDefault();
      openProjectDetail(projTrigger.getAttribute("data-name"));
      return;
    }

    var meetingTrigger = e.target.closest(".meeting-open");
    if (meetingTrigger) {
      e.preventDefault();
      var meetingName = meetingTrigger.getAttribute("data-name");
      var meeting = (state.meetings || []).filter(function (m) { return m.name === meetingName; })[0];
      if (meeting) window.open("obsidian://open?path=" + encodeURIComponent(meeting.file));
      return;
    }

    var saveBtn = e.target.closest(".detail-save");
    if (saveBtn) {
      var newText = document.getElementById("detail-text").value.trim();
      var newDue = document.getElementById("detail-due").value;
      var ctxEl = document.getElementById("detail-context");
      var editBody = { file: saveBtn.getAttribute("data-file"), line_text: saveBtn.getAttribute("data-line"), new_text: newText };
      if (newDue) editBody.new_due = newDue;
      if (ctxEl) editBody.new_context = ctxEl.value;
      post("/api/edit-task", editBody).then(function () { closeDetailModal(); refresh(); })
        .catch(function () { closeDetailModal(); refresh(); });
      return;
    }
```

- [ ] **Step 4: Wire the transcribe button**

Add this right after the existing `theme-toggle` listener (`document.getElementById("theme-toggle")...`
block):

```js
  document.getElementById("transcribe-btn").addEventListener("click", function () {
    var btn = document.getElementById("transcribe-btn");
    btn.disabled = true;
    btn.textContent = "Transcribing…";
    post("/api/transcribe", {}).then(function () {
      btn.disabled = false;
      btn.textContent = "Transcribe pending";
      refresh();
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = "Transcribe pending";
      refresh();
    });
  });
```

- [ ] **Step 5: Add styling**

Add to the end of `scripts/dashboard_static/style.css`:

```css
.meeting { color: var(--accent); font-size: 0.75rem; }
.meeting-open { cursor: pointer; text-decoration: none; }
.meeting-open:hover { text-decoration: underline; }
.card-attn { border-left: 3px solid var(--accent); }
#transcribe-btn {
  border-color: var(--accent); color: var(--accent); font-weight: 600;
  margin-bottom: 6px; padding: 6px 12px; border-radius: 8px; background: var(--card-bg);
  border-width: 1px; border-style: solid; cursor: pointer; font-size: 0.85rem;
}
#transcribe-btn:disabled { opacity: 0.6; cursor: default; }
```

- [ ] **Step 6: Manual smoke test**

Run: `python scripts/dashboard_server.py . --port 8788` (from the repo root — this serves the real
vault), then in a browser open `http://localhost:8788`:
- Confirm the page loads with 8 grid cells and no visibly broken layout.
- Confirm "Needs triage" and "Meetings" cards render (empty-state text if the vault currently has no
  `#unknown` tasks / no `Meetings/*.md` notes, which is expected on a fresh vault).
- Click "Transcribe pending" — confirm it disables, shows "Transcribing…", then re-enables and the
  page refreshes (with a vault that has no `vendor/whisper-cpp/` binary yet, this may show a failed
  network request in the console after the button re-enables — that's expected until Task 1's model is
  present on this machine; the important thing is the button doesn't hang or throw a JS error).
- Open a task's detail overlay — confirm the context row is now a dropdown and Save still works.

Stop the server (`Ctrl+C`) when done.

- [ ] **Step 7: Run the full JS + Python suites to check for regressions**

Run: `node --test scripts/dashboard_static/logic.test.js && python -m pytest scripts/tests/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/dashboard_static/index.html scripts/dashboard_static/app.js scripts/dashboard_static/style.css
git commit -m "feat(dashboard): wire Needs-triage/Meetings cards and the transcribe button into the UI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 8: GTD skills — new `gtd-summarize-meetings`, updated `gtd-transcribe-meeting`

**Files:**
- Create: `.claude/skills/gtd-summarize-meetings/SKILL.md`
- Modify: `.claude/skills/gtd-transcribe-meeting/SKILL.md`

**Interfaces:**
- Produces: `gtd-summarize-meetings` — a standalone, idempotent, no-prompt skill callable directly by
  the user or on a schedule; also invoked as step 2 of `gtd-transcribe-meeting`.
- Consumes: `transcribe_meetings.py`'s exact output strings and the `PENDING_SUMMARY_NOTE` placeholder
  text from Task 1 — this task's prose must match Task 1's actual final strings, not the pre-Task-1
  originals.

These are Claude Code prompt files with no automated test harness (same as every other skill in this
vault) — verification is Step 3 below, not TDD.

- [ ] **Step 1: Create `.claude/skills/gtd-summarize-meetings/SKILL.md`**

```markdown
---
name: gtd-summarize-meetings
description: Use when checking for or summarizing transcribed meetings that haven't been summarized yet — extracting notes, decisions, and action items from a meeting transcript. Triggers on "summarize meetings", "check for unsummarized meetings", "process meeting transcripts". Designed to also run unattended on a recurring schedule.
---

# GTD Summarize Meetings

Idempotent, unattended-safe: finds every meeting note under `Meetings/` that has been transcribed but
not yet summarized, and writes a real summary into it. No interactive prompts — safe to run on a
schedule (e.g. every 2 hours) with no one watching.

Unlike most GTD skills in this vault, this one's entire job IS generation: reading a transcript,
writing a summary, and inferring which action items exist and what context they belong to. That is
expected here — it is not a violation of "never fabricate."

## Steps
1. List every note directly under `Meetings/` (`README.md` excluded) whose frontmatter has
   `transcription_status: done` and `summary_status` not equal to `done`.
2. If none: report "No unsummarized meetings." and stop.
3. For each note, read its `## Transcript` section:
   - If empty or exactly `_No speech detected._`: set `summary_status: done` in frontmatter, leave
     `## Notes`/`## Decisions`/`## Action items` untouched, note "No speech detected — nothing to
     summarize," and move to the next note.
   - Otherwise, read the whole transcript (it may be in any language — read and respond in that
     language, never translate) and:
     - Append a concise summary to `## Notes`, below any existing non-placeholder content already
       there (never overwrite genuine user notes — this section may already have pre-meeting notes).
     - Append explicit decisions made in the meeting to `## Decisions`.
     - Replace the `_Pending summary — ..._` placeholder in `## Action items` with one
       `- [ ] {text} #next #{context} [[{note_stem}]]` line per real action item, inferring `{context}`
       from what the transcript actually says:
       - a phone call or message to make → `#phone`
       - a document, code, or deck to update → `#computer`
       - an in-person errand → `#errands`
       - something only doable at home → `#home`
       - something only doable at the workplace → `#office`
       - tied to a specific person's next meeting/conversation with them → `#agenda`
       - no clear location/tool signal → `#anywhere`
       - genuinely ambiguous even after reading the whole transcript → `#unknown` (the dashboard's
         "Needs triage" card lets the user resolve these later — never guess just to avoid it)
     - Set `summary_status: done`.
4. Report each note's result concisely (one line per note: summarized with N action items, or "no
   speech detected," etc.).

## Rules
- Idempotent — notes already `summary_status: done` are left untouched, so it's always safe to re-run
  (including on an unattended schedule).
- Never overwrite existing `## Notes`/`## Decisions` content — append below it.
- Never fabricate a transcript — this skill only summarizes what `## Transcript` actually contains;
  that section is filled mechanically by `scripts/transcribe_meetings.py` before this skill ever runs.
- No interactive prompts, no confirmation questions — this must be able to run with nobody watching.
```

- [ ] **Step 2: Replace `.claude/skills/gtd-transcribe-meeting/SKILL.md`**

```markdown
---
name: gtd-transcribe-meeting
description: Use when the user wants to transcribe a recorded meeting, process pending meeting recordings, or get a full summary (notes, decisions, action items) out of a meeting recording. Triggers on "transcribe my meeting", "process the recording", "what came out of that meeting".
---

# GTD Transcribe Meeting

Runs the full pipeline for recorded meetings, on demand: mechanical transcription, then summarization.
For scheduled/unattended summarization alone, see `gtd-summarize-meetings`, which this skill delegates
to for step 2 — that skill is the one source of truth for how summarization works.

## Steps
1. Run: `python scripts/transcribe_meetings.py .` — transcribes every meeting note under `Meetings/`
   whose frontmatter has `transcription_status: pending` (created by the `record-meeting` Obsidian
   plugin's recording button, or manually by setting `recording: "[[path/to/file.wav]]"` and
   `transcription_status: pending` on a note yourself). This writes the transcript into `## Transcript`
   and sets `summary_status: pending` — it does not summarize anything itself.
2. Invoke the `gtd-summarize-meetings` skill. This catches both the notes just transcribed in step 1
   and any older ones that were transcribed via the Obsidian captions button but never summarized.
3. Report both stages together: transcription results from step 1
   (`OK (transcribed): <note>` / `FAILED (<reason>): <note>` / "No pending meeting recordings."), then
   summarization results from step 2.
4. If any note failed transcription, open it — a `> [!fail] Transcription failed: ...` callout was
   added explaining why (commonly: the `.wav` was moved/deleted, or the vendored
   `vendor/whisper-cpp/whisper-cli.exe` is missing). Tell the user what it says; don't guess.

## Rules
- Transcription (step 1) is fully mechanical and must never be fabricated — it's the vendored
  `vendor/whisper-cpp/` binary + model doing the work (offline by default; only pass
  `--remote-url <endpoint>`/`--api-key` if the user explicitly wants a remote/OpenAI-compatible
  Whisper API instead, which requires network access).
- Summarization (step 2) IS real generation, by design — see `gtd-summarize-meetings` for why that's
  expected there and not a "never fabricate" violation.
- Idempotent — notes already `transcription_status: done` are skipped in step 1, and notes already
  `summary_status: done` are skipped in step 2, so it's always safe to re-run.
```

- [ ] **Step 3: Verify consistency with Task 1's actual script**

Read the final `scripts/transcribe_meetings.py` (from Task 1) and confirm every quoted string in both
SKILL.md files above matches it exactly: the three `process()` result-line formats (`"OK (transcribed):
{name}"`, `"FAILED ({reason}): {name}"`, `"No pending meeting recordings."`), the
`> [!fail] Transcription failed: ...` callout text from `mark_failed`, and the
`transcription_status`/`summary_status` frontmatter field names. Fix any mismatch you find before
committing — these skills are read by Claude Code at run time, so a stale quoted string would cause it
to misreport results to the user.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/gtd-summarize-meetings/SKILL.md .claude/skills/gtd-transcribe-meeting/SKILL.md
git commit -m "feat(gtd): add gtd-summarize-meetings skill, delegate to it from gtd-transcribe-meeting

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```

---

### Task 9: Docs — `meeting-recording.md` rewrite, `local-dashboard.md` addition

**Files:**
- Modify: `docs/gtd/meeting-recording.md`
- Modify: `docs/gtd/local-dashboard.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the final behavior from every prior task (this is the last task in the plan — docs
  describe what was actually built, not what was planned).

- [ ] **Step 1: Replace `docs/gtd/meeting-recording.md`**

```markdown
# Meeting recording, transcription, and summarization

Recording and transcription are Obsidian-plugin/script-driven and fully mechanical; summarizing what
was said (notes, decisions, action items) is a separate, Claude-Code-only step — a transcript can be
in any language and largely unstructured, so pattern-matching a summary out of it needs real reading
comprehension, not a regex.

## The two stages

1. **Transcription (mechanical).** Turns audio into `## Transcript` text. Tracked by the note's
   `transcription_status` frontmatter field (`pending` → `done`/`failed`). Never guesses at meaning —
   just runs the vendored offline Whisper model against the recording.
2. **Summarization (Claude Code, real generation).** Reads `## Transcript` and writes `## Notes`,
   `## Decisions`, and `## Action items` — with each action item tagged with a real context guess
   (`#computer`, `#phone`, ... or `#unknown` when genuinely ambiguous). Tracked by `summary_status`
   (`pending` → `done`). Handled by the `gtd-summarize-meetings` skill, in whatever language the
   transcript is in — nothing gets translated.

## Recording and transcribing (buttons)

Two buttons, both added by the vendored `record-meeting` Obsidian plugin
(`.obsidian/plugins/record-meeting/`, enabled by default via `community-plugins.json`):

- 🎙️ **mic ribbon icon** ("Toggle meeting recording") — click once to start recording your
  microphone; click again to stop. Saves `Meetings/recordings/<timestamp>.wav` and opens a new
  `Meetings/<timestamp> Meeting.md` note with `recording: "[[...]]"` pointing at it,
  `transcription_status: pending`, and `summary_status: pending`.
- 💬 **captions ribbon icon** ("Transcribe pending meeting recordings") — transcribes every pending
  recording and writes the result into that note's `## Transcript` section. It does **not** summarize
  — `## Action items` is left with a `_Pending summary — run /gtd-transcribe-meeting or
  /gtd-summarize-meetings in Claude Code._` placeholder until the summarization step runs.

Both are also in the command palette (`Ctrl+P` → "Record Meeting: ...") if you'd rather use a hotkey.
The local dashboard server's Meetings card has the same "Transcribe pending" action as a button, and
the dashboard's "Needs triage" card surfaces any action item whose context came back `#unknown` so you
can resolve it with a couple of clicks.

## Summarizing (Claude Code)

- **On demand, right now:** ask for "transcribe my meeting" (or run `/gtd-transcribe-meeting`) — it
  runs the transcription script, then summarizes anything pending (both what it just transcribed and
  anything transcribed earlier via the Obsidian button but never summarized).
- **Unattended, on a schedule:** `/gtd-summarize-meetings` does the summarization step alone, with no
  prompts — safe to run on a recurring schedule (e.g. every 2 hours) once you've configured one
  yourself, since it just finds transcribed-but-unsummarized notes and processes them.

## How it works offline

Recording uses the browser's own microphone + Web Audio APIs (`getUserMedia`/`AudioContext`) built
into Obsidian's desktop app and encodes straight to a `.wav` file itself — no external encoder, no
network. Transcription shells out to `vendor/whisper-cpp/whisper-cli.exe`, a vendored, fully offline
`whisper.cpp` build, against the vendored **multilingual** `ggml-tiny.bin` model with automatic
per-recording language detection (`-l auto`) — see `vendor/whisper-cpp/README.md` for exactly what's
in there and how to upgrade it. Nothing in the transcription stage requires internet access,
`pip install`, or `npm install` — it works immediately on a fresh, air-gapped clone of this repo.
Summarization, by contrast, always runs through Claude Code (it's the reading-comprehension step).

## Optional: a remote Whisper API instead

If you'd rather use a remote/hosted Whisper endpoint (e.g. OpenAI's), run
`python scripts/transcribe_meetings.py . --remote-url https://api.openai.com/v1/audio/transcriptions
--api-key sk-...` yourself, or pass `--remote-url`/`--api-key` through to the
`gtd-transcribe-meeting` skill. This is opt-in only — the plugin's captions button always uses the
local vendored model.

## Privacy note

`Meetings/recordings/*.wav` is gitignored — your recordings stay on your machine and are never
committed, even though the code that makes and processes them is.

## Troubleshooting

If the "Transcribe pending meeting recordings" button (or the dashboard's "Transcribe pending" button)
fails immediately with an unclear Python-related error, check that `python` (or `python3`/`py`) on
your PATH actually resolves to a real Python installation. On Windows, this usually means installing
Python from python.org with "Add python.exe to PATH" checked during setup, rather than relying on the
Microsoft Store's Python listing — its `python` command can silently no-op (a stub app-execution
alias) instead of running your code, which produces a confusing failure rather than a clear "Python
not found" message.
```

- [ ] **Step 2: Add a short section to `docs/gtd/local-dashboard.md`**

In the "What it does" bullet list, add one bullet after the existing "Auto-refreshes..." bullet:

```markdown
- Shows recent meetings (transcription/summary status at a glance) with a "Transcribe pending" button,
  and a "Needs triage" card for any task whose context came back `#unknown` from meeting summarization
  — resolve one by opening its detail overlay and picking a real context from the dropdown.
```

- [ ] **Step 3: Update the README feature table row**

In `README.md`, change:

```markdown
| Meeting recording | 🎙️/💬 ribbon buttons (`record-meeting` plugin) to record a meeting to WAV and transcribe it — fully offline, vendored `whisper.cpp`. See `docs/gtd/meeting-recording.md`. |
```

to:

```markdown
| Meeting recording | 🎙️/💬 ribbon buttons (`record-meeting` plugin) to record a meeting to WAV and transcribe it — fully offline, vendored multilingual `whisper.cpp`. Summarizing into notes/decisions/action items runs separately in Claude Code (`gtd-summarize-meetings`). See `docs/gtd/meeting-recording.md`. |
```

- [ ] **Step 4: Commit**

```bash
git add docs/gtd/meeting-recording.md docs/gtd/local-dashboard.md README.md
git commit -m "docs: rewrite meeting-recording pipeline docs, add dashboard meetings section

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015BwTTTyNnaeziGs8G6uMtb"
```
