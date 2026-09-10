import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_server as S


def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# P\n\n## Next actions\n"
        "- [ ] Pick SSG #next #computer\n")
    (vault / "_templates").mkdir()
    (vault / "_templates" / "Project.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: {{date:YYYY-MM-DD}}\n"
        "review: {{date:YYYY-MM-DD}}\n---\n# {{title}}\n\n## Next actions\n")


def _start_server(vault: Path) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(vault))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_server_binds_localhost_only(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.shutdown()


def test_get_state_returns_current_tasks(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert any("Pick SSG" in t["text"] for t in data["tasks_by_context"]["#computer"])
    finally:
        server.shutdown()


def test_get_root_serves_index_html(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/") as r:
            assert r.status == 200
            assert r.headers["Content-Type"].startswith("text/html")
            body = r.read().decode()
        assert "<!doctype html>" in body.lower()
    finally:
        server.shutdown()


def test_get_unknown_path_returns_404(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        from urllib.error import HTTPError
        try:
            request.urlopen(f"http://127.0.0.1:{server.server_port}/nope")
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
