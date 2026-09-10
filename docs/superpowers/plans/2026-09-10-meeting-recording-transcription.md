# Meeting Recording + Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-click "record meeting" button inside Obsidian that saves audio to the vault, then
a "transcribe pending recordings" action that runs Whisper (local by default, remote optional),
writes the transcript into the linked meeting note, and extracts `#next` action items — everything
traceable back to the original recording, and the whole thing works fully offline out of the box.

**Architecture:** A hand-written, zero-build Obsidian plugin (`record-meeting`) uses the browser
`MediaRecorder`-adjacent Web Audio APIs (`getUserMedia` + `AudioContext`) to capture mono 16kHz PCM
and encode it to a WAV file itself (no external encoder needed) — this is the literal "button."
Transcription is a separate, idempotent stdlib-only Python script (`scripts/transcribe_meetings.py`,
mirroring the existing `scripts/build_dashboard.py` pattern) that shells out to a vendored
`whisper.cpp` CLI binary + a vendored `ggml-tiny.en.bin` model (both committed to `vendor/`, same
pattern as the existing `vendor/outlook-mcp-rs`), or optionally to a remote OpenAI-compatible
`/v1/audio/transcriptions` endpoint if the user configures one. The plugin's "Transcribe pending"
command is a thin wrapper that just invokes this script via `child_process`, so the same
transcription logic is usable from the Obsidian button *or* from a Claude Code / opencode skill
(`gtd-transcribe-meeting`) — consistent with this vault's "skills are the interface" design.
Action-item extraction is a stdlib regex heuristic (no ML/network dependency), appended as
`#next` tasks linked back to the meeting note (which itself links to the recording).

**Tech Stack:** Vanilla CommonJS Obsidian plugin (no npm/TypeScript build step — `main.js` is the
source of truth, matching how the vault avoids build tooling elsewhere), Python 3 stdlib
(`scripts/transcribe_meetings.py`, tested with `pytest`), `whisper.cpp` (`whisper-cli.exe`, Windows
x64 CPU build, vendored) + `ggml-tiny.en.bin` model (vendored), plain Node `assert`-based tests for
the plugin's pure helpers (no npm test framework needed).

**Spec:** No separate spec doc — the user explicitly asked to skip clarifying questions and go
straight to a plan; every design decision below was made using the vault's existing conventions
(`vendor/`, `scripts/`, `.claude/skills/`, GTD tag/frontmatter rules in `30 Resources/GTD System.md`)
as the source of truth, and was validated hands-on (see "Validation already done" below) before
writing this plan.

## Global Constraints

- **Air-gapped, out-of-the-box:** no `npm install`, `pip install`, or network access may be required
  at *use* time. Everything the feature needs (whisper binary, model, plugin code) is committed to
  the repo. Remote transcription is optional and explicitly opt-in (requires the user's own network
  + API endpoint at that point, which is fine — local is the default and always works offline).
- **Windows x64 only** for the vendored `whisper.cpp` binary (matches `vendor/outlook-mcp-rs`'s
  existing "Windows only, no-ops elsewhere" precedent — this user is on Windows).
- **Follow existing vault conventions exactly:** GTD tags (`#next`), frontmatter style (see
  `10 Projects/*.md`, `_templates/Meeting.md`), stdlib-only Python (see `scripts/build_dashboard.py`),
  vendored-binary documentation style (see `vendor/README.md`).
- **Personal data stays out of git:** actual recordings the user makes are *not* committed (only the
  code/binaries that produce and process them are) — see Task 2's `.gitignore` change.
- **Every task must leave `pytest` (Python) and `node test/lib.test.js` (plugin helpers) green.**

## Validation already done (do not re-derive — reuse these facts)

These were verified hands-on in this session, from this machine, before writing the plan:
- `https://github.com/ggml-org/whisper.cpp/releases/latest` (tag `b4938` at time of writing) ships
  `whisper-bin-x64.zip` (Windows x64, **CPU-only**, no CUDA/OpenVINO needed) containing
  `whisper-cli.exe` which auto-detects CPU features at runtime and picks the right `ggml-cpu-*.dll`
  (confirmed via `load_backend: loaded CPU backend from ...ggml-cpu-alderlake.dll` on this machine).
  `whisper-cli.exe --help` confirms it natively decodes `flac, mp3, ogg, wav` — **no ffmpeg needed**.
- Only these files from that zip are required at runtime (confirmed by running end-to-end):
  `whisper-cli.exe`, `whisper.dll`, `ggml.dll`, `ggml-base.dll`, and all 8 `ggml-cpu-*.dll` variants
  (kept together since the target machine's CPU may differ from the build machine). Total ~9.6MB.
  `SDL2.dll` (live-mic demo tools only), `llama.dll` (talk-llama demo only), and `parakeet*`
  (unrelated model demo) are **not** needed and should not be vendored.
- `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin` is 77,704,715 bytes
  (~74MB) — under GitHub's 100MB hard block (unlike `ggml-base.en.bin` at ~148MB, which would need
  Git LFS — LFS is unusable for an air-gapped import since a fresh clone needs the LFS server to
  smudge pointers, so `tiny.en` is the right default, not `base.en`).
- Ran `whisper-cli.exe -m ggml-tiny.en.bin -f test.wav -oj -of out -np` end-to-end successfully; the
  JSON output shape is `{"transcription": [{"text": "...", ...}, ...]}` — confirmed the exact field
  the parser in Task 3 needs to read.
- `.obsidian/community-plugins.json` is a flat JSON array of plugin ids; local/unpublished plugins
  work exactly like vendored ones (folder with `manifest.json` + `main.js` under
  `.obsidian/plugins/<id>/`, id listed in `community-plugins.json`) — no Community store submission
  needed, matching how `quickadd`/`dataview`/etc. are already vendored here.
- QuickAdd's macro/user-script JSON schema (for wiring a Dashboard button to a plugin command) is
  minified in the vendored `main.js` and not worth reverse-engineering blind — **the ribbon icon +
  Command Palette entry the plugin itself adds is the "button in Obsidian"** the user asked for, and
  is the standard, documented way Obsidian plugins expose actions. Don't attempt QuickAdd macro
  wiring in this plan; mention it as a manual optional extra in docs only.

---

## File Structure

| File | Responsibility |
|---|---|
| `vendor/whisper-cpp/whisper-cli.exe` + `*.dll` | Vendored whisper.cpp Windows CPU binary (Task 1) |
| `vendor/whisper-cpp/models/ggml-tiny.en.bin` | Vendored Whisper model (Task 1) |
| `vendor/whisper-cpp/README.md` | Provenance/checksums/upgrade instructions (Task 1) |
| `.gitignore` | Add `Meetings/recordings/*.wav` (Task 2) |
| `Meetings/recordings/.gitkeep` | Keep the (otherwise-ignored) folder present out of the box (Task 2) |
| `_templates/Meeting.md` | Add `recording`/`transcription_status` frontmatter + Transcript section (Task 2) |
| `scripts/transcribe_meetings.py` | Stdlib-only: find pending meetings, transcribe, extract action items, update notes (Task 3) |
| `scripts/tests/test_transcribe_meetings.py` | pytest coverage for the above (Task 3) |
| `.obsidian/plugins/record-meeting/lib.js` | Pure, Obsidian-free helpers (WAV encoding, filename slug, note template) (Task 4) |
| `.obsidian/plugins/record-meeting/test/lib.test.js` | Plain-Node test for `lib.js` (Task 4) |
| `.obsidian/plugins/record-meeting/main.js` | The actual plugin: ribbon buttons/commands, recording, invoking the transcribe script (Task 5) |
| `.obsidian/plugins/record-meeting/manifest.json` | Plugin manifest (Task 5) |
| `.obsidian/community-plugins.json` | Enable the new plugin id (Task 5) |
| `.claude/skills/gtd-transcribe-meeting/SKILL.md` | Claude Code/opencode entry point to the same script (Task 6) |
| `docs/gtd/meeting-recording.md`, `README.md`, `AGENTS.md`, `Meetings/README.md`, `docs/gtd/obsidian-plugins.md` | Docs (Task 7) |

---

### Task 1: Vendor the whisper.cpp binary + model

**Files:**
- Create: `vendor/whisper-cpp/whisper-cli.exe`
- Create: `vendor/whisper-cpp/whisper.dll`, `vendor/whisper-cpp/ggml.dll`, `vendor/whisper-cpp/ggml-base.dll`, `vendor/whisper-cpp/ggml-cpu-alderlake.dll`, `vendor/whisper-cpp/ggml-cpu-cannonlake.dll`, `vendor/whisper-cpp/ggml-cpu-cascadelake.dll`, `vendor/whisper-cpp/ggml-cpu-haswell.dll`, `vendor/whisper-cpp/ggml-cpu-icelake.dll`, `vendor/whisper-cpp/ggml-cpu-sandybridge.dll`, `vendor/whisper-cpp/ggml-cpu-skylakex.dll`, `vendor/whisper-cpp/ggml-cpu-sse42.dll`
- Create: `vendor/whisper-cpp/models/ggml-tiny.en.bin`
- Create: `vendor/whisper-cpp/README.md`

**Interfaces:**
- Produces: a working `vendor/whisper-cpp/whisper-cli.exe` that Task 3's Python script invokes as
  `whisper-cli.exe -m <model> -f <wav> -oj -of <out_base> -np -l en` and reads
  `<out_base>.json` → `{"transcription": [{"text": str, ...}, ...]}`.

- [ ] **Step 1: Download and extract the official Windows CPU release**

Run (Git Bash):
```bash
cd "C:/Users/adamk/projects/second-brain"
mkdir -p vendor/whisper-cpp/models
TMP=$(mktemp -d)
curl -sL --max-time 120 -o "$TMP/whisper-bin-x64.zip" \
  "https://github.com/ggml-org/whisper.cpp/releases/download/b4938/whisper-bin-x64.zip"
unzip -o -q "$TMP/whisper-bin-x64.zip" -d "$TMP/extracted"
cp "$TMP/extracted/Release/whisper-cli.exe" \
   "$TMP/extracted/Release/whisper.dll" \
   "$TMP/extracted/Release/ggml.dll" \
   "$TMP/extracted/Release/ggml-base.dll" \
   "$TMP"/extracted/Release/ggml-cpu-*.dll \
   vendor/whisper-cpp/
curl -sL --max-time 120 -o vendor/whisper-cpp/models/ggml-tiny.en.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin"
```

- [ ] **Step 2: Verify the binary runs and produces the expected JSON shape**

Run:
```bash
cd "C:/Users/adamk/projects/second-brain"
/c/Python313/python -c "
import wave, struct, math
sr=16000
with wave.open('/tmp/smoke.wav','wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b''.join(struct.pack('<h', int(3000*math.sin(2*math.pi*440*i/sr))) for i in range(sr*2)))
"
./vendor/whisper-cpp/whisper-cli.exe -m vendor/whisper-cpp/models/ggml-tiny.en.bin \
  -f /tmp/smoke.wav -oj -of /tmp/smoke_out -np
cat /tmp/smoke_out.json
```
Expected: exits 0, prints `load_backend: loaded CPU backend from ...`, and `/tmp/smoke_out.json`
contains a top-level `"transcription": [...]` key (may be an empty array — the smoke file is a tone,
not speech; this step is only proving the binary + model load and run correctly end to end).

- [ ] **Step 3: Write `vendor/whisper-cpp/README.md`**

```markdown
# Vendored: whisper.cpp (Windows x64 CPU build)

Local, fully-offline speech-to-text used by `scripts/transcribe_meetings.py` (and, through it, the
`record-meeting` Obsidian plugin and the `gtd-transcribe-meeting` skill). Committed so the vault is
self-contained for air-gapped machines — no `pip install openai-whisper`, no network, no ffmpeg.

- **Source:** https://github.com/ggml-org/whisper.cpp (release `b4938`, CPU-only Windows x64 build:
  `whisper-bin-x64.zip`)
- **Model:** https://huggingface.co/ggerganov/whisper.cpp `ggml-tiny.en.bin` (~74MB, English-only —
  chosen over `base.en`/`small.en` because it's under GitHub's 100MB hard file-size limit, so it can
  be committed directly with no Git LFS; LFS would defeat the air-gapped "clone and go" requirement).
- **Files:** `whisper-cli.exe` + `whisper.dll`, `ggml.dll`, `ggml-base.dll`, and all `ggml-cpu-*.dll`
  variants (the exe auto-detects the running CPU's feature set and loads the matching one — keep all
  of them since the machine this runs on may differ from the machine that vendored these files).
  `SDL2.dll`/`llama.dll`/`parakeet*` from the same release zip are unrelated demo-tool dependencies
  and were intentionally **not** vendored.
- **Platform:** Windows x86-64 only. `scripts/transcribe_meetings.py` fails clearly (not silently) if
  `--remote-url` isn't given and this binary isn't present/runnable — see that script's `main()`.
- **sha256 (whisper-cli.exe):** `800a0fd754afa75e109c7248286ad735670fb6b23d92ca5d12604647ef638a65`
- **sha256 (ggml-tiny.en.bin):** `921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f`
- **Usage:** `whisper-cli.exe -m models/ggml-tiny.en.bin -f <audio> -oj -of <out> -np -l en` — see
  `scripts/transcribe_meetings.py::transcribe_local` for the exact invocation.
- **Updating:** download a newer `whisper-bin-x64.zip` from
  https://github.com/ggml-org/whisper.cpp/releases and repeat the file list above; swap the model for
  a different `ggml-*.bin` from https://huggingface.co/ggerganov/whisper.cpp if you want better
  accuracy and don't mind a bigger repo (anything ≤~95MB is still LFS-free).
```

- [ ] **Step 4: Confirm nothing outside `vendor/whisper-cpp/` changed, then commit**

Run: `git status --short vendor/`
Expected: only new files under `vendor/whisper-cpp/`.

```bash
git add vendor/whisper-cpp
git commit -m "$(cat <<'EOF'
feat(meetings): vendor whisper.cpp (Windows CPU) + ggml-tiny.en model

Committed so meeting transcription works fully offline on an air-gapped
machine — no pip/npm install, no ffmpeg, no network at use time.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 2: Recording folder, `.gitignore`, and meeting template

**Files:**
- Modify: `.gitignore`
- Create: `Meetings/recordings/.gitkeep`
- Modify: `_templates/Meeting.md`
- Modify: `Meetings/README.md`

**Interfaces:**
- Produces: the `recording:` / `transcription_status:` frontmatter keys and `## Transcript` /
  `## Action items` heading names that Task 3's parser and Task 4/5's note-creation code both read
  and write. **These exact strings are load-bearing across tasks — do not rename them:**
  - Frontmatter keys: `recording` (a `"[[relative/path.wav]]"` wikilink string), `transcription_status`
    (`pending` | `done` | `failed`), `transcribed` (ISO date, added once done).
  - Body headings (exact text, case-sensitive): `## Transcript`, `## Action items`.

- [ ] **Step 1: Ignore personal recordings, keep the folder present**

Edit `.gitignore`, add under the `# Generated` section:
```gitignore
# Meeting recordings are personal audio — keep the code, not the audio
Meetings/recordings/*.wav
```

Create `Meetings/recordings/.gitkeep` (empty file) so the folder exists in a fresh clone even though
its contents are ignored.

- [ ] **Step 2: Extend the meeting template**

Replace the full contents of `_templates/Meeting.md` with:
```markdown
---
type: meeting
date: {{date:YYYY-MM-DD}}
attendees: 
recording: 
transcription_status: 
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
(`recording` and `transcription_status` are left blank here — this template is for *manually*
created meeting notes with no recording. The `record-meeting` plugin in Task 5 fills both fields
itself when it creates a note from a recording, and writes `## Transcript`/`## Action items` content
directly rather than using this Templates-plugin template.)

- [ ] **Step 3: Update `Meetings/README.md`**

Replace its contents with:
```markdown
# 🤝 Meetings
Meeting notes. Capture action items as `#next` tasks so they flow to the dashboard. Use
`_templates/Meeting.md`.

## Recording + transcription
Click the mic icon in the left ribbon (or run "Toggle meeting recording" from the command palette)
to record a meeting straight to `Meetings/recordings/*.wav` and open a linked note for it. When
you're ready, click the captions icon (or run "Transcribe pending meeting recordings") to transcribe
every pending recording locally (vendored `whisper.cpp`, fully offline) and extract `#next` action
items into the note — see `docs/gtd/meeting-recording.md`.
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore "Meetings/recordings/.gitkeep" "_templates/Meeting.md" "Meetings/README.md"
git commit -m "$(cat <<'EOF'
feat(meetings): add recording/transcription fields to the meeting template

Adds recording + transcription_status frontmatter and Transcript/Action
items sections that the upcoming record-meeting plugin and
transcribe_meetings.py script read and write. Recordings are gitignored
(personal audio); the folder itself is kept via .gitkeep.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 3: `scripts/transcribe_meetings.py` (transcription + action-item extraction)

**Files:**
- Create: `scripts/transcribe_meetings.py`
- Create: `scripts/tests/test_transcribe_meetings.py`

**Interfaces:**
- Consumes: frontmatter keys `recording`/`transcription_status` and headings `## Transcript`/
  `## Action items` from Task 2. Vendored binary/model paths from Task 1
  (`vendor/whisper-cpp/whisper-cli.exe`, `vendor/whisper-cpp/models/ggml-tiny.en.bin`).
- Produces (for Task 5/6 callers): a CLI — `python scripts/transcribe_meetings.py <vault_path>
  [--whisper-bin PATH] [--model PATH] [--remote-url URL] [--api-key KEY]` — prints one line per
  processed note to stdout (`"OK (N action item(s)): <name>"` or `"FAILED (<reason>): <name>"`, or
  `"No pending meeting recordings."` if there's nothing to do) and exits 0 on success, non-zero only
  if the local binary is missing and no `--remote-url` was given. Also exposes these importable
  functions other tasks/tests rely on: `parse_frontmatter(text) -> (dict, str)`,
  `render_frontmatter(dict) -> str`, `find_pending(vault: Path) -> list[Path]`,
  `resolve_recording(vault: Path, fm: dict) -> Path | None`,
  `transcribe_local(wav: Path, whisper_bin: Path, model: Path) -> str`,
  `transcribe_remote(wav: Path, url: str, api_key: str | None) -> str`,
  `extract_action_items(transcript: str) -> list[str]`,
  `apply_transcript(note_text: str, transcript: str, action_items: list[str], note_stem: str) -> str`,
  `mark_failed(note_text: str, reason: str) -> str`,
  `process(vault, whisper_bin, model, remote_url, api_key) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_transcribe_meetings.py`:
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transcribe_meetings as T


def _mk_vault(tmp_path: Path) -> Path:
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "README.md").write_text("# Meetings\n")
    (tmp_path / "Meetings" / "recordings").mkdir()
    wav = tmp_path / "Meetings" / "recordings" / "2026-09-10_10-00-00.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")
    note = tmp_path / "Meetings" / "2026-09-10_10-00-00 Meeting.md"
    note.write_text(
        "---\n"
        "type: meeting\n"
        "date: 2026-09-10\n"
        'recording: "[[Meetings/recordings/2026-09-10_10-00-00.wav]]"\n'
        "transcription_status: pending\n"
        "---\n\n"
        "# Meeting\n\n"
        "## Notes\n\n"
        "## Transcript\n\n"
        "## Action items\n- [ ]  #next\n"
    )
    return tmp_path


def test_parse_and_render_frontmatter_roundtrip():
    text = "---\na: 1\nb: two\n---\nbody here\n"
    fm, body = T.parse_frontmatter(text)
    assert fm == {"a": "1", "b": "two"}
    assert body == "body here\n"
    assert T.render_frontmatter(fm).startswith("---\na: 1\nb: two\n---")


def test_find_pending_lists_only_pending_notes(tmp_path):
    vault = _mk_vault(tmp_path)
    (vault / "Meetings" / "done.md").write_text("---\ntranscription_status: done\n---\nx\n")
    pending = T.find_pending(vault)
    assert len(pending) == 1
    assert pending[0].name == "2026-09-10_10-00-00 Meeting.md"


def test_resolve_recording_strips_wikilink(tmp_path):
    vault = _mk_vault(tmp_path)
    fm = {"recording": '"[[Meetings/recordings/2026-09-10_10-00-00.wav]]"'}
    resolved = T.resolve_recording(vault, fm)
    assert resolved is not None
    assert resolved.name == "2026-09-10_10-00-00.wav"


def test_resolve_recording_missing_file_returns_none(tmp_path):
    vault = _mk_vault(tmp_path)
    fm = {"recording": '"[[Meetings/recordings/nope.wav]]"'}
    assert T.resolve_recording(vault, fm) is None


def test_extract_action_items_matches_action_cues():
    transcript = (
        "We discussed the budget. I'll send the report by Friday. "
        "The weather was nice. We need to schedule a follow up call."
    )
    items = T.extract_action_items(transcript)
    assert any("send the report" in i for i in items)
    assert any("schedule a follow up" in i.lower() for i in items)
    assert not any("weather" in i for i in items)


def test_extract_action_items_dedupes_and_caps():
    transcript = " ".join(["I need to follow up on this."] * 15)
    items = T.extract_action_items(transcript)
    assert len(items) == 1


def test_apply_transcript_fills_sections_and_marks_done():
    note_text = (
        "---\ntranscription_status: pending\nrecording: \"[[x.wav]]\"\n---\n"
        "# Meeting\n\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    )
    out = T.apply_transcript(note_text, "Hello world.", ["Send the report."], "My Meeting")
    fm, body = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "done"
    assert "transcribed" in fm
    assert "Hello world." in body
    assert "- [ ] Send the report. #next [[My Meeting]]" in body


def test_apply_transcript_with_no_action_items_leaves_review_note():
    note_text = "---\ntranscription_status: pending\n---\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    out = T.apply_transcript(note_text, "Nothing actionable here.", [], "Stem")
    assert "No action items detected" in out


def test_mark_failed_sets_status_and_appends_callout():
    note_text = "---\ntranscription_status: pending\n---\nbody\n"
    out = T.mark_failed(note_text, "boom")
    fm, body = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "failed"
    assert "boom" in body


def test_process_marks_failed_when_recording_missing(tmp_path):
    vault = _mk_vault(tmp_path)
    (vault / "Meetings" / "recordings" / "2026-09-10_10-00-00.wav").unlink()
    results = T.process(
        vault,
        vault / "vendor" / "whisper-cpp" / "whisper-cli.exe",
        vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.en.bin",
        None,
        None,
    )
    assert len(results) == 1
    assert "FAILED" in results[0]


def test_process_uses_transcribe_local_and_updates_note(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_local", lambda wav, b, m: "I'll email the vendor tomorrow.")
    results = T.process(vault, Path("fake-bin"), Path("fake-model"), None, None)
    assert len(results) == 1
    assert results[0].startswith("OK")
    note_text = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "I'll email the vendor tomorrow." in note_text
    assert "#next" in note_text


def test_process_is_idempotent_skips_done_notes(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_local", lambda wav, b, m: "Some transcript.")
    T.process(vault, Path("fake-bin"), Path("fake-model"), None, None)
    assert T.process(vault, Path("fake-bin"), Path("fake-model"), None, None) == []
```

- [ ] **Step 2: Run the tests to verify they fail (module doesn't exist yet)**

Run: `cd "C:/Users/adamk/projects/second-brain" && /c/Python313/python -m pytest scripts/tests/test_transcribe_meetings.py -v`
Expected: `ModuleNotFoundError: No module named 'transcribe_meetings'` (collection error).

- [ ] **Step 3: Implement `scripts/transcribe_meetings.py`**

```python
#!/usr/bin/env python3
"""Transcribe pending meeting recordings and extract #next action items. Stdlib only."""
from __future__ import annotations
import argparse, datetime as _dt, json, re, subprocess, sys, tempfile, urllib.request
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

ACTION_CUES = re.compile(
    r"\b(i'll|i will|we'll|we will|let's|lets|let us|need(?:s)? to|"
    r"should|going to|have to|has to|will follow up|follow up|"
    r"action item|to-?do|by (?:monday|tuesday|wednesday|thursday|friday|next week|tomorrow))\b",
    re.IGNORECASE,
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
             "-oj", "-of", str(out_base), "-np", "-l", "en"],
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


def extract_action_items(transcript: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", transcript)
    seen: set[str] = set()
    items: list[str] = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 8:
            continue
        if ACTION_CUES.search(s):
            key = s.lower()
            if key not in seen:
                seen.add(key)
                items.append(s)
        if len(items) >= 10:
            break
    return items


def _replace_section(body: str, heading: str, content: str) -> str:
    pattern = re.compile(rf"{re.escape(heading)}\n.*?(?=\n## |\Z)", re.DOTALL)
    replacement = f"{heading}\n{content}\n"
    if pattern.search(body):
        return pattern.sub(replacement, body)
    return body + f"\n{replacement}"


def apply_transcript(note_text: str, transcript: str, action_items: list[str], note_stem: str) -> str:
    fm, body = parse_frontmatter(note_text)
    fm["transcription_status"] = "done"
    fm["transcribed"] = _dt.date.today().isoformat()

    transcript_block = transcript if transcript else "_No speech detected._"
    body = _replace_section(body, "## Transcript", transcript_block)

    if action_items:
        items_block = "\n".join(f"- [ ] {i} #next [[{note_stem}]]" for i in action_items)
    else:
        items_block = "_No action items detected — review manually._"
    body = _replace_section(body, "## Action items", items_block)

    return render_frontmatter(fm) + "\n" + body


def mark_failed(note_text: str, reason: str) -> str:
    fm, body = parse_frontmatter(note_text)
    fm["transcription_status"] = "failed"
    body += f"\n> [!fail] Transcription failed: {reason}\n"
    return render_frontmatter(fm) + "\n" + body


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
        action_items = extract_action_items(transcript)
        note_path.write_text(
            apply_transcript(note_text, transcript, action_items, note_path.stem), encoding="utf-8"
        )
        results.append(f"OK ({len(action_items)} action item(s)): {note_path.name}")
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
             else vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.en.bin")

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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "C:/Users/adamk/projects/second-brain" && /c/Python313/python -m pytest scripts/tests/test_transcribe_meetings.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Add a gated smoke test against the real vendored binary**

Append to `scripts/tests/test_transcribe_meetings.py`:
```python
import platform
import pytest


@pytest.mark.skipif(platform.system() != "Windows", reason="whisper-cli.exe is a Windows binary")
def test_real_vendored_whisper_binary_runs(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    whisper_bin = repo_root / "vendor" / "whisper-cpp" / "whisper-cli.exe"
    model = repo_root / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.en.bin"
    if not whisper_bin.is_file() or not model.is_file():
        pytest.skip("vendored whisper binary/model not present")
    import wave, struct
    wav = tmp_path / "silence.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * 16000)
    text = T.transcribe_local(wav, whisper_bin, model)
    assert isinstance(text, str)
```

Run: `cd "C:/Users/adamk/projects/second-brain" && /c/Python313/python -m pytest scripts/tests/test_transcribe_meetings.py -v`
Expected: all tests PASS, including `test_real_vendored_whisper_binary_runs` (proves the Task 1
binary actually works against the real Python subprocess call path, not just mocks).

- [ ] **Step 6: Run the full existing test suite to check for regressions**

Run: `cd "C:/Users/adamk/projects/second-brain" && /c/Python313/python -m pytest scripts/ -v`
Expected: all tests PASS (including the pre-existing `test_build_dashboard.py`).

- [ ] **Step 7: Commit**

```bash
git add scripts/transcribe_meetings.py scripts/tests/test_transcribe_meetings.py
git commit -m "$(cat <<'EOF'
feat(meetings): add transcribe_meetings.py (local/remote whisper + action items)

Stdlib-only script that finds meeting notes with transcription_status:
pending, transcribes the linked recording (vendored whisper.cpp by
default, or a remote OpenAI-compatible endpoint if --remote-url is
given), extracts #next action items via regex heuristics, and writes
both back into the note. Idempotent — already-done notes are skipped.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 4: Plugin pure helpers (`lib.js`) with a plain-Node test

**Files:**
- Create: `.obsidian/plugins/record-meeting/lib.js`
- Create: `.obsidian/plugins/record-meeting/test/lib.test.js`

**Interfaces:**
- Produces (for Task 5): `timestampSlug(date: Date): string` (e.g. `"2026-09-10_07-05-03"`, used for
  both the `.wav` filename and the note filename so they stay correlated),
  `buildWavBuffer(float32Chunks: Float32Array[], sampleRate: number): ArrayBuffer` (a complete,
  playable 16-bit mono PCM WAV file), `meetingNoteContent({dateStr, recordingRelPath}): string`
  (full note body using the exact frontmatter keys/headings Task 2/3 established).

- [ ] **Step 1: Write the failing test**

Create `.obsidian/plugins/record-meeting/test/lib.test.js`:
```js
"use strict";
const assert = require("assert");
const { timestampSlug, buildWavBuffer, meetingNoteContent } = require("../lib.js");

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (e) {
    console.error(`FAIL - ${name}`);
    console.error(e);
    process.exitCode = 1;
  }
}

test("timestampSlug formats a zero-padded local timestamp", () => {
  const d = new Date(2026, 8, 9, 7, 5, 3); // month is 0-indexed -> September
  assert.strictEqual(timestampSlug(d), "2026-09-09_07-05-03");
});

test("buildWavBuffer writes a valid RIFF/WAVE header", () => {
  const chunk = new Float32Array([0, 0.5, -0.5, 1, -1]);
  const buf = buildWavBuffer([chunk], 16000);
  const view = new DataView(buf);
  const str = (o, n) =>
    Array.from({ length: n }, (_, i) => String.fromCharCode(view.getUint8(o + i))).join("");
  assert.strictEqual(str(0, 4), "RIFF");
  assert.strictEqual(str(8, 4), "WAVE");
  assert.strictEqual(str(12, 4), "fmt ");
  assert.strictEqual(view.getUint16(22, true), 1); // mono
  assert.strictEqual(view.getUint32(24, true), 16000); // sample rate
  assert.strictEqual(view.getUint16(34, true), 16); // bits per sample
  assert.strictEqual(str(36, 4), "data");
  assert.strictEqual(view.getUint32(40, true), chunk.length * 2);
  assert.strictEqual(buf.byteLength, 44 + chunk.length * 2);
});

test("buildWavBuffer clamps out-of-range samples", () => {
  const buf = buildWavBuffer([new Float32Array([2, -2])], 16000);
  const view = new DataView(buf);
  assert.strictEqual(view.getInt16(44, true), 0x7fff);
  assert.strictEqual(view.getInt16(46, true), -0x8000);
});

test("buildWavBuffer concatenates multiple chunks in order", () => {
  const buf = buildWavBuffer([new Float32Array([0.1]), new Float32Array([0.2, 0.3])], 16000);
  assert.strictEqual(buf.byteLength, 44 + 3 * 2);
});

test("meetingNoteContent embeds the recording link, pending status, and both headings", () => {
  const content = meetingNoteContent({
    dateStr: "2026-09-10",
    recordingRelPath: "Meetings/recordings/x.wav",
  });
  assert.ok(content.includes('recording: "[[Meetings/recordings/x.wav]]"'));
  assert.ok(content.includes("transcription_status: pending"));
  assert.ok(content.includes("## Transcript"));
  assert.ok(content.includes("## Action items"));
});

if (process.exitCode) {
  process.exit(process.exitCode);
}
console.log("All lib.js tests passed.");
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd "C:/Users/adamk/projects/second-brain" && node ".obsidian/plugins/record-meeting/test/lib.test.js"`
Expected: fails with `Error: Cannot find module '../lib.js'`.

- [ ] **Step 3: Implement `lib.js`**

Create `.obsidian/plugins/record-meeting/lib.js`:
```js
// lib.js — pure helpers for the record-meeting plugin.
// Deliberately zero Obsidian/Electron dependencies so this can be tested with plain `node`.
"use strict";

function pad(n) {
  return String(n).padStart(2, "0");
}

function timestampSlug(date) {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_` +
    `${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`
  );
}

// Encode mono Float32 PCM chunks (as produced by Web Audio) into a 16-bit PCM WAV ArrayBuffer.
// whisper.cpp decodes wav/mp3/flac/ogg natively, so no external encoder is needed.
function buildWavBuffer(float32Chunks, sampleRate) {
  let total = 0;
  for (const c of float32Chunks) total += c.length;

  const buffer = new ArrayBuffer(44 + total * 2);
  const view = new DataView(buffer);

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + total * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM fmt chunk size
  view.setUint16(20, 1, true); // audio format = PCM
  view.setUint16(22, 1, true); // channels = mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate (mono, 16-bit)
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, "data");
  view.setUint32(40, total * 2, true);

  let offset = 44;
  for (const chunk of float32Chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const s = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
  }
  return buffer;
}

function meetingNoteContent({ dateStr, recordingRelPath }) {
  return (
    "---\n" +
    "type: meeting\n" +
    `date: ${dateStr}\n` +
    "attendees: \n" +
    `recording: "[[${recordingRelPath}]]"\n` +
    "transcription_status: pending\n" +
    "---\n\n" +
    `# Meeting ${dateStr}\n\n` +
    `**Date:** ${dateStr}\n` +
    "**Attendees:** \n\n" +
    "## Notes\n\n" +
    "## Decisions\n\n" +
    "## Transcript\n\n" +
    "## Action items\n- [ ]  #next\n"
  );
}

module.exports = { timestampSlug, buildWavBuffer, meetingNoteContent };
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd "C:/Users/adamk/projects/second-brain" && node ".obsidian/plugins/record-meeting/test/lib.test.js"`
Expected: prints `ok - ...` for all 5 tests, then `All lib.js tests passed.`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add ".obsidian/plugins/record-meeting/lib.js" ".obsidian/plugins/record-meeting/test/lib.test.js"
git commit -m "$(cat <<'EOF'
feat(meetings): add record-meeting plugin's pure helpers (WAV encoding)

lib.js has zero Obsidian/Electron deps so it's testable with plain
node — WAV header/PCM encoding, the recording/note filename slug, and
the meeting note template the plugin writes on stop-recording.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 5: The Obsidian plugin itself (`main.js` + `manifest.json`)

**Files:**
- Create: `.obsidian/plugins/record-meeting/main.js`
- Create: `.obsidian/plugins/record-meeting/manifest.json`
- Modify: `.obsidian/community-plugins.json`

**Interfaces:**
- Consumes: `timestampSlug`, `buildWavBuffer`, `meetingNoteContent` from Task 4's `lib.js`;
  `scripts/transcribe_meetings.py`'s CLI contract from Task 3 (`python <script> <vault_path>`,
  stdout lines, exit code 0 on success).
- Produces: two ribbon icons + two command-palette commands — "Toggle meeting recording"
  (id `record-meeting:toggle-recording`) and "Transcribe pending meeting recordings" (id
  `record-meeting:transcribe-pending`) — these are the "button in Obsidian" the feature is built
  around.

- [ ] **Step 1: Write `manifest.json`**

Create `.obsidian/plugins/record-meeting/manifest.json`:
```json
{
  "id": "record-meeting",
  "name": "Record Meeting",
  "version": "1.0.0",
  "minAppVersion": "1.13.0",
  "description": "Record a meeting to WAV, then transcribe it locally (vendored whisper.cpp) or via a remote Whisper API, extracting #next action items linked back to the recording.",
  "author": "second-brain",
  "isDesktopOnly": true
}
```

- [ ] **Step 2: Write `main.js`**

Create `.obsidian/plugins/record-meeting/main.js`:
```js
"use strict";
const { Plugin, Notice, setIcon } = require("obsidian");
const { spawn } = require("child_process");
const path = require("path");
const { timestampSlug, buildWavBuffer, meetingNoteContent } = require("./lib.js");

const SAMPLE_RATE = 16000;
const RECORDINGS_DIR = "Meetings/recordings";
const PYTHON_CANDIDATES = ["python", "python3", "py"];

module.exports = class RecordMeetingPlugin extends Plugin {
  async onload() {
    this.recording = null; // { stream, audioCtx, source, processor, chunks, startedAt }

    this.ribbonEl = this.addRibbonIcon("mic", "Start/stop meeting recording", () => {
      this.toggleRecording();
    });

    this.addCommand({
      id: "toggle-recording",
      name: "Toggle meeting recording",
      callback: () => this.toggleRecording(),
    });

    this.addRibbonIcon("captions", "Transcribe pending meeting recordings", () => {
      this.transcribePending();
    });

    this.addCommand({
      id: "transcribe-pending",
      name: "Transcribe pending meeting recordings",
      callback: () => this.transcribePending(),
    });
  }

  onunload() {
    if (this.recording) this.stopRecording().catch(() => {});
  }

  async toggleRecording() {
    if (this.recording) await this.stopRecording();
    else await this.startRecording();
  }

  async startRecording() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      new Notice(`Could not access microphone: ${e.message || e}`);
      return;
    }

    const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    const chunks = [];

    processor.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };

    source.connect(processor);
    processor.connect(audioCtx.destination);

    this.recording = { stream, audioCtx, source, processor, chunks, startedAt: new Date() };
    setIcon(this.ribbonEl, "circle-stop");
    new Notice("Recording meeting…");
  }

  async stopRecording() {
    const rec = this.recording;
    this.recording = null;
    if (!rec) return;

    rec.processor.disconnect();
    rec.source.disconnect();
    rec.stream.getTracks().forEach((t) => t.stop());
    await rec.audioCtx.close();
    setIcon(this.ribbonEl, "mic");

    if (rec.chunks.length === 0) {
      new Notice("No audio captured; discarding.");
      return;
    }

    const wavBuffer = buildWavBuffer(rec.chunks, SAMPLE_RATE);
    const slug = timestampSlug(rec.startedAt);
    const recordingRelPath = `${RECORDINGS_DIR}/${slug}.wav`;

    await this.ensureFolder(RECORDINGS_DIR);
    await this.app.vault.adapter.writeBinary(recordingRelPath, wavBuffer);

    const dateStr = `${rec.startedAt.getFullYear()}-${String(rec.startedAt.getMonth() + 1).padStart(2, "0")}-${String(rec.startedAt.getDate()).padStart(2, "0")}`;
    const noteContent = meetingNoteContent({ dateStr, recordingRelPath });
    const notePath = `Meetings/${slug} Meeting.md`;
    const noteFile = await this.app.vault.create(notePath, noteContent);

    new Notice(`Saved recording + meeting note: ${notePath}`);
    await this.app.workspace.getLeaf(true).openFile(noteFile);
  }

  async ensureFolder(folderPath) {
    if (!(await this.app.vault.adapter.exists(folderPath))) {
      await this.app.vault.createFolder(folderPath);
    }
  }

  async transcribePending() {
    const basePath = this.getBasePath();
    if (!basePath) {
      new Notice("Transcription requires the desktop app.");
      return;
    }
    const scriptPath = path.join(basePath, "scripts", "transcribe_meetings.py");

    new Notice("Transcribing pending meeting recordings…");
    try {
      const output = await this.runPython(scriptPath, [basePath]);
      const lastLine = output.trim().split("\n").filter(Boolean).pop();
      new Notice(lastLine || "No pending meeting recordings.");
      console.log("[record-meeting] transcribe output:\n" + output);
    } catch (e) {
      new Notice(`Transcription failed: ${e.message || e}`);
      console.error("[record-meeting] transcribe error", e);
    }
  }

  getBasePath() {
    const adapter = this.app.vault.adapter;
    return typeof adapter.getBasePath === "function" ? adapter.getBasePath() : null;
  }

  runPython(scriptPath, args) {
    return new Promise((resolve, reject) => {
      const tryNext = (i) => {
        if (i >= PYTHON_CANDIDATES.length) {
          reject(new Error("No Python interpreter found (tried python, python3, py)"));
          return;
        }
        const bin = PYTHON_CANDIDATES[i];
        const child = spawn(bin, [scriptPath, ...args], { windowsHide: true });
        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (d) => (stdout += d.toString()));
        child.stderr.on("data", (d) => (stderr += d.toString()));
        child.on("error", () => tryNext(i + 1));
        child.on("close", (code) => {
          if (code === 0) resolve(stdout);
          else reject(new Error(stderr.trim() || `exit code ${code}`));
        });
      };
      tryNext(0);
    });
  }
};
```

- [ ] **Step 3: Enable the plugin by default**

Edit `.obsidian/community-plugins.json` — add `"record-meeting"` to the array:
```json
[
  "dataview",
  "realclaudian",
  "smart-second-brain",
  "quickadd",
  "record-meeting"
]
```

- [ ] **Step 4: Static-verify the plugin loads syntactically**

Run: `cd "C:/Users/adamk/projects/second-brain" && node -e "require('./.obsidian/plugins/record-meeting/lib.js'); new Function(require('fs').readFileSync('.obsidian/plugins/record-meeting/main.js','utf8').replace(/require\(\"obsidian\"\)/, '({Plugin:class{},Notice:class{},setIcon(){}})')); console.log('main.js parses OK')"`
Expected: prints `main.js parses OK` (this can't exercise the Obsidian-runtime paths — that needs a
real Obsidian window — but it does prove there's no syntax error and `lib.js` is requireable, which
is what's mechanically checkable outside Obsidian itself).

Also run `node --check ".obsidian/plugins/record-meeting/main.js"` (should print nothing / exit 0 —
`--check` parses without executing, so it tolerates the top-level `require("obsidian")` that only
resolves inside Obsidian's runtime).

- [ ] **Step 5: Manual verification inside Obsidian (do this now — don't skip)**

1. Open this vault folder in Obsidian (or reload it if already open: Ctrl+P → "Reload app without saving").
2. Confirm two new ribbon icons appear on the left: a mic and a captions icon.
3. Click the mic icon, allow microphone access when prompted, say a couple of sentences including at
   least one like "I'll send the notes by Friday", then click the mic icon again (it should now show
   a stop icon while recording).
4. Confirm: a new file exists under `Meetings/recordings/*.wav` and it opened a new note
   `Meetings/<same-timestamp> Meeting.md` with `recording:` pointing at that wav and
   `transcription_status: pending`.
5. Click the captions icon. Confirm a Notice appears, then confirm the note now has
   `transcription_status: done`, a `## Transcript` with real text, and at least one
   `- [ ] ... #next [[<note name>]]` line under `## Action items` (or the "no action items detected"
   fallback line if nothing matched the heuristics — either is a pass, the point is it ran without
   error and the note was rewritten).

- [ ] **Step 6: Commit**

```bash
git add ".obsidian/plugins/record-meeting/main.js" ".obsidian/plugins/record-meeting/manifest.json" ".obsidian/community-plugins.json"
git commit -m "$(cat <<'EOF'
feat(meetings): add record-meeting Obsidian plugin (the recording button)

Hand-written CommonJS plugin, no build step — main.js is the source of
truth, same as every other vendored plugin here. Adds two ribbon
buttons: toggle recording (Web Audio -> WAV, no external encoder) and
transcribe pending (shells out to scripts/transcribe_meetings.py).
Enabled by default via community-plugins.json.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 6: Claude Code / opencode skill (`gtd-transcribe-meeting`)

**Files:**
- Create: `.claude/skills/gtd-transcribe-meeting/SKILL.md`

**Interfaces:**
- Consumes: `scripts/transcribe_meetings.py`'s CLI contract from Task 3.
- Produces: a skill discoverable the same way `gtd-dashboard` etc. are (per `AGENTS.md`), so a user
  can also say "transcribe my meetings" to Claude Code/opencode instead of clicking the Obsidian
  button — same underlying script, so behavior is identical either way.

- [ ] **Step 1: Write the skill**

Create `.claude/skills/gtd-transcribe-meeting/SKILL.md`:
```markdown
---
name: gtd-transcribe-meeting
description: Use when the user wants to transcribe a recorded meeting, process pending meeting recordings, or extract action items from a meeting recording. Triggers on "transcribe my meeting", "process the recording", "what came out of that meeting".
---

# GTD Transcribe Meeting

Transcribes every meeting note under `Meetings/` whose frontmatter has
`transcription_status: pending` (created by the `record-meeting` Obsidian plugin's recording
button, or manually by setting `recording: "[[path/to/file.wav]]"` and
`transcription_status: pending` on a note yourself), writes the transcript into that note's
`## Transcript` section, and extracts `#next` action items — linked back to the note (which itself
links to the recording) — into `## Action items`.

## Steps
1. Run: `python scripts/transcribe_meetings.py .`
2. Report each result line back to the user (`OK (N action item(s)): <note>` or
   `FAILED (<reason>): <note>`, or "No pending meeting recordings.").
3. If any note failed, open it — a `> [!fail] Transcription failed: ...` callout was added explaining
   why (commonly: the `.wav` was moved/deleted, or the vendored `vendor/whisper-cpp/whisper-cli.exe`
   is missing). Tell the user what it says; don't guess.

## Rules
- Fully offline by default — transcription runs against the vendored `vendor/whisper-cpp/` binary +
  model. Only pass `--remote-url <endpoint>` (and optionally `--api-key`) if the user explicitly
  wants a remote/OpenAI-compatible Whisper API instead; that requires network access.
- Idempotent — notes already `transcription_status: done` are left untouched, so it's always safe to
  re-run.
- Never invent a transcript or action items yourself — this skill's job is to run the script and
  relay its output, not to transcribe or summarize the meeting from the note title alone.
```

- [ ] **Step 2: Verify it's discoverable**

Run: `cd "C:/Users/adamk/projects/second-brain" && ls .claude/skills/gtd-transcribe-meeting`
Expected: `SKILL.md` listed, matching the shape of every other skill under `.claude/skills/`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-transcribe-meeting/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skills): add gtd-transcribe-meeting

Thin wrapper around scripts/transcribe_meetings.py so meeting
transcription is reachable the same way from Claude Code/opencode as
from the record-meeting Obsidian plugin's button — same script, same
behavior either way.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

---

### Task 7: Docs + final verification pass

**Files:**
- Create: `docs/gtd/meeting-recording.md`
- Modify: `README.md`, `AGENTS.md`, `docs/gtd/obsidian-plugins.md`

**Interfaces:** none (docs only) — but this task is also where the whole feature gets re-verified
end-to-end before pushing, since it's the last task in the plan.

- [ ] **Step 1: Write `docs/gtd/meeting-recording.md`**

```markdown
# Meeting recording + transcription

Two buttons, both added by the vendored `record-meeting` Obsidian plugin
(`.obsidian/plugins/record-meeting/`, enabled by default via `community-plugins.json`):

- 🎙️ **mic ribbon icon** ("Toggle meeting recording") — click once to start recording your
  microphone; click again to stop. Saves `Meetings/recordings/<timestamp>.wav` and opens a new
  `Meetings/<timestamp> Meeting.md` note with `recording: "[[...]]"` pointing at it and
  `transcription_status: pending`.
- 💬 **captions ribbon icon** ("Transcribe pending meeting recordings") — transcribes every pending
  recording and writes the result into that note's `## Transcript` section, extracting `#next`
  action items (each linked back to the note, e.g. `- [ ] Send the report. #next [[2026-09-10_...]]`)
  into `## Action items`. Action items flow into `Dashboard.md` like any other `#next` task.

Both are also in the command palette (`Ctrl+P` → "Record Meeting: ...") if you'd rather use a
hotkey, and the same transcription step is reachable from Claude Code/opencode via the
`gtd-transcribe-meeting` skill ("transcribe my meeting") if you'd rather not click anything.

## How it works offline
Recording uses the browser's own microphone + Web Audio APIs (`getUserMedia`/`AudioContext`) built
into Obsidian's desktop app and encodes straight to a `.wav` file itself — no external encoder, no
network. Transcription shells out to `vendor/whisper-cpp/whisper-cli.exe`, a vendored, fully offline
`whisper.cpp` build, against the vendored `ggml-tiny.en.bin` model — see
`vendor/whisper-cpp/README.md` for exactly what's in there and how to upgrade it. Nothing in this
feature requires internet access, `pip install`, or `npm install` — it works immediately on a fresh,
air-gapped clone of this repo.

## Optional: a remote Whisper API instead
If you'd rather use a remote/hosted Whisper endpoint (e.g. OpenAI's), run
`python scripts/transcribe_meetings.py . --remote-url https://api.openai.com/v1/audio/transcriptions
--api-key sk-...` yourself, or pass `--remote-url`/`--api-key` through to the
`gtd-transcribe-meeting` skill. This is opt-in only — the plugin's captions button always uses the
local vendored model.

## Privacy note
`Meetings/recordings/*.wav` is gitignored — your recordings stay on your machine and are never
committed, even though the code that makes and processes them is.
```

- [ ] **Step 2: Update `README.md`**

In the "What's inside" table, add a row after the "Live dashboard" row:
```markdown
| Meeting recording | 🎙️/💬 ribbon buttons (`record-meeting` plugin) to record a meeting to WAV and transcribe it — fully offline, vendored `whisper.cpp`. See `docs/gtd/meeting-recording.md`. |
```

- [ ] **Step 3: Update `AGENTS.md`**

Add a bullet under "## Skills (the interface)":
```markdown
- `gtd-transcribe-meeting` — transcribe pending meeting recordings and extract action items.
```

- [ ] **Step 4: Update `docs/gtd/obsidian-plugins.md`**

Add a new subsection under "## Optional" (before "Core plugins already enabled"):
```markdown
### Record Meeting — meeting recording + transcription
Vendored and pre-enabled (`.obsidian/plugins/record-meeting`, `.obsidian/community-plugins.json`).
Adds a mic ribbon button (record → WAV) and a captions ribbon button (transcribe pending recordings
via the vendored, fully offline `whisper.cpp` in `vendor/whisper-cpp/`). See
`docs/gtd/meeting-recording.md`. Desktop only (uses Node `child_process` + the local microphone).
```

- [ ] **Step 5: Full verification pass**

Run all of these from the repo root and confirm every one is green before moving on:
```bash
cd "C:/Users/adamk/projects/second-brain"
/c/Python313/python -m pytest scripts/ -v
node ".obsidian/plugins/record-meeting/test/lib.test.js"
node --check ".obsidian/plugins/record-meeting/main.js"
git status --short
```
Expected: pytest all green (including the Windows-gated whisper smoke test), the Node test prints
`All lib.js tests passed.`, `node --check` prints nothing, and `git status --short` shows only the
files this plan intentionally touched (no stray files from manual testing — see Step 6).

- [ ] **Step 6: Clean up any manual-testing artifacts before staging**

If Task 5's manual verification (Step 5 of that task) created a real test recording/note, decide with
the user whether to keep it as a demo or remove it — **do not silently commit it**. Run
`git status --short "Meetings/"` and only `git add` files that are meant to ship (the updated
`_templates/Meeting.md`, `Meetings/README.md`, `Meetings/recordings/.gitkeep`) — any real `.wav` is
already gitignored by Task 2, but a note created from a test recording is *not* ignored, so check for
it explicitly.

- [ ] **Step 7: Commit docs**

```bash
git add README.md AGENTS.md "docs/gtd/obsidian-plugins.md" "docs/gtd/meeting-recording.md"
git commit -m "$(cat <<'EOF'
docs: document meeting recording + transcription

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VRJvSbzAE2ypLevj8Th8Uy
EOF
)"
```

- [ ] **Step 8: Push to master**

```bash
git log --oneline origin/master..HEAD
git push origin master
```
Expected: shows exactly the commits from Tasks 1–7 (vendor whisper, meeting template, transcribe
script, plugin lib, plugin, skill, docs) — nothing else — then a successful push.
