#!/usr/bin/env python3
"""Local, 127.0.0.1-only dashboard server for the vault. stdlib only."""
from __future__ import annotations
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_parser as P
import dashboard_writer as W
import outlook_calendar as OC

STATIC_DIR = Path(__file__).resolve().parent / "dashboard_static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/logic.js": ("logic.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


CALENDAR_OFF = {"status": "off", "error": None, "events": [], "updated": None}


def make_handler(vault: Path, calendar=None, auto_transcribe: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep test/console output quiet

        def _send_json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/state":
                state = P.collect_state(vault)
                state["calendar"] = calendar.snapshot() if calendar else dict(CALENDAR_OFF)
                self._send_json(state)
                return
            if path in STATIC_FILES:
                fname, ctype = STATIC_FILES[path]
                fpath = STATIC_DIR / fname
                if not fpath.is_file():
                    self._send_json({"error": "not found"}, 404)
                    return
                body = fpath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                self._send_json({"error": "cross-origin request refused"}, 403)
                return
            host_header = (self.headers.get("Host") or "").split(":")[0]
            if host_header and host_header not in ("127.0.0.1", "localhost"):
                self._send_json({"error": "invalid host"}, 403)
                return
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("application/json"):
                self._send_json({"error": "expected application/json"}, 415)
                return
            try:
                data = self._read_json()
                if path == "/api/complete-task":
                    W.complete_task(vault, data["file"], data["line_text"])
                    self._send_json({"ok": True})
                elif path == "/api/delete-task":
                    W.delete_task(vault, data["file"], data["line_text"])
                    self._send_json({"ok": True})
                elif path == "/api/edit-task":
                    new_line = W.edit_task(vault, data["file"], data["line_text"],
                                            data.get("new_text"), data.get("new_due"),
                                            data.get("new_context"))
                    self._send_json({"ok": True, "line_text": new_line})
                elif path == "/api/new-task":
                    result = W.create_task(vault, data["text"], data.get("context", "anywhere"),
                                            data.get("project"))
                    self._send_json({"ok": True, **result})
                elif path == "/api/new-project":
                    rel = W.create_project(vault, data["title"])
                    self._send_json({"ok": True, "file": rel})
                elif path == "/api/transcribe":
                    output = W.run_transcription(vault)
                    self._send_json({"ok": True, "output": output})
                else:
                    self._send_json({"error": "not found"}, 404)
            except (W.LineNotFoundError, W.AmbiguousLineError, FileExistsError) as e:
                self._send_json({"error": str(e)}, 409)
            except FileNotFoundError as e:
                self._send_json({"error": str(e)}, 404)
            except W.PathEscapesVaultError as e:
                self._send_json({"error": str(e)}, 400)
            except KeyError as e:
                self._send_json({"error": f"missing field: {e}"}, 400)
            except Exception as e:
                self._send_json({"error": "internal error: " + str(e)}, 500)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-outlook", action="store_true", help="don't read the Outlook calendar")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    calendar = None
    if not a.no_outlook:
        calendar = OC.CalendarCache(OC.resolve_command())
        calendar.start()
    server = ThreadingHTTPServer(("127.0.0.1", a.port),
                                 make_handler(vault, calendar=calendar, auto_transcribe=True))
    print(f"Dashboard server running at http://127.0.0.1:{a.port} (vault: {vault})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
