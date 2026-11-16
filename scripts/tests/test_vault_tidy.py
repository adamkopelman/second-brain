import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vault_tidy as T

OLD = (dt.date.today() - dt.timedelta(days=200)).isoformat()


def _vault(v: Path):
    (v / "10 Projects").mkdir(parents=True)
    (v / "10 Projects" / "Done.md").write_text("---\nstatus: done\n---\n# Done\n- [x] a\n- [ ]  #next\n")
    (v / "10 Projects" / "DoneOpen.md").write_text("---\nstatus: done\n---\n- [ ] real task #next\n")
    (v / "10 Projects" / "Live.md").write_text("---\nstatus: active\n---\n- [ ] go #next\n")
    (v / "Meetings").mkdir()
    long = "words " * 2000
    (v / "Meetings" / f"{OLD} Sync.md").write_text(
        f"---\ndate: {OLD}\nsummary_status: done\n---\n# Sync\n## Notes\nshort\n"
        f"## Transcript\n{long}\n## Action items\n- [x] done\n")
    (v / "Journal").mkdir()
    (v / "Journal" / f"{OLD}.md").write_text("# day\n")
    (v / "Journal" / f"{OLD} review.md").write_text("#weekly-review\n")
    return v


def test_dry_run_changes_nothing(tmp_path, capsys):
    v = _vault(tmp_path)
    T.main(["--vault", str(v)])
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "PLAN" in out and "DoneOpen.md — status: done but has open" in out
    assert (v / "10 Projects" / "Done.md").exists()
    assert not (v / "40 Archive").exists()


def test_apply_archives_and_splits_transcript(tmp_path, capsys):
    v = _vault(tmp_path)
    T.main(["--vault", str(v), "--apply", "--only", "projects,transcripts,journal"])
    assert (v / "40 Archive/Projects/Done.md").exists()
    assert (v / "10 Projects/DoneOpen.md").exists() and (v / "10 Projects/Live.md").exists()
    meeting = (v / "Meetings" / f"{OLD} Sync.md").read_text()
    assert "words words" not in meeting and "## Action items" in meeting and "[[" in meeting
    tr = (v / "40 Archive/Transcripts" / f"{OLD} Sync transcript.md").read_text()
    assert tr.count("words") == 2000
    # newest weekly review stays; the plain old daily goes
    assert (v / "Journal" / f"{OLD} review.md").exists()
    assert (v / "40 Archive/Journal" / f"{OLD}.md").exists()


def test_apply_archives_old_meeting(tmp_path, capsys):
    v = _vault(tmp_path)
    T.main(["--vault", str(v), "--apply", "--only", "meetings"])
    assert (v / "40 Archive/Meetings" / f"{OLD} Sync.md").exists()


def test_apply_all_steps_archives_meeting_once(tmp_path, capsys):
    v = _vault(tmp_path)
    T.main(["--vault", str(v), "--apply"])
    assert (v / "40 Archive/Meetings" / f"{OLD} Sync.md").exists()
    assert not (v / "40 Archive/Transcripts").exists()
