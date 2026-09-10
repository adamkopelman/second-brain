from pathlib import Path
import json
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


def test_apply_transcript_always_leaves_pending_summary_placeholder():
    note_text = "---\ntranscription_status: pending\n---\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    out = T.apply_transcript(note_text, "Nothing actionable here.", "Stem")
    assert T.PENDING_SUMMARY_NOTE in out


def test_mark_failed_sets_status_and_appends_callout():
    note_text = "---\ntranscription_status: pending\n---\nbody\n"
    out = T.mark_failed(note_text, "boom")
    fm, body = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "failed"
    assert "boom" in body


def test_apply_transcript_preserves_yaml_list_frontmatter():
    note_text = (
        "---\n"
        "type: meeting\n"
        "attendees:\n"
        "  - Alice\n"
        "  - Bob\n"
        "tags:\n"
        "  - meeting\n"
        "  - q3\n"
        'recording: "[[x.wav]]"\n'
        "transcription_status: pending\n"
        "---\n"
        "# Meeting\n\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    )
    out = T.apply_transcript(note_text, "Hello world.", "Stem")
    assert "  - Alice" in out
    assert "  - Bob" in out
    assert "  - meeting" in out
    assert "  - q3" in out
    fm, _ = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "done"
    assert fm["summary_status"] == "pending"
    assert "transcribed" in fm


def test_mark_failed_preserves_yaml_list_frontmatter():
    note_text = (
        "---\n"
        "type: meeting\n"
        "attendees:\n"
        "  - Alice\n"
        "  - Bob\n"
        "tags:\n"
        "  - meeting\n"
        "  - q3\n"
        'recording: "[[x.wav]]"\n'
        "transcription_status: pending\n"
        "---\n"
        "# Meeting\n\n## Transcript\n\n## Action items\n- [ ]  #next\n"
    )
    out = T.mark_failed(note_text, "boom")
    assert "  - Alice" in out
    assert "  - Bob" in out
    assert "  - meeting" in out
    assert "  - q3" in out
    fm, body = T.parse_frontmatter(out)
    assert fm["transcription_status"] == "failed"
    assert "boom" in body


def test_process_marks_failed_when_recording_missing(tmp_path):
    vault = _mk_vault(tmp_path)
    (vault / "Meetings" / "recordings" / "2026-09-10_10-00-00.wav").unlink()
    results = T.process(
        vault,
        vault / "vendor" / "whisper-cpp" / "whisper-cli.exe",
        vault / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.bin",
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
    assert results[0] == "OK (transcribed): 2026-09-10_10-00-00 Meeting.md"
    note_text = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "I'll email the vendor tomorrow." in note_text
    assert T.PENDING_SUMMARY_NOTE in note_text


def test_process_is_idempotent_skips_done_notes(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_local", lambda wav, b, m: "Some transcript.")
    T.process(vault, Path("fake-bin"), Path("fake-model"), None, None)
    assert T.process(vault, Path("fake-bin"), Path("fake-model"), None, None) == []


import platform
import pytest


@pytest.mark.skipif(platform.system() != "Windows", reason="whisper-cli.exe is a Windows binary")
def test_real_vendored_whisper_binary_runs(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    whisper_bin = repo_root / "vendor" / "whisper-cpp" / "whisper-cli.exe"
    model = repo_root / "vendor" / "whisper-cpp" / "models" / "ggml-tiny.bin"
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
