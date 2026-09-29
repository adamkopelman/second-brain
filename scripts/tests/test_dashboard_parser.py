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

def test_iter_tasks_with_location_drops_wikilink_from_text(tmp_path):
    _mk_vault(tmp_path)
    tasks = list(P.iter_tasks_with_location(tmp_path))
    waiting_task = next(t for t in tasks if "Logo files" in t["text"])
    assert waiting_task["text"] == "Logo files"

def test_iter_tasks_with_location_keeps_linked_names_as_links(tmp_path):
    _mk_vault(tmp_path)
    tasks = list(P.iter_tasks_with_location(tmp_path))
    waiting_task = next(t for t in tasks if "Logo files" in t["text"])
    assert waiting_task["links"] == ["Design Agency"]

def test_iter_tasks_with_location_omits_the_notes_own_backlink(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "Meetings").mkdir()
    (tmp_path / "Meetings" / "2026-09-10 Sync.md").write_text(
        "---\ntype: meeting\ndate: 2026-09-10\n---\n"
        "# Sync\n\n## Action items\n- [ ] Email the vendor #next #unknown [[2026-09-10 Sync]] [[Sam Rivera]]\n")
    tasks = list(P.iter_tasks_with_location(tmp_path))
    vendor = next(t for t in tasks if "Email the vendor" in t["text"])
    assert vendor["links"] == ["Sam Rivera"]

def test_iter_tasks_with_location_shows_a_links_alias(tmp_path):
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "00 Inbox" / "a.md").write_text("- [ ] Ask about figures #agenda [[Sam Rivera|Sam]]\n")
    task = next(P.iter_tasks_with_location(tmp_path))
    assert task["links"] == ["Sam"]

def test_iter_tasks_with_location_skips_blank_template_placeholders(tmp_path):
    (tmp_path / "Journal").mkdir()
    (tmp_path / "Journal" / "2026-09-10.md").write_text(
        "## Today's next actions\n- [ ]  #next\n- [ ] Real one #next\n")
    (tmp_path / "People").mkdir()
    (tmp_path / "People" / "Sam Rivera.md").write_text(
        "## Waiting for\n- [ ]  #waiting [[Sam Rivera]] [since:: 2026-09-10]\n")
    texts = [t["text"] for t in P.iter_tasks_with_location(tmp_path)]
    assert texts == ["Real one"]

def test_iter_tasks_with_location_keeps_a_task_that_is_only_a_link(tmp_path):
    (tmp_path / "10 Projects").mkdir()
    (tmp_path / "10 Projects" / "P.md").write_text("- [ ] #agenda [[Sam Rivera]]\n")
    task = next(P.iter_tasks_with_location(tmp_path))
    assert task["links"] == ["Sam Rivera"]

def _todo(state, text):
    return next(t for t in state["todos"] if t["text"] == text)


def test_collect_state_threads_links_and_vault_name(tmp_path):
    _mk_vault(tmp_path)
    state = P.collect_state(tmp_path)
    assert _todo(state, "Logo files")["links"] == ["Design Agency"]
    assert _todo(state, "Finalize homepage wireframe")["links"] == []
    assert state["vault_name"] == tmp_path.name


def test_collect_state_shapes_todos_like_things(tmp_path):
    _mk_vault(tmp_path)
    state = P.collect_state(tmp_path)
    wf = _todo(state, "Finalize homepage wireframe")
    assert wf["status"] == "next" and wf["context"] == "computer"
    assert wf["deadline"] == "2026-09-12" and wf["when"] is None and wf["evening"] is False
    assert wf["project"] == "Website Redesign" and wf["area"] == "Career"
    assert wf["heading"] == "Next actions" and wf["done"] is False and wf["inbox"] is False
    logo = _todo(state, "Logo files")
    assert logo["status"] == "waiting" and logo["since"] == "2026-09-05" and logo["heading"] == "Waiting for"
    loose = _todo(state, "loose item")
    assert loose["inbox"] is True and loose["status"] is None
    assert _todo(state, "Done already")["done"] is True


def test_collect_state_projects_carry_status_area_progress_and_headings(tmp_path):
    _mk_vault(tmp_path)
    state = P.collect_state(tmp_path)
    by_name = {p["name"]: p for p in state["projects"]}
    assert set(by_name) == {"Website Redesign", "Plan Family Trip", "Learn Spanish"}
    web = by_name["Website Redesign"]
    assert web["status"] == "active" and web["area"] == "Career"
    assert (web["open"], web["done"]) == (2, 1)
    assert web["headings"] == ["Next actions", "Waiting for"]
    trip = by_name["Plan Family Trip"]
    assert trip["review"] == "2026-09-03" and trip["review_overdue"] is True
    assert by_name["Learn Spanish"]["status"] == "someday"
    assert by_name["Learn Spanish"]["review_overdue"] is False  # someday projects aren't reviewed weekly
    assert state["areas"] == [{"name": "Career", "file": None}]


def test_collect_state_lists_area_notes_and_their_todos(tmp_path):
    (tmp_path / "20 Areas").mkdir(parents=True)
    (tmp_path / "20 Areas" / "Health.md").write_text("# Health\n\n## Next actions\n- [ ] Book a checkup\n")
    state = P.collect_state(tmp_path)
    assert state["areas"] == [{"name": "Health", "file": "20 Areas/Health.md"}]
    t = _todo(state, "Book a checkup")
    assert t["area"] == "Health" and t["project"] is None


def test_collect_state_reads_when_evening_and_completion(tmp_path):
    (tmp_path / "Journal").mkdir(parents=True)
    (tmp_path / "Journal" / "2026-09-10.md").write_text(
        "- [ ] Call mom #next #phone #evening [scheduled:: 2026-09-10]\n"
        "- [x] Old one #next [completion:: 2026-09-08]\n"
        "- [x] Tasks-plugin one #next \u2705 2026-09-09\n"
        "- [ ] untagged journal line\n"
        "- [ ] Read #someday #reading\n", encoding="utf-8")
    state = P.collect_state(tmp_path)
    mom = _todo(state, "Call mom")
    assert mom["when"] == "2026-09-10" and mom["evening"] is True and mom["context"] == "phone"
    assert _todo(state, "Read")["tags"] == ["reading"]
    done = [t for t in state["todos"] if t["done"]]
    assert [t["completed"] for t in done] == ["2026-09-09", "2026-09-08"]  # newest first
    assert done[0]["text"] == "Tasks-plugin one"
    assert not any(t["text"] == "untagged journal line" for t in state["todos"])


def test_collect_state_on_empty_vault(tmp_path):
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "00 Inbox" / "README.md").write_text("# Inbox\n")
    state = P.collect_state(tmp_path)
    assert state["todos"] == [] and state["projects"] == [] and state["areas"] == []
    assert state["inbox_notes"] == []


def test_collect_state_extracts_project_outcome(tmp_path):
    (tmp_path / "10 Projects").mkdir(parents=True)
    (tmp_path / "10 Projects" / "Filled.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# Filled\n\n"
        "**Outcome:** New site launched with updated branding.\n\n## Next actions\n")
    (tmp_path / "10 Projects" / "Blank.md").write_text(
        "---\ntype: project\nstatus: someday\n---\n# Blank\n\n"
        '**Outcome:** _What does "done" look like?_\n')
    (tmp_path / "10 Projects" / "Finished.md").write_text(
        "---\ntype: project\nstatus: done\n---\n# Finished\n- [ ] leftover #next\n")
    state = P.collect_state(tmp_path)
    by_name = {p["name"]: p for p in state["projects"]}
    assert by_name["Filled"]["outcome"] == "New site launched with updated branding."
    assert by_name["Blank"]["outcome"] is None
    assert "Finished" not in by_name
    assert not any(t["text"] == "leftover" for t in state["todos"])


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
    task = _todo(state, "Email the vendor")
    assert task["context"] == "unknown"
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


def test_collect_state_lists_inbox_notes_without_checkboxes(tmp_path):
    _mk_vault(tmp_path)
    ib = tmp_path / "00 Inbox"
    (ib / "2026-09-10 call-plumber.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-10\n---\n- [ ] Call plumber about the leaky faucet\n", encoding="utf-8")
    (ib / "2026-09-11 idea.md").write_text(
        "---\ntype: inbox\n---\n\nCheck out [[Atomic Habits]] — recommended by Sam\nsecond line\n", encoding="utf-8")
    (ib / "2026-09-11 hebrew.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-11\n---\n- [ ] להתקשר לאינסטלטור #next #phone\n", encoding="utf-8")
    (ib / "2026-09-12 empty.md").write_text("---\ntype: inbox\ncaptured: 2026-09-12\n---\n", encoding="utf-8")
    state = P.collect_state(tmp_path)
    notes = {i["file"]: i for i in state["inbox_notes"]}
    # captures with a checkbox are to-dos; only the rest are notes
    assert set(notes) == {"00 Inbox/2026-09-11 idea.md", "00 Inbox/2026-09-12 empty.md"}
    assert notes["00 Inbox/2026-09-11 idea.md"]["text"] == "Check out Atomic Habits — recommended by Sam"
    assert notes["00 Inbox/2026-09-11 idea.md"]["captured"] == "2026-09-11"  # from the file name
    assert notes["00 Inbox/2026-09-12 empty.md"]["text"] == "2026-09-12 empty"  # falls back to the name
    inbox_todos = {t["text"] for t in state["todos"] if t["inbox"]}
    assert inbox_todos == {"loose item", "Call plumber about the leaky faucet", "להתקשר לאינסטלטור"}
