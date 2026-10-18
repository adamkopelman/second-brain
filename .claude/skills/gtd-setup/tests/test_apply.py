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
    assert A.main([str(tmp_path), "--no-outlook-mcp"]) == 0
    assert (d / "data.json").is_file()
    assert "created .obsidian/plugins/dataview/data.json" in capsys.readouterr().out


# --- outlook-mcp-rs.exe download (from the upstream GitHub release, not committed) ---------------
import hashlib, io, urllib.error
import pytest

EXE_REL = Path("vendor") / "outlook-mcp-rs" / "outlook-mcp-rs.exe"
REPO_ROOT = Path(__file__).resolve().parents[4]

class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.close()

def _fake_urlopen(payload, calls):
    def urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(payload)
    return urlopen

def test_outlook_mcp_downloads_and_verifies(tmp_path):
    payload, calls = b"MZ fake exe", []
    res = A.ensure_outlook_mcp(tmp_path, platform="win32", urlopen=_fake_urlopen(payload, calls),
                               sha256=hashlib.sha256(payload).hexdigest())
    assert res["status"] == "downloaded"
    assert (tmp_path / EXE_REL).read_bytes() == payload
    assert calls == [A.OUTLOOK_MCP_URL]
    assert not list((tmp_path / EXE_REL).parent.glob("*.part"))

def test_outlook_mcp_present_is_left_alone(tmp_path):
    exe = tmp_path / EXE_REL
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"my own build")
    calls = []
    res = A.ensure_outlook_mcp(tmp_path, platform="win32", urlopen=_fake_urlopen(b"x", calls))
    assert res["status"] == "present"
    assert calls == [] and exe.read_bytes() == b"my own build"

def test_outlook_mcp_checksum_mismatch_installs_nothing(tmp_path):
    res = A.ensure_outlook_mcp(tmp_path, platform="win32", urlopen=_fake_urlopen(b"tampered", []))
    assert res["status"] == "failed" and "checksum" in res["error"].lower()
    assert not (tmp_path / EXE_REL).exists()
    assert not list((tmp_path / EXE_REL).parent.glob("*.part"))

def test_outlook_mcp_offline_is_a_clear_error(tmp_path):
    def offline(url, timeout=None):
        raise urllib.error.URLError("getaddrinfo failed")
    res = A.ensure_outlook_mcp(tmp_path, platform="win32", urlopen=offline)
    assert res["status"] == "failed"
    assert "offline" in res["error"] and A.OUTLOOK_MCP_URL in res["error"]
    assert not (tmp_path / EXE_REL).exists()

def test_outlook_mcp_is_windows_only(tmp_path):
    calls = []
    res = A.ensure_outlook_mcp(tmp_path, platform="linux", urlopen=_fake_urlopen(b"x", calls))
    assert res["status"] == "skipped" and calls == []

def test_main_reports_a_failed_download_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    def offline(url, timeout=None):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(A.sys, "platform", "win32")
    monkeypatch.setattr(A.urllib.request, "urlopen", offline)
    assert A.main([str(tmp_path)]) == 1
    assert (tmp_path / "Dashboard.md").exists()           # the rest of setup still ran
    err = capsys.readouterr().err
    assert "outlook-mcp-rs" in err and "offline" in err

def test_download_scripts_pin_the_same_release_as_apply():
    scripts = REPO_ROOT / "vendor" / "outlook-mcp-rs"
    if not scripts.is_dir():
        pytest.skip("not inside the second-brain repo")
    for name in ("download-outlook-mcp-rs.ps1", "download-outlook-mcp-rs.sh"):
        text = (scripts / name).read_text(encoding="utf-8")
        assert A.OUTLOOK_MCP_VERSION in text and A.OUTLOOK_MCP_SHA256 in text, name
    assert A.OUTLOOK_MCP_URL.endswith(f"/{A.OUTLOOK_MCP_VERSION}/outlook-mcp-rs.exe")

def test_downloaded_exe_is_gitignored():
    gitignore = REPO_ROOT / ".gitignore"
    if not gitignore.is_file():
        pytest.skip("not inside the second-brain repo")
    assert "vendor/outlook-mcp-rs/*.exe" in gitignore.read_text(encoding="utf-8").splitlines()

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
