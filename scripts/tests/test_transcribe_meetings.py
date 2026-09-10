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
