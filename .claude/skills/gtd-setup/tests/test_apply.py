from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply as A

SCAFFOLD = Path(__file__).resolve().parents[1] / "scaffold" / "vault"
PLUGIN_DATA = Path(__file__).resolve().parents[1] / "scaffold" / "plugin-data"

def _install_plugin(vault, plugin_id):
    d = vault / ".obsidian" / "plugins" / plugin_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text('{"id": "%s"}' % plugin_id)
    return d

def test_plugin_presets_exist_for_dataview_and_quickadd():
    assert (PLUGIN_DATA / "dataview" / "data.json").is_file()
    assert (PLUGIN_DATA / "quickadd" / "data.json").is_file()

def test_plugin_data_goes_only_into_installed_plugins(tmp_path):
    d = _install_plugin(tmp_path, "dataview")
    res = A.apply_plugin_data(PLUGIN_DATA, tmp_path)
    assert (d / "data.json").read_bytes() == (PLUGIN_DATA / "dataview" / "data.json").read_bytes()
    assert res["created"] == [".obsidian/plugins/dataview/data.json"]
    # quickadd isn't installed (e.g. its submodule wasn't checked out): don't create its folder,
    # or a later `git submodule update --init` would find a non-empty directory
    assert not (tmp_path / ".obsidian" / "plugins" / "quickadd").exists()
    assert res["missing"] == ["quickadd"]

def test_plugin_data_never_overwrites_user_settings(tmp_path):
    d = _install_plugin(tmp_path, "quickadd")
    (d / "data.json").write_text("{}")
    res = A.apply_plugin_data(PLUGIN_DATA, tmp_path)
    assert (d / "data.json").read_text() == "{}"
    assert res["skipped"] == [".obsidian/plugins/quickadd/data.json"]
    A.apply_plugin_data(PLUGIN_DATA, tmp_path, force=True)
    assert (d / "data.json").read_bytes() == (PLUGIN_DATA / "quickadd" / "data.json").read_bytes()

def test_main_installs_presets_for_installed_plugins(tmp_path, capsys):
    d = _install_plugin(tmp_path, "dataview")
    assert A.main([str(tmp_path)]) == 0
    assert (d / "data.json").is_file()
    assert "created .obsidian/plugins/dataview/data.json" in capsys.readouterr().out

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
    assert (tmp_path / "Dashboard.md").read_text(encoding="utf-8") != "X"
