from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_parser as P

def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "00 Inbox" / "loose.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-09\n---\n- [ ] loose item\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "README.md").write_text("# Projects\n")
    (vault / "10 Projects" / "Website Redesign.md").write_text(
        "---\ntype: project\nstatus: active\narea: \"[[Career]]\"\n"
        "created: 2026-09-01\nreview: 2026-09-15\n---\n"
        "# Website Redesign\n\n## Next actions\n"
        "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]\n"
        "- [x] Done already #next #computer\n\n"
        "## Waiting for\n"
        "- [ ] Logo files #waiting [[Design Agency]] [since:: 2026-09-05]\n")
    (vault / "10 Projects" / "Plan Family Trip.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: 2026-08-20\nreview: 2026-09-03\n---\n"
        "# Plan Family Trip\n\n## Next actions\n")
    (vault / "10 Projects" / "Learn Spanish.md").write_text(
        "---\ntype: project\nstatus: someday\ncreated: 2026-09-01\nreview: 2026-12-01\n---\n"
        "# Learn Spanish\n")

def test_iter_tasks_with_location_finds_file_and_exact_line(tmp_path):
    _mk_vault(tmp_path)
    tasks = list(P.iter_tasks_with_location(tmp_path))
    wireframe = next(t for t in tasks if "wireframe" in t["text"])
    assert wireframe["file"] == "10 Projects/Website Redesign.md"
    assert wireframe["line_text"] == "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]"
    assert wireframe["done"] is False
    assert wireframe["project"] == "Website Redesign"
    assert "#next" in wireframe["tags"] and "#computer" in wireframe["tags"]
    assert wireframe["fields"] == {"due": "2026-09-12"}
    done_task = next(t for t in tasks if t["text"] == "Done already")
    assert done_task["done"] is True
    inbox_task = next(t for t in tasks if t["text"] == "loose item")
    assert inbox_task["project"] is None
    assert inbox_task["file"] == "00 Inbox/loose.md"

def test_collect_state_counts_and_groups(tmp_path):
    _mk_vault(tmp_path)
    state = P.collect_state(tmp_path)
    assert state["inbox_count"] == 1
    assert len(state["tasks_by_context"]["#computer"]) == 1
    assert state["tasks_by_context"]["#computer"][0]["text"] == "Finalize homepage wireframe"
    assert len(state["waiting"]) == 1
    assert state["waiting"][0]["since"] == "2026-09-05"
    assert len(state["due_soon"]) == 1  # due 2026-09-12 is within 7 days of "today" in fixture-independent terms
    names = {p["name"] for p in state["active_projects"]}
    assert names == {"Website Redesign", "Plan Family Trip"}
    trip = next(p for p in state["active_projects"] if p["name"] == "Plan Family Trip")
    assert trip["review"] == "2026-09-03"
    assert trip["review_overdue"] is True  # 2026-09-03 is in the past relative to any real test run
    someday_names = {p["name"] for p in state["someday_projects"]}
    assert someday_names == {"Learn Spanish"}

def test_collect_state_on_empty_vault(tmp_path):
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "00 Inbox" / "README.md").write_text("# Inbox\n")
    state = P.collect_state(tmp_path)
    assert state["inbox_count"] == 0
    assert state["tasks_by_context"] == {}
    assert state["waiting"] == []
    assert state["active_projects"] == []

def test_collect_state_extracts_project_outcome(tmp_path):
    (tmp_path / "10 Projects").mkdir(parents=True)
    (tmp_path / "10 Projects" / "Filled.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# Filled\n\n"
        "**Outcome:** New site launched with updated branding.\n\n## Next actions\n")
    (tmp_path / "10 Projects" / "Blank.md").write_text(
        "---\ntype: project\nstatus: someday\n---\n# Blank\n\n"
        '**Outcome:** _What does "done" look like?_\n')
    state = P.collect_state(tmp_path)
    filled = next(p for p in state["active_projects"] if p["name"] == "Filled")
    assert filled["outcome"] == "New site launched with updated branding."
    blank = next(p for p in state["someday_projects"] if p["name"] == "Blank")
    assert blank["outcome"] is None

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
