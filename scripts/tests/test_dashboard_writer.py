# scripts/tests/test_dashboard_writer.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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
    assert "- [x] Pick SSG #next #computer" in text
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
