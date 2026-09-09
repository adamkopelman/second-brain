from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_dashboard as B

def _mk(vault: Path):
    (vault / "30 Resources").mkdir(parents=True)
    (vault / "30 Resources" / "GTD System.md").write_text("# GTD\n")
    (vault / "00 Inbox").mkdir()
    (vault / "00 Inbox" / "a.md").write_text("- [ ] loose\n")
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n"
        "- [ ] Pick SSG #next #computer [due:: 2026-09-15] [[P]]\n"
        "- [ ] Wait domain #waiting [[Reg]] [since:: 2026-09-02]\n")

def test_collect_counts(tmp_path):
    _mk(tmp_path)
    d = B.collect(tmp_path)
    assert d["inbox"] == 1
    assert d["active_projects"] == ["P"]
    assert any("Pick SSG" in x for x in d["next_by_context"].get("#computer", []))
    assert any("Wait domain" in x for x in d["waiting"])

def test_render_is_self_contained_html(tmp_path):
    _mk(tmp_path)
    html = B.render(B.collect(tmp_path), generated="2026-09-09")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html   # no external assets
    assert "Pick SSG" in html
