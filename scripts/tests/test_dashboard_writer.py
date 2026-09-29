# scripts/tests/test_dashboard_writer.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import datetime as dt
import wave
import dashboard_writer as W
import pytest

def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# P\n\n## Next actions\n"
        "- [ ] Pick SSG #next #computer\n- [ ] Buy domain #next #computer\n")
    (vault / "10 Projects" / "NoHeading.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# NoHeading\n")
    (vault / "_templates").mkdir()
    (vault / "_templates" / "Project.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: {{date:YYYY-MM-DD}}\n"
        "review: {{date:YYYY-MM-DD}}\n---\n# {{title}}\n\n## Next actions\n")

def test_complete_task_flips_checkbox(tmp_path):
    _mk_vault(tmp_path)
    W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer")
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert f"- [x] Pick SSG #next #computer [completion:: {dt.date.today().isoformat()}]" in text
    assert "- [ ] Buy domain #next #computer" in text  # untouched

def test_complete_task_missing_line_raises(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(W.LineNotFoundError):
        W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] does not exist")

def test_complete_task_ambiguous_line_raises(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text() + "- [ ] Pick SSG #next #computer\n")  # duplicate the line
    with pytest.raises(W.AmbiguousLineError):
        W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer")

def test_delete_task_removes_the_line(tmp_path):
    _mk_vault(tmp_path)
    W.delete_task(tmp_path, "10 Projects/P.md", "- [ ] Buy domain #next #computer")
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "Buy domain" not in text
    assert "Pick SSG" in text

def test_edit_task_changes_text_and_preserves_tags(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer",
                            new_text="Pick a static site generator")
    assert new_line == "- [ ] Pick a static site generator #next #computer"
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "Pick a static site generator #next #computer" in text

def test_edit_task_sets_due_date(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Buy domain #next #computer",
                            new_due="2026-09-20")
    assert new_line == "- [ ] Buy domain #next #computer [due:: 2026-09-20]"

def test_edit_task_updates_existing_due_date(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text().replace(
        "- [ ] Pick SSG #next #computer", "- [ ] Pick SSG #next #computer [due:: 2026-09-10]"))
    new_line = W.edit_task(tmp_path, "10 Projects/P.md",
                            "- [ ] Pick SSG #next #computer [due:: 2026-09-10]", new_due="2026-09-20")
    assert new_line == "- [ ] Pick SSG #next #computer [due:: 2026-09-20]"

def test_create_task_without_project_writes_one_file_to_inbox(tmp_path):
    _mk_vault(tmp_path)
    result = W.create_task(tmp_path, "Call the dentist", "phone")
    inbox_files = list((tmp_path / "00 Inbox").glob("*.md"))
    assert len(inbox_files) == 1
    assert result["file"] == "00 Inbox/" + inbox_files[0].name
    content = inbox_files[0].read_text()
    assert "type: inbox" in content
    assert "- [ ] Call the dentist #next #phone" in content
    assert result["line_text"] == "- [ ] Call the dentist #next #phone"

def test_create_task_with_project_inserts_under_next_actions(tmp_path):
    _mk_vault(tmp_path)
    result = W.create_task(tmp_path, "Ship v1", "computer", project="P")
    assert result["file"] == "10 Projects/P.md"
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "- [ ] Ship v1 #next #computer" in text

def test_create_task_with_project_creates_missing_heading(tmp_path):
    _mk_vault(tmp_path)
    W.create_task(tmp_path, "Do the thing", "anywhere", project="NoHeading")
    text = (tmp_path / "10 Projects" / "NoHeading.md").read_text()
    assert "## Next actions" in text
    assert "- [ ] Do the thing #next #anywhere" in text

def test_create_task_names_a_hebrew_capture_after_its_text(tmp_path):
    _mk_vault(tmp_path)
    a = W.create_task(tmp_path, "לקנות מתנה לדנה", "errands")
    b = W.create_task(tmp_path, "להתקשר לאינסטלטור", "phone")
    assert a["file"].endswith(" לקנות-מתנה-לדנה.md")  # was "item.md" for every Hebrew task
    assert b["file"].endswith(" להתקשר-לאינסטלטור.md")
    assert W.create_task(tmp_path, "!!!", "phone")["file"].endswith(" item.md")  # nothing usable left


def test_edit_task_with_an_empty_due_removes_the_due_date(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "10 Projects" / "P.md").write_text(
        "# P\n- [ ] Pick SSG #next #computer [due:: 2026-09-10]\n", encoding="utf-8")
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer [due:: 2026-09-10]",
                           new_text="Pick SSG", new_due="")
    assert new_line == "- [ ] Pick SSG #next #computer"


def test_create_task_unknown_project_raises(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(FileNotFoundError):
        W.create_task(tmp_path, "x", "computer", project="DoesNotExist")

def test_create_project_from_template(tmp_path):
    _mk_vault(tmp_path)
    rel = W.create_project(tmp_path, "New Idea")
    assert rel == "10 Projects/New Idea.md"
    text = (tmp_path / "10 Projects" / "New Idea.md").read_text()
    assert "# New Idea" in text
    assert "{{" not in text  # every template placeholder was substituted

def test_create_project_refuses_to_overwrite(tmp_path):
    _mk_vault(tmp_path)
    W.create_project(tmp_path, "New Idea")
    with pytest.raises(FileExistsError):
        W.create_project(tmp_path, "New Idea")

def test_complete_task_refuses_path_escaping_vault(tmp_path):
    _mk_vault(tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("- [ ] victim line\n")
    with pytest.raises(W.PathEscapesVaultError):
        W.complete_task(tmp_path, "../outside.md", "- [ ] victim line")
    assert "- [ ] victim line" in outside.read_text()  # untouched

def test_create_project_refuses_path_escaping_vault(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(W.PathEscapesVaultError):
        W.create_project(tmp_path, "../../outside")

def test_edit_task_on_non_checkbox_line_raises(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text() + "# Not a task\n")
    with pytest.raises(W.LineNotFoundError):
        W.edit_task(tmp_path, "10 Projects/P.md", "# Not a task", new_text="x")

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

def test_edit_task_does_not_duplicate_wikilink_text(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "2026-09-10 Sync.md").write_text(
        "---\ntype: meeting\ndate: 2026-09-10\n---\n"
        "# Sync\n\n## Action items\n"
        "- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]\n")
    line = "- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]"
    new_line = W.edit_task(tmp_path, "Meetings/2026-09-10 Sync.md", line,
                            new_text="Email the vendor", new_context="phone")
    assert new_line == "- [ ] Email the vendor #next #phone [[2026-09-10 Sync]]"
    # simulate a second save with the same (correct, undupped) prefilled text — must be a fixed point
    new_line2 = W.edit_task(tmp_path, "Meetings/2026-09-10 Sync.md", new_line,
                             new_text="Email the vendor", new_context="phone")
    assert new_line2 == new_line

def test_edit_task_fallback_text_drops_wikilink(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "2026-09-10 Sync.md").write_text(
        "---\ntype: meeting\ndate: 2026-09-10\n---\n"
        "# Sync\n\n## Action items\n"
        "- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]\n")
    line = "- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]]"
    # no new_text given — edit_task must fall back to the link-dropping cleaner, not BD._clean
    new_line = W.edit_task(tmp_path, "Meetings/2026-09-10 Sync.md", line, new_due="2026-09-20")
    assert new_line == "- [ ] Email the vendor #next #unknown [due:: 2026-09-20] [[2026-09-10 Sync]]"

def test_edit_task_empty_string_context_is_a_noop(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer",
                            new_context="")
    assert new_line == "- [ ] Pick SSG #next #computer"

def test_run_transcription_reports_no_pending_meetings(tmp_path):
    (tmp_path / "vendor" / "whisper-cpp").mkdir(parents=True)
    (tmp_path / "vendor" / "whisper-cpp" / "whisper-cli.exe").write_text("stub")
    out = W.run_transcription(tmp_path)
    assert out == "No pending meeting recordings."

def test_run_transcription_raises_on_failure(tmp_path):
    with pytest.raises(RuntimeError):
        W.run_transcription(tmp_path)  # no vendored whisper binary present


def test_save_meeting_recording_writes_a_wav_and_a_linked_pending_note(tmp_path):
    started = dt.datetime(2026, 9, 11, 14, 0, 5)
    out = W.save_meeting_recording(tmp_path, b"\x00\x10" * 16000, started,
                                   title="סנכרון שבועי: צוות", attendees="Dana; Omer")
    assert out == {"note": "Meetings/2026-09-11_14-00-05 סנכרון שבועי צוות.md",
                   "recording": "Meetings/recordings/2026-09-11_14-00-05.wav"}
    with wave.open(str(tmp_path / out["recording"]), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 16000)
    note = (tmp_path / out["note"]).read_text(encoding="utf-8")
    assert "transcription_status: pending" in note
    assert 'recording: "[[Meetings/recordings/2026-09-11_14-00-05.wav]]"' in note
    assert "# סנכרון שבועי: צוות" in note
    assert 'attendees: "Dana; Omer"' in note
    import transcribe_meetings as T  # the transcription script must find this recording
    fm, _ = T.parse_frontmatter(note)
    assert T.resolve_recording(tmp_path, fm) == tmp_path / out["recording"]
    assert (tmp_path / out["note"]) in T.find_pending(tmp_path)


def test_save_meeting_recording_without_a_title_matches_the_obsidian_plugin(tmp_path):
    out = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, dt.datetime(2026, 9, 11, 9, 5, 0))
    assert out["note"] == "Meetings/2026-09-11_09-05-00 Meeting.md"
    note = (tmp_path / out["note"]).read_text(encoding="utf-8")
    assert "# Meeting 2026-09-11" in note
    assert "attendees: \n" in note


def test_save_meeting_recording_never_overwrites(tmp_path):
    started = dt.datetime(2026, 9, 11, 9, 5, 0)
    a = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, started, title="Sync")
    b = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, started, title="Sync")
    assert a["note"] != b["note"] and a["recording"] != b["recording"]
    assert (tmp_path / b["note"]).read_text(encoding="utf-8").count(b["recording"]) == 1


def test_save_meeting_recording_rejects_empty_audio(tmp_path):
    with pytest.raises(ValueError):
        W.save_meeting_recording(tmp_path, b"", dt.datetime(2026, 9, 11, 9, 0, 0))


def test_start_background_transcription_runs_transcription(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "run_transcription", lambda vault: calls.append(vault) or "ok")
    W.start_background_transcription(tmp_path).join(timeout=5)
    assert calls == [tmp_path]


TODAY = dt.date.today().isoformat()
LINE = "- [ ] Pick SSG #next #computer"


def _p(vault):
    return (vault / "10 Projects" / "P.md").read_text()


def test_uncomplete_task_reopens_it_and_drops_the_completion_date(tmp_path):
    _mk_vault(tmp_path)
    done = W.complete_task(tmp_path, "10 Projects/P.md", LINE)
    assert W.uncomplete_task(tmp_path, "10 Projects/P.md", done) == LINE
    assert LINE in _p(tmp_path)


def test_uncomplete_task_drops_a_tasks_plugin_completion_emoji(tmp_path):
    (tmp_path / "Journal").mkdir()
    (tmp_path / "Journal" / "d.md").write_text("- [x] Walk #next \u2705 2026-09-01\n", encoding="utf-8")
    assert W.uncomplete_task(tmp_path, "Journal/d.md", "- [x] Walk #next \u2705 2026-09-01") == "- [ ] Walk #next"


@pytest.mark.parametrize("when,expected", [
    ("today", f"- [ ] Pick SSG #next #computer [scheduled:: {TODAY}]"),
    ("evening", f"- [ ] Pick SSG #next #computer #evening [scheduled:: {TODAY}]"),
    ("2026-12-01", "- [ ] Pick SSG #next #computer [scheduled:: 2026-12-01]"),
    ("someday", "- [ ] Pick SSG #computer #someday"),
    ("anytime", LINE),
    ("", LINE),
])
def test_edit_task_sets_when(tmp_path, when, expected):
    _mk_vault(tmp_path)
    assert W.edit_task(tmp_path, "10 Projects/P.md", LINE, new_when=when) == expected
    assert expected in _p(tmp_path)


def test_edit_task_when_brings_a_someday_task_back_and_clears_evening(tmp_path):
    _mk_vault(tmp_path)
    evening = W.edit_task(tmp_path, "10 Projects/P.md", LINE, new_when="evening")
    someday = W.edit_task(tmp_path, "10 Projects/P.md", evening, new_when="someday")
    assert someday == "- [ ] Pick SSG #computer #someday"
    back = W.edit_task(tmp_path, "10 Projects/P.md", someday, new_when="2026-12-01")
    assert back == "- [ ] Pick SSG #computer #next [scheduled:: 2026-12-01]"


def test_edit_task_when_keeps_a_waiting_task_waiting(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "10 Projects" / "P.md").write_text("- [ ] Figures #waiting [since:: 2026-09-01] [[Sam]]\n")
    line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Figures #waiting [since:: 2026-09-01] [[Sam]]",
                       new_when="2026-10-01")
    assert line == "- [ ] Figures #waiting [since:: 2026-09-01] [scheduled:: 2026-10-01] [[Sam]]"


def test_edit_task_rejects_a_malformed_date(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(ValueError):
        W.edit_task(tmp_path, "10 Projects/P.md", LINE, new_when="next tuesday")
    assert LINE in _p(tmp_path)


def test_create_task_with_when_deadline_and_a_typed_context(tmp_path):
    _mk_vault(tmp_path)
    r = W.create_task(tmp_path, "Call the bank #phone", "anywhere", project="P", when="evening",
                      deadline="2026-10-02")
    assert r["line_text"] == f"- [ ] Call the bank #phone #next #evening [scheduled:: {TODAY}] [due:: 2026-10-02]"
    assert r["line_text"] in _p(tmp_path)


def test_create_task_someday_and_waiting(tmp_path):
    _mk_vault(tmp_path)
    assert W.create_task(tmp_path, "Learn to sail", None, project="P", status="someday")["line_text"] == \
        "- [ ] Learn to sail #someday"
    assert W.create_task(tmp_path, "Figures from Sam", None, project="P", status="waiting")["line_text"] == \
        f"- [ ] Figures from Sam #waiting [since:: {TODAY}]"


def test_create_task_in_an_area_note(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "20 Areas").mkdir()
    (tmp_path / "20 Areas" / "Health.md").write_text("# Health\n")
    r = W.create_task(tmp_path, "Book a checkup", "phone", area="Health")
    assert r["file"] == "20 Areas/Health.md"
    assert (tmp_path / "20 Areas" / "Health.md").read_text().endswith("## Next actions\n\n- [ ] Book a checkup #next #phone\n")
    with pytest.raises(FileNotFoundError):
        W.create_task(tmp_path, "x", "phone", area="Nope")


def test_move_task_from_the_inbox_to_a_project_removes_the_capture(tmp_path):
    _mk_vault(tmp_path)
    cap = W.create_task(tmp_path, "Compare hosting", "computer")
    r = W.move_task(tmp_path, cap["file"], cap["line_text"], project="P")
    assert r == {"file": "10 Projects/P.md", "line_text": cap["line_text"]}
    assert not (tmp_path / cap["file"]).exists()
    assert "- [ ] Buy domain #next #computer\n- [ ] Compare hosting #next #computer\n" in _p(tmp_path)


def test_move_task_between_projects_and_back_to_the_inbox(tmp_path):
    _mk_vault(tmp_path)
    W.move_task(tmp_path, "10 Projects/P.md", LINE, project="NoHeading")
    assert LINE not in _p(tmp_path)
    assert (tmp_path / "10 Projects" / "NoHeading.md").read_text().endswith("## Next actions\n\n" + LINE + "\n")
    r = W.move_task(tmp_path, "10 Projects/NoHeading.md", LINE)
    assert r["file"].startswith("00 Inbox/") and LINE in (tmp_path / r["file"]).read_text()


def test_move_task_to_where_it_already_is_changes_nothing(tmp_path):
    _mk_vault(tmp_path)
    before = _p(tmp_path)
    assert W.move_task(tmp_path, "10 Projects/P.md", LINE, project="P")["file"] == "10 Projects/P.md"
    assert _p(tmp_path) == before


def test_delete_task_removes_an_emptied_inbox_capture(tmp_path):
    _mk_vault(tmp_path)
    cap = W.create_task(tmp_path, "Stray thought", "anywhere")
    W.delete_task(tmp_path, cap["file"], cap["line_text"])
    assert not (tmp_path / cap["file"]).exists()


def test_mark_project_reviewed_and_status(tmp_path):
    _mk_vault(tmp_path)
    nxt = W.mark_project_reviewed(tmp_path, "P", days=7)
    assert nxt == (dt.date.today() + dt.timedelta(days=7)).isoformat()
    assert f"review: {nxt}" in _p(tmp_path)
    W.mark_project_reviewed(tmp_path, "P", days=14)
    assert _p(tmp_path).count("review:") == 1
    W.set_project_status(tmp_path, "P", "done")
    text = _p(tmp_path)
    assert "status: done" in text and f"completed: {TODAY}" in text and "status: active" not in text
    assert text.endswith("- [ ] Buy domain #next #computer\n")  # body untouched
    with pytest.raises(ValueError):
        W.set_project_status(tmp_path, "P", "paused")


def test_create_project_in_an_area(tmp_path):
    _mk_vault(tmp_path)
    rel = W.create_project(tmp_path, "Garden", area="Home")
    assert 'area: "[[Home]]"' in (tmp_path / rel).read_text()


def test_create_task_keeps_a_status_typed_into_the_text(tmp_path):
    _mk_vault(tmp_path)
    assert W.create_task(tmp_path, "Learn to sail #someday", None, project="P")["line_text"] == \
        "- [ ] Learn to sail #someday"
