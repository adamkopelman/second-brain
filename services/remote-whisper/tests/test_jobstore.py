import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.jobstore import JobStore  # noqa: E402


class Clock:
    """Deterministic, advanceable UTC clock."""

    def __init__(self, start="2026-09-15T09:00:00+00:00"):
        self.now = datetime.fromisoformat(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class JobStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.store = JobStore(Path(self.tmp.name) / "whisper.db", now=self.clock)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def add(self, name="a", language=None):
        return self.store.add(name, f"{name}.wav", f"/data/audio/{name}.wav", 1024, language)

    def test_add_returns_queued_job_with_generated_id(self):
        job = self.add("meeting")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["name"], "meeting")
        self.assertEqual(job["progress"], 0.0)
        self.assertEqual(job["created_at"], "2026-09-15T09:00:00+00:00")
        self.assertTrue(job["id"])
        self.assertIsNone(job["started_at"])
        self.assertEqual(job["queue_position"], 1)

    def test_claim_next_is_fifo_and_only_claims_queued(self):
        first = self.add("first")
        self.clock.advance(5)
        self.add("second")
        claimed = self.store.claim_next()
        self.assertEqual(claimed["id"], first["id"])
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["started_at"], "2026-09-15T09:00:05+00:00")
        second = self.store.claim_next()
        self.assertEqual(second["name"], "second")
        self.assertIsNone(self.store.claim_next())

    def test_queue_position_counts_only_queued_jobs(self):
        self.add("a")
        b = self.add("b")
        self.store.claim_next()  # a is now running
        self.assertEqual(self.store.get(b["id"])["queue_position"], 1)

    def test_set_progress_throttles_to_one_write_per_second(self):
        job = self.add()
        self.store.claim_next()
        self.assertTrue(self.store.set_progress(job["id"], 0.1))
        self.assertFalse(self.store.set_progress(job["id"], 0.2))
        self.assertEqual(self.store.get(job["id"])["progress"], 0.1)
        self.clock.advance(1)
        self.assertTrue(self.store.set_progress(job["id"], 0.3))
        self.assertEqual(self.store.get(job["id"])["progress"], 0.3)

    def test_set_progress_force_bypasses_throttle_and_clamps(self):
        job = self.add()
        self.store.claim_next()
        self.store.set_progress(job["id"], 0.1)
        self.assertTrue(self.store.set_progress(job["id"], 2.0, force=True))
        self.assertEqual(self.store.get(job["id"])["progress"], 1.0)

    def test_eta_and_elapsed_derived_for_running_job(self):
        job = self.add()
        self.store.claim_next()
        self.clock.advance(30)
        self.store.set_progress(job["id"], 0.25, force=True)
        running = self.store.get(job["id"])
        self.assertEqual(running["elapsed_seconds"], 30)
        self.assertEqual(running["eta_seconds"], 90)  # 30s did 25% -> 90s left

    def test_eta_is_none_without_progress(self):
        job = self.add()
        self.store.claim_next()
        self.clock.advance(10)
        self.assertIsNone(self.store.get(job["id"])["eta_seconds"])

    def test_finish_records_transcript_language_and_duration(self):
        job = self.add()
        self.store.claim_next()
        self.clock.advance(60)
        self.store.finish(job["id"], "shalom", "he", 42.5)
        done = self.store.get(job["id"])
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["transcript"], "shalom")
        self.assertEqual(done["detected_language"], "he")
        self.assertEqual(done["duration_seconds"], 42.5)
        self.assertEqual(done["progress"], 1.0)
        self.assertEqual(done["finished_at"], "2026-09-15T09:01:00+00:00")
        self.assertEqual(done["elapsed_seconds"], 60)
        self.assertIsNone(done["eta_seconds"])

    def test_fail_records_error(self):
        job = self.add()
        self.store.claim_next()
        self.store.fail(job["id"], "model exploded")
        failed = self.store.get(job["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "model exploded")
        self.assertIsNotNone(failed["finished_at"])

    def test_list_jobs_is_newest_first_filterable_and_omits_transcripts(self):
        a = self.add("a")
        self.clock.advance(1)
        self.add("b")
        self.store.claim_next()
        self.store.finish(a["id"], "text body", "en", 1.0)
        names = [j["name"] for j in self.store.list_jobs()]
        self.assertEqual(names, ["b", "a"])
        self.assertIsNone(self.store.list_jobs()[1]["transcript"])
        self.assertEqual([j["name"] for j in self.store.list_jobs(status="done")], ["a"])
        self.assertEqual(len(self.store.list_jobs(limit=1)), 1)

    def test_requeue_running_recovers_from_a_crash(self):
        job = self.add()
        self.store.claim_next()
        self.store.set_progress(job["id"], 0.5, force=True)
        self.assertEqual(self.store.requeue_running(), 1)
        recovered = self.store.get(job["id"])
        self.assertEqual(recovered["status"], "queued")
        self.assertEqual(recovered["progress"], 0.0)
        self.assertIsNone(recovered["started_at"])
        self.assertEqual(self.store.requeue_running(), 0)

    def test_purge_finished_drops_old_jobs_and_returns_their_audio_paths(self):
        old = self.add("old")
        self.store.claim_next()
        self.store.finish(old["id"], "t", "en", 1.0)
        self.clock.advance(15 * 86400)
        fresh = self.add("fresh")
        self.store.claim_next()
        self.store.finish(fresh["id"], "t", "en", 1.0)
        removed = self.store.purge_finished(14)
        self.assertEqual(removed, ["/data/audio/old.wav"])
        self.assertIsNone(self.store.get(old["id"]))
        self.assertIsNotNone(self.store.get(fresh["id"]))

    def test_purge_finished_disabled_by_zero_and_spares_unfinished(self):
        job = self.add("queued-forever")
        self.clock.advance(365 * 86400)
        self.assertEqual(self.store.purge_finished(0), [])
        self.assertEqual(self.store.purge_finished(14), [])
        self.assertIsNotNone(self.store.get(job["id"]))

    def test_stats_counts_every_status(self):
        self.add("a")
        b = self.add("b")
        self.store.claim_next()
        self.store.claim_next()
        self.store.fail(b["id"], "boom")
        self.assertEqual(
            self.store.stats(), {"queued": 0, "running": 1, "done": 0, "failed": 1, "total": 2}
        )

    def test_get_unknown_job_is_none(self):
        self.assertIsNone(self.store.get("nope"))

    def test_reopening_the_database_keeps_jobs(self):
        job = self.add("persisted")
        path = Path(self.tmp.name) / "whisper.db"
        self.store.close()
        self.store = JobStore(path, now=self.clock)
        self.assertEqual(self.store.get(job["id"])["name"], "persisted")


if __name__ == "__main__":
    unittest.main()
