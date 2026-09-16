"""HTTP surface: the JSON job API, an OpenAI-compatible sync shim, health probes, and the UI."""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .multipart import (MalformedMultipart, MultipartTooLarge, boundary_from_content_type,
                        parse_multipart)

JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".flac", ".ogg", ".oga", ".opus",
                            ".webm", ".mpga", ".mpeg", ".aac", ".wma"}
STATIC_TYPES = {".html": "text/html; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon"}


class EngineState:
    """Shared between the deferred model load and the readiness probe."""

    def __init__(self):
        self._ready = False
        self.error = None

    @property
    def ready(self) -> bool:
        return self._ready

    def mark_ready(self) -> None:
        self._ready = True
        self.error = None

    def mark_failed(self, exc) -> None:
        self._ready = False
        self.error = f"{type(exc).__name__}: {exc}"


def _safe_filename(raw: str) -> str:
    """Keep a basename only — an upload must never be able to choose a path."""
    return Path(unquote(raw or "")).name.strip()


_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9 ._()\[\]-]")


def content_disposition(name: str) -> str:
    """Build a Content-Disposition header value for a name that came from an upload.

    Two properties are load-bearing, and both are about untrusted input reaching a header:

    1. It must not be able to carry CR or LF. `send_header` performs no validation, so a job named
       "x\r\nSet-Cookie: ..." would inject real response headers (HTTP response splitting).
    2. It must be latin-1 encodable, because http.server encodes headers as latin-1 — and this
       vault's meeting names are usually Hebrew. An unencodable character would raise mid-response,
       turning a download into a dropped connection.

    RFC 6266 solves both: `filename=` carries an ASCII-folded fallback, `filename*=` carries the
    real name percent-encoded as UTF-8.
    """
    stem = (name or "").replace("\r", " ").replace("\n", " ").strip() or "transcript"
    ascii_stem = _UNSAFE_FILENAME.sub("_", stem).strip("._ ") or "transcript"
    return (f'attachment; filename="{ascii_stem}.txt"; '
            f"filename*=UTF-8''{quote(stem + '.txt', safe='')}")


def make_handler(store, engine_state, audio_dir, static_dir, max_upload_bytes,
                 sync_timeout=7200.0, sync_poll=1.0):
    audio_dir, static_dir = Path(audio_dir), Path(static_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = "remote-whisper"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[whisper] {self.address_string()} {fmt % args}\n")

        # --- plumbing ---------------------------------------------------

        def _send(self, status, body: bytes, content_type, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, status=200, extra=None):
            self._send(status, json.dumps(obj).encode("utf-8"),
                       "application/json; charset=utf-8", extra)

        def _fail(self, status, message, **extra_fields):
            """Refusing a request mid-upload leaves unread bytes on the socket, and we cannot know
            how many. Close the connection instead of trying to drain it — draining a body we only
            partly read would block for bytes the client already stopped sending."""
            self.close_connection = True
            self._json({"error": message, **extra_fields}, status, extra={"Connection": "close"})

        def _query(self):
            return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

        # --- routing ----------------------------------------------------

        def do_GET(self):  # noqa: N802
            self._guarded(self._route_get)

        def do_HEAD(self):  # noqa: N802
            self._guarded(self._route_get)

        def do_POST(self):  # noqa: N802
            self._guarded(self._route_post)

        def _guarded(self, route):
            """Every request must end in an HTTP response. Without this, an unexpected failure
            (a disk error, a database fault) escapes the handler and closes the socket with zero
            bytes written — the client sees a bare connection reset it cannot report, and the
            operator sees nothing at all."""
            try:
                route()
            except Exception as exc:  # noqa: BLE001 - answer, log, and keep serving
                sys.stderr.write(f"[whisper] unhandled error on {self.path}: "
                                 f"{traceback.format_exc()}\n")
                try:
                    self._fail(500, f"internal error: {type(exc).__name__}")
                except Exception:  # noqa: BLE001 - response already started; just drop it
                    self.close_connection = True

        def _route_get(self):
            path = urlparse(self.path).path
            if path == "/healthz":
                return self._json({"status": "ok", "ready": engine_state.ready})
            if path == "/readyz":
                if engine_state.ready:
                    return self._json({"ready": True})
                return self._json({"ready": False, "error": engine_state.error}, 503)
            if path == "/api/jobs":
                return self._list_jobs()
            if path.startswith("/api/jobs/"):
                rest = path[len("/api/jobs/"):]
                if rest.endswith("/transcript"):
                    return self._transcript(rest[: -len("/transcript")])
                return self._job_detail(rest)
            return self._static(path)

        def _route_post(self):
            path = urlparse(self.path).path
            if path == "/api/jobs":
                return self._create_job(sync=False)
            if path == "/v1/audio/transcriptions":
                return self._create_job(sync=True)
            self._fail(404, "not found")

        # --- handlers ---------------------------------------------------

        def _list_jobs(self):
            query = self._query()
            try:
                limit = max(1, min(int(query.get("limit", 200)), 1000))
            except ValueError:
                limit = 200
            status = query.get("status") or None
            self._json({"jobs": store.list_jobs(status=status, limit=limit),
                        "stats": store.stats(),
                        "model_ready": engine_state.ready})

        def _job_detail(self, job_id):
            job = store.get(job_id) if JOB_ID_RE.match(job_id or "") else None
            if job is None:
                return self._fail(404, "no such job")
            self._json(job)

        def _transcript(self, job_id):
            job = store.get(job_id) if JOB_ID_RE.match(job_id or "") else None
            if job is None:
                return self._fail(404, "no such job")
            if job["status"] != "done":
                return self._fail(409, f"job is {job['status']}, not done")
            self._send(200, (job["transcript"] or "").encode("utf-8"),
                       "text/plain; charset=utf-8",
                       {"Content-Disposition": content_disposition(job["name"])})

        def _receive_audio(self):
            """Returns (fields, filename, staged_path, size) or raises _Rejected."""
            declared = int(self.headers.get("Content-Length") or 0)
            if declared <= 0:
                raise _Rejected(400, "request body is empty")
            if declared > max_upload_bytes + (1 << 16):  # allow for multipart framing
                raise _Rejected(413, f"upload is too large (limit {max_upload_bytes} bytes)")

            audio_dir.mkdir(parents=True, exist_ok=True)
            content_type = self.headers.get("Content-Type", "")
            boundary = boundary_from_content_type(content_type)
            staged = audio_dir / f"{uuid.uuid4().hex}.upload"
            try:
                if boundary:
                    fields, info = parse_multipart(self.rfile, declared, boundary, staged,
                                                   max_upload_bytes)
                    if info is None:
                        raise _Rejected(400, "no file part in the multipart body")
                    filename, size = _safe_filename(info["filename"]), info["bytes"]
                else:
                    fields = self._query()
                    filename = _safe_filename(fields.get("filename", ""))
                    size = _stream_to_file(self.rfile, declared, staged, max_upload_bytes)
            except MultipartTooLarge:
                raise _Rejected(413, f"upload is too large (limit {max_upload_bytes} bytes)")
            except MalformedMultipart as exc:
                staged.unlink(missing_ok=True)
                raise _Rejected(400, f"malformed multipart body: {exc}")
            except _Rejected:
                staged.unlink(missing_ok=True)
                raise

            try:
                if not filename:
                    raise _Rejected(400, "a filename is required (?filename= or the file part)")
                suffix = Path(filename).suffix.lower()
                if suffix not in ALLOWED_AUDIO_EXTENSIONS:
                    raise _Rejected(415, f"unsupported audio type '{suffix or filename}'")
                if size <= 0:
                    raise _Rejected(400, "uploaded audio is empty")
            except _Rejected:
                staged.unlink(missing_ok=True)
                raise

            final = staged.with_suffix(suffix)
            staged.rename(final)
            return fields, filename, final, size

        def _create_job(self, sync):
            try:
                fields, filename, path, size = self._receive_audio()
            except _Rejected as rejected:
                return self._fail(rejected.status, rejected.message)

            name = (fields.get("name") or "").strip() or Path(filename).stem
            language = (fields.get("language") or "").strip() or None
            job = store.add(name, filename, str(path), size, language)
            if not sync:
                return self._json(job, 201)
            return self._wait_for(job)

        def _wait_for(self, job):
            """OpenAI-compatible shim: hold the connection until the worker is done."""
            deadline = time.monotonic() + sync_timeout
            while time.monotonic() < deadline:
                current = store.get(job["id"])
                if current is None:
                    return self._fail(500, "job disappeared")
                if current["status"] == "done":
                    return self._json({"text": current["transcript"] or "",
                                       "language": current["detected_language"],
                                       "duration": current["duration_seconds"]})
                if current["status"] == "failed":
                    return self._fail(500, current["error"] or "transcription failed")
                time.sleep(sync_poll)
            self._fail(504, "transcription is still running; poll /api/jobs/<id> instead",
                       job_id=job["id"])

        def _static(self, path):
            # is_relative_to, not a string prefix: "<static>-backup" starts with "<static>" as a
            # string but is a different directory. And decode %20 so an asset with a space in its
            # name is findable, the same way uploads decode their filename.
            name = "index.html" if path == "/" else unquote(path.lstrip("/"))
            static_root = static_dir.resolve()
            target = (static_root / name).resolve()
            if (not target.is_relative_to(static_root)
                    or not target.is_file()
                    or target.suffix not in STATIC_TYPES):
                return self._fail(404, "not found")
            self._send(200, target.read_bytes(), STATIC_TYPES[target.suffix])

    return Handler


class _Rejected(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _stream_to_file(rfile, length, dest, max_bytes, chunk_size=1 << 20):
    """Copy a raw octet-stream body to disk without buffering it in memory."""
    written, remaining = 0, int(length)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as handle:
            while remaining > 0:
                chunk = rfile.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                written += len(chunk)
                if written > max_bytes:
                    raise _Rejected(413, f"upload is too large (limit {max_bytes} bytes)")
                handle.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return written


def serve(handler_cls, host="0.0.0.0", port=8080) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    httpd.daemon_threads = True
    return httpd
