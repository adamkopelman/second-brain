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


from urllib.error import HTTPError


def _post(server, path, payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(f"http://127.0.0.1:{server.server_port}{path}", data=body,
                           method="POST", headers={"Content-Type": "application/json"})
    return request.urlopen(req)


def test_complete_task_writes_the_file(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/complete-task",
                    {"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer"}) as r:
            assert r.status == 200
        text = (tmp_path / "10 Projects" / "P.md").read_text()
        assert "- [x] Pick SSG #next #computer" in text
    finally:
        server.shutdown()


def test_complete_task_conflict_when_line_missing(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/complete-task", {"file": "10 Projects/P.md", "line_text": "- [ ] nope"})
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 409
    finally:
        server.shutdown()


def test_new_task_without_project_creates_inbox_file(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/new-task", {"text": "Call dentist", "context": "phone"}) as r:
            data = json.loads(r.read())
        assert data["file"].startswith("00 Inbox/")
        assert (tmp_path / data["file"]).is_file()
    finally:
        server.shutdown()


def test_new_project_creates_from_template(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/new-project", {"title": "New Idea"}) as r:
            data = json.loads(r.read())
        assert data["file"] == "10 Projects/New Idea.md"
        assert (tmp_path / "10 Projects" / "New Idea.md").is_file()
    finally:
        server.shutdown()


def test_delete_task_missing_required_field_is_bad_request(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/delete-task", {"file": "10 Projects/P.md"})  # no line_text
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()


def test_complete_task_rejects_path_outside_vault(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/complete-task", {"file": "../outside.md", "line_text": "x"})
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()


def test_post_with_non_json_content_type_is_rejected(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        body = json.dumps({"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer"}).encode()
        req = request.Request(f"http://127.0.0.1:{server.server_port}/api/complete-task",
                               data=body, method="POST", headers={"Content-Type": "text/plain"})
        try:
            request.urlopen(req)
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 415
    finally:
        server.shutdown()


def test_post_with_cross_origin_header_is_rejected(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        body = json.dumps({"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer"}).encode()
        req = request.Request(f"http://127.0.0.1:{server.server_port}/api/complete-task",
                               data=body, method="POST",
                               headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
        try:
            request.urlopen(req)
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 403
    finally:
        server.shutdown()


def test_edit_task_passes_through_new_context(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/edit-task",
                    {"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer",
                     "new_context": "phone"}) as r:
            data = json.loads(r.read())
        assert data["line_text"] == "- [ ] Pick SSG #next #phone"
        text = (tmp_path / "10 Projects" / "P.md").read_text()
        assert "#phone" in text
    finally:
        server.shutdown()


def test_transcribe_endpoint_reports_no_pending_meetings(tmp_path):
    _mk_vault(tmp_path)
    (tmp_path / "vendor" / "whisper-cpp").mkdir(parents=True)
    (tmp_path / "vendor" / "whisper-cpp" / "whisper-cli.exe").write_text("stub")
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/transcribe", {}) as r:
            data = json.loads(r.read())
        assert data["ok"] is True
        assert "No pending meeting recordings." in data["output"]
    finally:
        server.shutdown()


def test_transcribe_endpoint_returns_500_when_whisper_binary_missing(tmp_path):
    _mk_vault(tmp_path)  # no vendor/ dir at all
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/transcribe", {})
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 500
    finally:
        server.shutdown()


class _FakeCalendar:
    def snapshot(self):
        return {"status": "ok", "error": None, "events": [{"subject": "Standup"}], "updated": "now"}


def test_state_includes_the_calendar_snapshot(tmp_path):
    _mk_vault(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(tmp_path, calendar=_FakeCalendar()))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            data = json.loads(r.read())
        assert data["calendar"]["events"][0]["subject"] == "Standup"
    finally:
        server.shutdown()


def test_state_calendar_is_off_without_a_calendar(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            data = json.loads(r.read())
        assert data["calendar"]["status"] == "off"
    finally:
        server.shutdown()
