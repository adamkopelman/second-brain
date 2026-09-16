import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import FakeEngine  # noqa: E402
from app.jobstore import JobStore  # noqa: E402
from app.server import EngineState, make_handler, serve  # noqa: E402
from app.worker import Worker  # noqa: E402

BOUNDARY = "----planboundary"


def multipart_body(fields, filename, payload):
    parts = []
    for name, value in fields.items():
        parts += [f"--{BOUNDARY}\r\n".encode(),
                  f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                  f"{value}\r\n".encode()]
    parts += [f"--{BOUNDARY}\r\n".encode(),
              f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
              b"Content-Type: audio/wav\r\n\r\n", payload, b"\r\n",
              f"--{BOUNDARY}--\r\n".encode()]
    return b"".join(parts)


class ServerTestBase(unittest.TestCase):
    max_upload_bytes = 4096
    sync_timeout = 5.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.audio = root / "audio"
        self.audio.mkdir()
        self.static = root / "static"
        self.static.mkdir()
        (self.static / "index.html").write_text("<h1>queue</h1>", encoding="utf-8")
        (self.static / "app.js").write_text("// app", encoding="utf-8")
        self.store = JobStore(root / "whisper.db")
        self.state = EngineState()
        self.state.mark_ready()
        handler = make_handler(
            self.store, self.state, self.audio, self.static,
            max_upload_bytes=self.max_upload_bytes,
            sync_timeout=self.sync_timeout, sync_poll=0.01,
        )
        self.httpd = serve(handler, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.store.close()
        self.tmp.cleanup()

    def request(self, path, data=None, method=None, content_type=None):
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def json_request(self, path, data=None, method=None, content_type=None):
        status, body, headers = self.request(path, data, method, content_type)
        return status, json.loads(body or b"{}"), headers

    def upload_raw(self, payload=b"RIFFrandom", filename="rec.wav", name="Standup", language=None):
        # Percent-encode: a name like "Board meeting" would otherwise put a space in the request
        # line and the server would reject it before any handler ran.
        params = {"filename": filename, "name": name}
        if language:
            params["language"] = language
        return self.json_request("/api/jobs?" + urlencode(params), data=payload, method="POST",
                                 content_type="application/octet-stream")


class HealthTest(ServerTestBase):
    def test_healthz_is_ok_and_readyz_reflects_the_engine(self):
        status, body, _ = self.json_request("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(self.json_request("/readyz")[0], 200)

    def test_readyz_is_503_before_the_model_loads(self):
        self.state._ready = False
        status, body, _ = self.json_request("/readyz")
        self.assertEqual(status, 503)
        self.assertFalse(body["ready"])


class UploadTest(ServerTestBase):
    def test_raw_upload_creates_a_queued_job_and_stores_the_audio(self):
        status, job, _ = self.upload_raw(payload=b"RIFF1234", filename="a.wav", name="Weekly")
        self.assertEqual(status, 201)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["name"], "Weekly")
        self.assertEqual(job["filename"], "a.wav")
        self.assertEqual(job["bytes"], 8)
        self.assertEqual(job["queue_position"], 1)
        self.assertEqual(Path(job["audio_path"]).read_bytes(), b"RIFF1234")
        self.assertEqual(Path(job["audio_path"]).parent, self.audio)

    def test_multipart_upload_reads_name_and_language_fields(self):
        body = multipart_body({"name": "Sync", "language": "he"}, "m.wav", b"RIFFmulti")
        status, job, _ = self.json_request(
            "/api/jobs", data=body, method="POST",
            content_type=f"multipart/form-data; boundary={BOUNDARY}")
        self.assertEqual(status, 201)
        self.assertEqual((job["name"], job["language"]), ("Sync", "he"))
        self.assertEqual(job["filename"], "m.wav")

    def test_name_defaults_to_the_filename_stem(self):
        _, job, _ = self.upload_raw(filename="2026-09-15_10-00-00.wav", name="")
        self.assertEqual(job["name"], "2026-09-15_10-00-00")

    def test_unsupported_extension_is_rejected(self):
        status, body, _ = self.upload_raw(filename="notes.txt")
        self.assertEqual(status, 415)
        self.assertIn("unsupported", body["error"].lower())

    def test_missing_filename_is_rejected(self):
        status, body, _ = self.json_request("/api/jobs", data=b"RIFF", method="POST",
                                            content_type="application/octet-stream")
        self.assertEqual(status, 400)
        self.assertIn("filename", body["error"])

    def test_empty_upload_is_rejected(self):
        status, body, _ = self.upload_raw(payload=b"")
        self.assertEqual(status, 400)
        self.assertIn("empty", body["error"].lower())

    def test_oversize_upload_is_rejected_and_leaves_no_audio_behind(self):
        status, body, _ = self.upload_raw(payload=b"x" * (self.max_upload_bytes + 1))
        self.assertEqual(status, 413)
        self.assertIn("too large", body["error"].lower())
        self.assertEqual(list(self.audio.iterdir()), [])
        self.assertEqual(self.store.stats()["total"], 0)


class ReadTest(ServerTestBase):
    def test_list_returns_jobs_stats_and_model_readiness_without_transcripts(self):
        _, first, _ = self.upload_raw(name="one", filename="one.wav")
        self.upload_raw(name="two", filename="two.wav")
        self.store.claim_next()
        self.store.finish(first["id"], "the full transcript", "en", 3.0)
        status, body, _ = self.json_request("/api/jobs")
        self.assertEqual(status, 200)
        self.assertEqual([j["name"] for j in body["jobs"]], ["two", "one"])
        self.assertIsNone(body["jobs"][1]["transcript"])
        self.assertEqual(body["stats"], {"queued": 1, "running": 0, "done": 1, "failed": 0,
                                         "total": 2})
        self.assertTrue(body["model_ready"])

    def test_list_filters_by_status_and_respects_limit(self):
        self.upload_raw(name="a", filename="a.wav")
        self.upload_raw(name="b", filename="b.wav")
        self.assertEqual(len(self.json_request("/api/jobs?limit=1")[1]["jobs"]), 1)
        self.assertEqual(self.json_request("/api/jobs?status=done")[1]["jobs"], [])

    def test_detail_includes_the_transcript(self):
        _, job, _ = self.upload_raw()
        self.store.claim_next()
        self.store.finish(job["id"], "shalom olam", "he", 9.0)
        status, body, _ = self.json_request(f"/api/jobs/{job['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body["transcript"], "shalom olam")
        self.assertEqual(body["detected_language"], "he")

    def test_detail_404s_for_unknown_and_malformed_ids(self):
        self.assertEqual(self.json_request("/api/jobs/" + "0" * 32)[0], 404)
        self.assertEqual(self.json_request("/api/jobs/not-an-id")[0], 404)

    def test_transcript_download_is_plain_text_with_a_filename(self):
        _, job, _ = self.upload_raw(name="Board meeting")
        self.store.claim_next()
        self.store.finish(job["id"], "line one", "en", 1.0)
        status, body, headers = self.request(f"/api/jobs/{job['id']}/transcript")
        self.assertEqual(status, 200)
        self.assertEqual(body.decode("utf-8"), "line one")
        self.assertTrue(headers["Content-Type"].startswith("text/plain"))
        self.assertIn("Board meeting.txt", headers["Content-Disposition"])

    def test_transcript_409s_while_the_job_is_unfinished(self):
        _, job, _ = self.upload_raw()
        status, body, _ = self.json_request(f"/api/jobs/{job['id']}/transcript")
        self.assertEqual(status, 409)
        self.assertIn("queued", body["error"])


class StaticTest(ServerTestBase):
    def test_root_serves_index_html(self):
        status, body, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"queue", body)
        self.assertTrue(headers["Content-Type"].startswith("text/html"))

    def test_known_asset_is_served_with_its_type(self):
        status, _, headers = self.request("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])

    def test_unknown_path_is_404_and_traversal_is_refused(self):
        self.assertEqual(self.request("/nope.js")[0], 404)
        self.assertEqual(self.request("/../whisper.db")[0], 404)


class HeaderSafetyTest(ServerTestBase):
    def finished_job(self, name, transcript="body", language="en"):
        _, job, _ = self.upload_raw(name=name)
        self.store.claim_next()
        self.store.finish(job["id"], transcript, language, 1.0)
        return job

    def test_a_crlf_in_the_job_name_cannot_inject_response_headers(self):
        job = self.finished_job("Evil\r\nX-Injected: pwned\r\nSet-Cookie: sess=hax")
        status, _, headers = self.request(f"/api/jobs/{job['id']}/transcript")
        self.assertEqual(status, 200)
        self.assertFalse([k for k in headers if k.lower() in ("x-injected", "set-cookie")])
        disposition = headers["Content-Disposition"]
        self.assertNotIn("\r", disposition)
        self.assertNotIn("\n", disposition)

    def test_a_hebrew_job_name_still_downloads(self):
        job = self.finished_job("ישיבת צוות", transcript="שלום עולם", language="he")
        status, body, headers = self.request(f"/api/jobs/{job['id']}/transcript")
        self.assertEqual(status, 200)
        self.assertEqual(body.decode("utf-8"), "שלום עולם")
        # http.server encodes headers as latin-1, so the real name can only ride in filename*.
        self.assertIn("filename*=UTF-8''", headers["Content-Disposition"])
        self.assertIn('filename="', headers["Content-Disposition"])


class ErrorHandlingTest(ServerTestBase):
    def test_an_unexpected_error_still_produces_a_500(self):
        def boom(*args, **kwargs):
            raise RuntimeError("database is gone")

        self.store.list_jobs = boom
        status, body, _ = self.json_request("/api/jobs")
        self.assertEqual(status, 500)
        self.assertIn("internal error", body["error"])


class StaticSafetyTest(ServerTestBase):
    def test_a_sibling_directory_sharing_the_static_prefix_is_refused(self):
        sibling = self.static.parent / f"{self.static.name}-backup"
        sibling.mkdir()
        (sibling / "secret.js").write_text("// secret", encoding="utf-8")
        self.assertEqual(self.request(f"/../{sibling.name}/secret.js")[0], 404)

    def test_percent_encoded_asset_names_are_served(self):
        (self.static / "my asset.js").write_text("// spaced", encoding="utf-8")
        status, body, _ = self.request("/my%20asset.js")
        self.assertEqual(status, 200)
        self.assertIn(b"spaced", body)


class OpenAIShimTest(ServerTestBase):
    def test_v1_transcriptions_blocks_until_the_worker_finishes(self):
        # FakeEngine mirrors the real engine and refuses to transcribe until load() has been
        # called; production calls it once in __main__ before the worker thread starts.
        engine = FakeEngine(text="synchronous text", language="en")
        engine.load()
        worker = Worker(self.store, engine, poll_interval=0.01)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        try:
            body = multipart_body({"model": "whisper-1"}, "sync.wav", b"RIFFsync")
            status, payload, _ = self.json_request(
                "/v1/audio/transcriptions", data=body, method="POST",
                content_type=f"multipart/form-data; boundary={BOUNDARY}")
        finally:
            worker.stop()
            thread.join(timeout=5)
        self.assertEqual(status, 200)
        self.assertEqual(payload["text"], "synchronous text")

    def test_v1_transcriptions_reports_a_failed_job_as_an_error(self):
        engine = FakeEngine(fail_with="decode error")
        engine.load()
        worker = Worker(self.store, engine, poll_interval=0.01)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        try:
            body = multipart_body({}, "bad.wav", b"RIFFbad")
            status, payload, _ = self.json_request(
                "/v1/audio/transcriptions", data=body, method="POST",
                content_type=f"multipart/form-data; boundary={BOUNDARY}")
        finally:
            worker.stop()
            thread.join(timeout=5)
        self.assertEqual(status, 500)
        self.assertIn("decode error", payload["error"])


class ShimTimeoutTest(ServerTestBase):
    sync_timeout = 0.05

    def test_v1_transcriptions_times_out_with_504_and_keeps_the_job(self):
        body = multipart_body({}, "slow.wav", b"RIFFslow")
        status, payload, _ = self.json_request(
            "/v1/audio/transcriptions", data=body, method="POST",
            content_type=f"multipart/form-data; boundary={BOUNDARY}")
        self.assertEqual(status, 504)
        self.assertIn("job_id", payload)
        self.assertEqual(self.store.stats()["queued"], 1)


if __name__ == "__main__":
    unittest.main()
