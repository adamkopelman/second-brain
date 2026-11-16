import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gtd_query as Q

TODAY = dt.date.today()
PAST = (TODAY - dt.timedelta(days=30)).isoformat()
FUTURE = (TODAY + dt.timedelta(days=30)).isoformat()


def _vault(v: Path):
    (v / "00 Inbox").mkdir(parents=True)
    (v / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (v / "00 Inbox" / "2026-11-01 call mom.md").write_text("---\ncaptured: 2026-11-01\n---\nCall mom\n")
    (v / "10 Projects").mkdir()
    (v / "10 Projects" / "Kitchen.md").write_text(
        "---\ntype: project\nstatus: active\nreview: " + PAST + "\n---\n# Kitchen\n"
        "- [ ] Call plumber #next #phone [due:: " + PAST + "]\n"
        "- [ ] Buy tiles #next #errands [scheduled:: " + FUTURE + "]\n"
        "- [ ] Quote #waiting [[Sam]] [since:: " + PAST + "]\n"
        "- [x] Measure #next #home\n")
    (v / "10 Projects" / "Stuck.md").write_text("---\nstatus: active\n---\n# Stuck\n")
    (v / "10 Projects" / "Old.md").write_text("---\nstatus: done\n---\n# Old\n")
    (v / "Journal").mkdir()
    return v


def run(v, *args, capsys):
    Q.main(["--vault", str(v), *args])
    return capsys.readouterr().out


def test_next_hides_future_scheduled_and_done_and_gives_line(tmp_path, capsys):
    out = run(_vault(tmp_path), "next", capsys=capsys)
    assert "1 open #next" in out
    assert "Call plumber" in out and "10 Projects/Kitchen.md:7" in out
    assert "Buy tiles" not in out and "Measure" not in out


def test_next_filters_context(tmp_path, capsys):
    out = run(_vault(tmp_path), "next", "--ctx", "@errands", capsys=capsys)
    assert out.startswith("0 open #next @errands")


def test_brief_and_inbox(tmp_path, capsys):
    v = _vault(tmp_path)
    out = run(v, "brief", capsys=capsys)
    assert "Inbox 1 · active projects 2 · open #next 1" in out and "none yet" in out
    out = run(v, "inbox", capsys=capsys)
    assert "Call mom" in out and "README" not in out


def test_health_finds_each_problem(tmp_path, capsys):
    out = run(_vault(tmp_path), "health", capsys=capsys)
    for tag in ("STUCK     10 Projects/Stuck.md", "REVIEW    10 Projects/Kitchen.md",
                "ARCHIVE   10 Projects/Old.md", "STALE", "OVERDUE", "INBOX", "WEEKLY"):
        assert tag in out, tag


def test_waiting_find_projects(tmp_path, capsys):
    v = _vault(tmp_path)
    assert "⚠" in run(v, "waiting", capsys=capsys)
    assert "Quote" in run(v, "find", "quote", capsys=capsys)
    out = run(v, "projects", capsys=capsys)
    assert "Kitchen [active] next 2 · waiting 1" in out and "Old" not in out
