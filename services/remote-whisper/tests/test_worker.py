import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import FakeEngine  # noqa: E402
from app.jobstore import JobStore  # noqa: E402
from app.worker import Worker, unlink_audio  # noqa: E402
from tests.test_jobstore import Clock  # noqa: E402


def loaded_engine(**kwargs):
    """A FakeEngine that has been load()ed — mirrors production, where __main__ loads the model
    before the worker thread starts. FakeEngine refuses to transcribe otherwise, just as the real
    engine does."""
    engine = FakeEngine(**kwargs)
    engine.load()
    return engine


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.store = JobStore(self.root / "whisper.db", now=self.clock)
        self.audio = self.root / "audio"
        self.audio.mkdir()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def enqueue(self, name="a", language=None):
        path = self.audio / f"{name}.wav"
        path.write_bytes(b"RIFF")
        return self.store.add(name, f"{name}.wav", str(path), 4, language)

    def test_run_once_transcribes_and_records_progress(self):
        job = self.enqueue("standup")
        engine = loaded_engine(text="hello there", language="en", duration=12.0, steps=2)
        worker = Worker(self.store, engine)
        self.assertEqual(worker.run_once(), job["id"])
        done = self.store.get(job["id"])
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["transcript"], "hello there")
        self.assertEqual(done["detected_language"], "en")
        self.assertEqual(done["duration_seconds"], 12.0)
        self.assertEqual(done["progress"], 1.0)

    def test_requested_language_is_passed_through(self):
        self.enqueue("heb", language="he")
        engine = loaded_engine()
        Worker(self.store, engine).run_once()
        self.assertEqual(engine.calls[0][1], "he")

    def test_engine_failure_marks_the_job_failed_with_the_message(self):
        job = self.enqueue("bad")
        worker = Worker(self.store, loaded_engine(fail_with="ct2 blew up"))
        self.assertEqual(worker.run_once(), job["id"])
        failed = self.store.get(job["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertIn("ct2 blew up", failed["error"])

    def test_missing_audio_file_fails_the_job_without_calling_the_engine(self):
        job = self.enqueue("gone")
        Path(self.store.get(job["id"])["audio_path"]).unlink()
        engine = loaded_engine()
        Worker(self.store, engine).run_once()
        self.assertEqual(self.store.get(job["id"])["status"], "failed")
        self.assertIn("audio file is missing", self.store.get(job["id"])["error"])
        self.assertEqual(engine.calls, [])

    def test_run_once_on_an_empty_queue_returns_none(self):
        self.assertIsNone(Worker(self.store, loaded_engine()).run_once())

    def test_run_loop_drains_the_queue_then_stops(self):
        for name in ("a", "b", "c"):
            self.enqueue(name)
        stop = threading.Event()
        worker = Worker(self.store, loaded_engine(), poll_interval=0.01, stop_event=stop)
        thread = threading.Thread(target=worker.run)
        thread.start()
        try:
            for _ in range(500):
                if self.store.stats()["done"] == 3:
                    break
                threading.Event().wait(0.01)
        finally:
            worker.stop()
            thread.join(timeout=5)
        self.assertEqual(self.store.stats()["done"], 3)
        self.assertFalse(thread.is_alive())

    def test_sweep_retention_deletes_old_rows_and_their_audio(self):
        job = self.enqueue("old")
        audio_path = Path(self.store.get(job["id"])["audio_path"])
        Worker(self.store, loaded_engine()).run_once()
        self.clock.advance(20 * 86400)
        worker = Worker(self.store, loaded_engine(), retention_days=14)
        self.assertEqual(worker.sweep_retention(force=True), 1)
        self.assertIsNone(self.store.get(job["id"]))
        self.assertFalse(audio_path.exists())

    def test_sweep_retention_is_rate_limited(self):
        first = self.enqueue("first")
        Worker(self.store, loaded_engine()).run_once()
        self.clock.advance(20 * 86400)
        worker = Worker(self.store, loaded_engine(), retention_days=14, retention_interval=3600.0,
                        clock=lambda: 0.0)  # a frozen clock never clears the interval
        self.assertEqual(worker.sweep_retention(), 1)
        self.assertIsNone(self.store.get(first["id"]))

        second = self.enqueue("second")
        Worker(self.store, loaded_engine()).run_once()
        self.clock.advance(20 * 86400)
        self.assertEqual(worker.sweep_retention(), 0)  # rate-limited: skipped, not swept
        self.assertIsNotNone(self.store.get(second["id"]))

    def test_unlink_audio_reports_only_real_failures(self):
        present = self.audio / "present.wav"
        present.write_bytes(b"x")
        # A directory cannot be unlinked, so it stands in for a read-only volume or a permission
        # error; an absent file is not a failure because nothing is left behind.
        undeletable = self.audio / "a-directory.wav"
        undeletable.mkdir()
        failures = unlink_audio([str(present), str(self.audio / "absent.wav"), str(undeletable)])
        self.assertEqual(failures, [str(undeletable)])
        self.assertFalse(present.exists())

    def test_a_raising_store_does_not_kill_the_run_loop(self):
        """The single worker thread must outlive a database or volume error, or the service answers
        /healthz forever while transcribing nothing."""
        job = self.enqueue("survivor")
        real_claim = self.store.claim_next
        calls = {"n": 0}

        def flaky_claim():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database is locked")
            return real_claim()

        self.store.claim_next = flaky_claim
        logs = []
        stop = threading.Event()
        worker = Worker(self.store, loaded_engine(), poll_interval=0.01, stop_event=stop,
                        log=logs.append)
        thread = threading.Thread(target=worker.run)
        thread.start()
        try:
            for _ in range(500):
                if self.store.get(job["id"])["status"] == "done":
                    break
                threading.Event().wait(0.01)
        finally:
            worker.stop()
            thread.join(timeout=5)
        self.assertEqual(self.store.get(job["id"])["status"], "done")
        self.assertTrue(any("worker loop error" in line for line in logs))
        self.assertFalse(thread.is_alive())

    def test_a_failure_that_cannot_be_recorded_is_logged_not_raised(self):
        job = self.enqueue("unrecordable")

        def exploding_fail(job_id, error):
            raise RuntimeError("disk is full")

        self.store.fail = exploding_fail
        logs = []
        worker = Worker(self.store, loaded_engine(fail_with="ct2 blew up"), log=logs.append)
        self.assertEqual(worker.run_once(), job["id"])  # must not raise
        self.assertTrue(any("could not record failure" in line for line in logs))

    def test_sweep_retention_reports_audio_it_could_not_delete(self):
        job = self.enqueue("orphan")
        Worker(self.store, loaded_engine()).run_once()
        audio_path = Path(self.store.get(job["id"])["audio_path"])
        audio_path.unlink()
        audio_path.mkdir()  # undeletable stand-in for a read-only volume
        self.clock.advance(20 * 86400)
        logs = []
        worker = Worker(self.store, loaded_engine(), retention_days=14, log=logs.append)
        self.assertEqual(worker.sweep_retention(force=True), 1)
        self.assertTrue(any("could NOT be deleted" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
