from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply as A

SCAFFOLD = Path(__file__).resolve().parents[1] / "scaffold" / "vault"

def test_apply_creates_all_assets(tmp_path):
    res = A.apply(SCAFFOLD, tmp_path)
    assert (tmp_path / "30 Resources" / "GTD System.md").exists()
    assert (tmp_path / "Dashboard.md").exists()
    assert (tmp_path / ".obsidian" / "app.json").exists()
    assert res["created"] and not res["skipped"]

def test_apply_is_idempotent(tmp_path):
    A.apply(SCAFFOLD, tmp_path)
    res2 = A.apply(SCAFFOLD, tmp_path)
    assert res2["created"] == []          # nothing new the second time
    assert res2["skipped"]                # everything skipped

def test_apply_never_overwrites_user_edits(tmp_path):
    target = tmp_path / "Dashboard.md"
    A.apply(SCAFFOLD, tmp_path)
    target.write_text("MY EDITS")
    A.apply(SCAFFOLD, tmp_path)           # no --force
    assert target.read_text() == "MY EDITS"

def test_force_overwrites(tmp_path):
    A.apply(SCAFFOLD, tmp_path)
    (tmp_path / "Dashboard.md").write_text("X")
    A.apply(SCAFFOLD, tmp_path, force=True)
    assert (tmp_path / "Dashboard.md").read_text() != "X"
