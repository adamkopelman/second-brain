# Remote Whisper Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a CPU-only whisper-large-v3 transcription service as a container image + Helm chart with a live queue/progress web UI, wire the Obsidian plugin and `transcribe_meetings.py` to it, and package everything as a zip that can be carried into an air-gapped Harbor/Kubernetes environment.

**Architecture:** One pod, one process: a stdlib `ThreadingHTTPServer` serving both the JSON API and a vanilla-JS UI, a SQLite job store on a PVC, and a single background worker thread holding a resident faster-whisper (CTranslate2) large-v3 model. faster-whisper is reached only through an injected `Engine` interface, so every test in this repo still runs with no `pip install`. Note-writing logic is *not* duplicated into the plugin — the plugin shells out to `scripts/transcribe_meetings.py`, which gains a `--service-url` mode.

**Tech Stack:** Python 3 stdlib (`http.server`, `sqlite3`, `wave`, `urllib`, `zipfile`, `unittest`), vanilla JS + `node --test`, faster-whisper 1.1.1 / CTranslate2 (image only), Docker multi-stage build, Helm 3, Harbor (OCI registry for both image and chart).

**Spec:** `docs/superpowers/specs/2026-09-15-remote-whisper-service-design.md`

## Global Constraints

- **The vault stays dependency-free.** No file under `scripts/`, `.obsidian/`, or `services/remote-whisper/app/` may import a third-party package at module import time. faster-whisper is imported **lazily, inside `FasterWhisperEngine.load()`**, never at module top level. `services/remote-whisper/requirements.txt` is for the image only and must never be installed into the vault.
- **Tests run with nothing installed.** New service tests use stdlib `unittest` (run: `cd services/remote-whisper && python3 -m unittest discover -s tests -t .`). Tests under `scripts/tests/` follow the existing pytest style (bare `assert`, `tmp_path` fixture). JS tests use `node --test`.
- **Baseline to preserve:** 92 passing Python tests (1 skipped) and 54 passing JS tests. No task may reduce these numbers.
- **No authentication anywhere.** Deliberate user decision. Say so in `values.yaml` comments and in `docs/gtd/remote-whisper.md`; never add a token check.
- **No GPU.** `device="cpu"` is hardcoded in the engine. No CUDA base image, no `nvidia.com/gpu` resources.
- **`replicas: 1`, `strategy: Recreate`.** Never templated as configurable — a second replica would fight over a `ReadWriteOnce` PVC and slow both jobs down.
- **Timestamps** are UTC ISO-8601 strings, seconds precision: `datetime.now(timezone.utc).replace(microsecond=0).isoformat()`.
- **Default model path in the image:** `/models/faster-whisper-large-v3`. **Default data dir:** `/data` (`/data/audio/`, `/data/whisper.db`). **Default port:** `8080`.
- **Env var names** (the chart sets these, `app/__main__.py` reads them): `WHISPER_MODEL_PATH`, `WHISPER_COMPUTE_TYPE`, `WHISPER_DATA_DIR`, `WHISPER_PORT`, `WHISPER_THREADS`, `WHISPER_BEAM_SIZE`, `WHISPER_VAD`, `WHISPER_LANGUAGE`, `WHISPER_RETENTION_DAYS`, `WHISPER_MAX_UPLOAD_BYTES`, `WHISPER_SYNC_TIMEOUT`.
- **Commit after every task** with a `type(scope): subject` message, matching this repo's history (`feat(whisper): ...`, `docs(whisper): ...`).
- **Never commit** the built image tar, the packaged `.tgz` chart, or a model file. Only the source bundle zip is committed.

## File Structure

**Created:**

| Path | Responsibility |
|---|---|
| `services/remote-whisper/app/jobstore.py` | SQLite job state machine: enqueue, FIFO claim, throttled progress, finish/fail, crash requeue, retention, derived fields |
| `services/remote-whisper/app/engine.py` | `TranscriptResult`, `FakeEngine` (tests + `--fake-engine`), `FasterWhisperEngine` (lazy import), `probe_wav_duration` |
| `services/remote-whisper/app/multipart.py` | Streaming `multipart/form-data` parser — writes the file part straight to disk, never buffers it |
| `services/remote-whisper/app/worker.py` | Worker thread: claim → transcribe → record; plus the retention sweep |
| `services/remote-whisper/app/server.py` | HTTP handler: `/api/*`, `/v1/audio/transcriptions`, health probes, static files |
| `services/remote-whisper/app/__main__.py` | CLI/env wiring, deferred model load, server + worker startup, `EngineState` |
| `services/remote-whisper/app/static/{index.html,logic.js,app.js,style.css}` | The queue/progress UI. `logic.js` is pure and unit-tested |
| `services/remote-whisper/tests/test_{jobstore,engine,multipart,worker,server}.py` | stdlib `unittest` coverage |
| `services/remote-whisper/tests/test_logic.js` | `node --test` coverage for `logic.js` |
| `services/remote-whisper/{Dockerfile,requirements.txt,.dockerignore}` | Image build |
| `deploy/helm/remote-whisper/**` | Chart: Deployment, Service, Ingress, PVC, ConfigMap, helpers, NOTES, test hook |
| `scripts/remote_whisper/{build-image.sh,push-to-harbor.sh,lint-chart.sh,INSTALL.md}` | Build outside, push to Harbor inside, chart checks, bundle install guide |
| `scripts/package_remote_whisper.py` | Deterministic air-gap zip builder |
| `scripts/tests/test_package_remote_whisper.py` | Bundle tests |
| `docs/gtd/remote-whisper.md` | Operator + user guide |

**Modified:** `scripts/transcribe_meetings.py` (+`--service-url`), `scripts/tests/test_transcribe_meetings.py`, `.obsidian/plugins/record-meeting/{main.js,lib.js,manifest.json}`, `.obsidian/plugins/record-meeting/test/lib.test.js`, `docs/gtd/meeting-recording.md`, `README.md`, `.gitignore`.

> **Refinement vs the spec:** the spec's layout did not name `app/multipart.py`. Streaming multipart parsing is ~90 lines of fiddly buffer work that deserves its own file and its own tests rather than living inside `server.py`; nothing else about the design changes.

---

### Task 1: Job store

**Files:**
- Create: `services/remote-whisper/app/__init__.py` (empty),
  `services/remote-whisper/tests/__init__.py` (empty), `services/remote-whisper/app/jobstore.py`
- Test: `services/remote-whisper/tests/test_jobstore.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `utcnow_dt() -> datetime`, `JobStore(db_path: Path, now=utcnow_dt)` with methods
  `add(name: str, filename: str, audio_path: str, size_bytes: int, language: str | None = None) -> dict`,
  `get(job_id: str) -> dict | None`, `list_jobs(status: str | None = None, limit: int = 100) -> list[dict]`,
  `claim_next() -> dict | None`, `set_progress(job_id: str, progress: float, force: bool = False) -> bool`,
  `finish(job_id: str, transcript: str, detected_language: str | None, duration_seconds: float | None) -> None`,
  `fail(job_id: str, error: str) -> None`, `requeue_running() -> int`,
  `purge_finished(older_than_days: int) -> list[str]`, `stats() -> dict[str, int]`, `close() -> None`.
  Job dicts always carry: `id, name, filename, audio_path, bytes, duration_seconds, language,
  detected_language, status, progress, transcript, error, created_at, started_at, finished_at,
  elapsed_seconds, eta_seconds, queue_position`. `list_jobs` returns `transcript: None` (bodies are
  fetched per-job).

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_jobstore.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/__init__.py` as an empty file, then `services/remote-whisper/app/jobstore.py`:

```python
"""SQLite-backed job store for the remote Whisper service. Stdlib only.

Every state transition goes through this module, so the queue survives a pod restart: the audio
lives on the PVC and the row records exactly how far the transcription got.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATUSES = ("queued", "running", "done", "failed")

_COLUMNS = (
    "id, name, filename, audio_path, bytes, duration_seconds, language, detected_language, "
    "status, progress, transcript, error, created_at, started_at, finished_at"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    bytes INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    language TEXT,
    detected_language TEXT,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0.0,
    transcript TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs (status, created_at, rowid);
"""


def utcnow_dt() -> datetime:
    """UTC now, seconds precision — every timestamp this service stores comes from here."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class JobStore:
    def __init__(self, db_path: Path, now=utcnow_dt):
        self._now = now
        self._lock = threading.Lock()
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._last_progress: dict[str, datetime] = {}

    # --- writes ---------------------------------------------------------

    def add(self, name, filename, audio_path, size_bytes, language=None) -> dict:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO jobs (id, name, filename, audio_path, bytes, language, status, "
                "progress, created_at) VALUES (?, ?, ?, ?, ?, ?, 'queued', 0.0, ?)",
                (job_id, name, filename, str(audio_path), int(size_bytes),
                 language or None, _iso(self._now())),
            )
            self._conn.commit()
        return self.get(job_id)

    def claim_next(self) -> dict | None:
        """Atomically move the oldest queued job to running. FIFO is the database's job, not ours.

        Ties on created_at (second precision, so two jobs submitted in the same second tie) break on
        rowid — insertion order — not on the random uuid id, which would make FIFO a coin flip.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            cur = self._conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ?, progress = 0.0, error = NULL "
                "WHERE id = ? AND status = 'queued'",
                (_iso(self._now()), row["id"]),
            )
            self._conn.commit()
            if cur.rowcount != 1:  # someone else won the race
                return None
            job_id = row["id"]
        self._last_progress.pop(job_id, None)
        return self.get(job_id)

    def set_progress(self, job_id, progress, force=False) -> bool:
        """Throttled to one write per second per job — a 40-minute run must not do 40k writes."""
        progress = max(0.0, min(float(progress), 1.0))
        now = self._now()
        last = self._last_progress.get(job_id)
        if not force and last is not None and (now - last) < timedelta(seconds=1):
            return False
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET progress = ? WHERE id = ? AND status = 'running'",
                (progress, job_id),
            )
            self._conn.commit()
        self._last_progress[job_id] = now
        return True

    def finish(self, job_id, transcript, detected_language, duration_seconds) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'done', progress = 1.0, transcript = ?, "
                "detected_language = ?, duration_seconds = ?, finished_at = ?, error = NULL "
                "WHERE id = ?",
                (transcript, detected_language, duration_seconds, _iso(self._now()), job_id),
            )
            self._conn.commit()
        self._last_progress.pop(job_id, None)

    def fail(self, job_id, error) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                (str(error)[:4000], _iso(self._now()), job_id),
            )
            self._conn.commit()
        self._last_progress.pop(job_id, None)

    def requeue_running(self) -> int:
        """Called at startup: a pod that died mid-job left a 'running' row with no worker."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE jobs SET status = 'queued', progress = 0.0, started_at = NULL "
                "WHERE status = 'running'"
            )
            self._conn.commit()
        self._last_progress.clear()
        return cur.rowcount

    def purge_finished(self, older_than_days) -> list[str]:
        """Delete finished jobs past retention; returns the audio paths the caller should unlink."""
        if not older_than_days or older_than_days <= 0:
            return []
        cutoff = _iso(self._now() - timedelta(days=older_than_days))
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, audio_path FROM jobs WHERE status IN ('done', 'failed') "
                "AND finished_at IS NOT NULL AND finished_at < ? ORDER BY finished_at",
                (cutoff,),
            ).fetchall()
            if rows:
                self._conn.executemany(
                    "DELETE FROM jobs WHERE id = ?", [(r["id"],) for r in rows]
                )
                self._conn.commit()
        return [r["audio_path"] for r in rows]

    # --- reads ----------------------------------------------------------

    def get(self, job_id) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            order = self._queued_order() if row else []
        return self._decorate(row, order) if row else None

    def list_jobs(self, status=None, limit=100) -> list[dict]:
        sql = f"SELECT {_COLUMNS} FROM jobs"
        params: list = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            order = self._queued_order()
        jobs = [self._decorate(r, order) for r in rows]
        for job in jobs:
            job["transcript"] = None
        return jobs

    def stats(self) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
            ).fetchall()
        out = {s: 0 for s in STATUSES}
        for row in rows:
            out[row["status"]] = row["n"]
        out["total"] = sum(out[s] for s in STATUSES)
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- derived fields -------------------------------------------------

    def _queued_order(self) -> list[str]:
        """Caller must already hold self._lock — this never takes it, so _decorate stays lock-free."""
        rows = self._conn.execute(
            "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, rowid"
        ).fetchall()
        return [r["id"] for r in rows]

    def _decorate(self, row, queued_order: list[str]) -> dict:
        job = dict(row)
        started, finished = _parse(job["started_at"]), _parse(job["finished_at"])
        end = finished or self._now()
        job["elapsed_seconds"] = int((end - started).total_seconds()) if started else None
        job["eta_seconds"] = None
        if job["status"] == "running" and job["progress"] > 0 and job["elapsed_seconds"]:
            job["eta_seconds"] = int(job["elapsed_seconds"] * (1 - job["progress"]) / job["progress"])
        job["queue_position"] = None
        if job["status"] == "queued" and job["id"] in queued_order:
            job["queue_position"] = queued_order.index(job["id"]) + 1
        return job
```

**Locking rule to hold to:** `_decorate` and `_queued_order` never acquire the lock; every public
reader (`get`, `list_jobs`) takes `self._lock` once, reads its rows *and* the queued order inside it,
then decorates outside. The writers (`add`, `claim_next`) return `self.get(job_id)` after releasing
the lock, so they never nest it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 16 tests

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/__init__.py services/remote-whisper/app/jobstore.py services/remote-whisper/tests/test_jobstore.py
git commit -m "feat(whisper): SQLite job store with FIFO claim, throttled progress and retention"
```

---

### Task 2: Engine adapter

**Files:**
- Create: `services/remote-whisper/app/engine.py`
- Test: `services/remote-whisper/tests/test_engine.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TranscriptResult(text: str, detected_language: str | None, duration_seconds: float | None)`;
  `probe_wav_duration(path) -> float | None`;
  `FakeEngine(text="hello world", language="en", duration=10.0, steps=4, fail_with=None)` with
  `.load()`, `.duration(path)`, `.transcribe(path, language=None, on_progress=None) -> TranscriptResult`
  (which raises `RuntimeError` if `load()` was never called, exactly as the real engine does),
  `.loaded` bool, `.calls` list of `(path, language)`;
  `FasterWhisperEngine(model_path, compute_type="int8", threads=0, beam_size=1, vad=True)` with the
  same three methods and a `MissingDependency` error for the absent-package case.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_engine.py`:

```python
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import engine as E  # noqa: E402


def write_wav(path: Path, seconds=1.0, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_probe_reads_wav_duration(self):
        path = Path(self.tmp.name) / "a.wav"
        write_wav(path, seconds=2.5)
        self.assertAlmostEqual(E.probe_wav_duration(path), 2.5, places=3)

    def test_probe_returns_none_for_non_wav(self):
        path = Path(self.tmp.name) / "a.mp3"
        path.write_bytes(b"not a wav")
        self.assertIsNone(E.probe_wav_duration(path))

    def test_probe_returns_none_for_missing_file(self):
        self.assertIsNone(E.probe_wav_duration(Path(self.tmp.name) / "nope.wav"))


class FakeEngineTest(unittest.TestCase):
    def test_reports_monotonic_progress_ending_at_one(self):
        eng = E.FakeEngine(text="shalom", language="he", duration=8.0, steps=4)
        eng.load()
        seen = []
        result = eng.transcribe(Path("/tmp/x.wav"), language=None, on_progress=seen.append)
        self.assertTrue(eng.loaded)
        self.assertEqual(seen, [0.25, 0.5, 0.75, 1.0])
        self.assertEqual(result.text, "shalom")
        self.assertEqual(result.detected_language, "he")
        self.assertEqual(result.duration_seconds, 8.0)

    def test_records_calls_and_honours_requested_language(self):
        eng = E.FakeEngine()
        eng.load()
        eng.transcribe(Path("/tmp/y.wav"), language="en", on_progress=None)
        self.assertEqual(eng.calls, [(Path("/tmp/y.wav"), "en")])

    def test_fail_with_raises(self):
        eng = E.FakeEngine(fail_with="no speech backend")
        eng.load()
        with self.assertRaises(RuntimeError) as ctx:
            eng.transcribe(Path("/tmp/z.wav"))
        self.assertIn("no speech backend", str(ctx.exception))

    def test_transcribing_before_load_raises_like_the_real_engine(self):
        eng = E.FakeEngine()
        with self.assertRaises(RuntimeError) as ctx:
            eng.transcribe(Path("/tmp/early.wav"))
        self.assertIn("load()", str(ctx.exception))
        self.assertEqual(eng.calls, [])


class FasterWhisperEngineTest(unittest.TestCase):
    def test_constructing_does_not_import_faster_whisper(self):
        eng = E.FasterWhisperEngine("/models/faster-whisper-large-v3", compute_type="int8")
        self.assertEqual(eng.compute_type, "int8")
        self.assertIsNone(sys.modules.get("faster_whisper"))

    def test_load_raises_a_clear_error_when_the_package_is_absent(self):
        eng = E.FasterWhisperEngine("/models/faster-whisper-large-v3")
        if "faster_whisper" in sys.modules:
            self.skipTest("faster-whisper is installed in this environment")
        with self.assertRaises(E.MissingDependency) as ctx:
            eng.load()
        self.assertIn("faster-whisper", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k Engine -v`
Expected: FAIL — `ImportError: cannot import name 'engine'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/engine.py`:

```python
"""Speech-to-text engines.

faster-whisper is imported lazily inside FasterWhisperEngine.load() and nowhere else, so this module
— and therefore the whole test suite — imports fine on a machine that has never seen a pip install.
"""
from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


class MissingDependency(RuntimeError):
    """Raised when the real engine is asked to load without faster-whisper installed."""


@dataclass
class TranscriptResult:
    text: str
    detected_language: str | None
    duration_seconds: float | None


def probe_wav_duration(path) -> float | None:
    """Duration of a PCM WAV, or None for anything else. Only used to show a duration in the UI
    before transcription starts; the real duration comes back from the engine."""
    try:
        with wave.open(str(path), "rb") as w:
            rate = w.getframerate()
            return w.getnframes() / float(rate) if rate else None
    except Exception:
        return None


class FakeEngine:
    """Scripted engine for tests and for `--fake-engine` when working on the UI."""

    def __init__(self, text="hello world", language="en", duration=10.0, steps=4, fail_with=None):
        self.text = text
        self.language = language
        self._duration = duration
        self.steps = max(1, steps)
        self.fail_with = fail_with
        self.loaded = False
        self.calls: list[tuple] = []

    def load(self) -> None:
        self.loaded = True

    def duration(self, path):
        return self._duration

    def transcribe(self, path, language=None, on_progress=None) -> TranscriptResult:
        # Same precondition as the real engine: a double that accepts calls the real thing would
        # reject lets a caller that forgets load() pass every test and fail in production.
        if not self.loaded:
            raise RuntimeError("engine.load() has not been called")
        self.calls.append((Path(path), language))
        if self.fail_with:
            raise RuntimeError(self.fail_with)
        for step in range(1, self.steps + 1):
            if on_progress:
                on_progress(step / self.steps)
        return TranscriptResult(self.text, language or self.language, self._duration)


class FasterWhisperEngine:
    """CTranslate2 Whisper on CPU. Progress comes from each segment's end timestamp."""

    def __init__(self, model_path, compute_type="int8", threads=0, beam_size=1, vad=True):
        self.model_path = str(model_path)
        self.compute_type = compute_type
        self.threads = int(threads or 0)
        self.beam_size = int(beam_size or 1)
        self.vad = bool(vad)
        self._model = None

    def load(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - exercised only outside the image
            raise MissingDependency(
                "faster-whisper is not installed; this engine only runs inside the "
                "remote-whisper image (see services/remote-whisper/requirements.txt). "
                "Use --fake-engine for local development."
            ) from exc
        self._model = WhisperModel(
            self.model_path,
            device="cpu",
            compute_type=self.compute_type,
            cpu_threads=self.threads,
            num_workers=1,
        )

    def duration(self, path):
        return probe_wav_duration(path)

    def transcribe(self, path, language=None, on_progress=None) -> TranscriptResult:
        if self._model is None:
            raise RuntimeError("engine.load() has not been called")
        segments, info = self._model.transcribe(
            str(path),
            language=language or None,
            beam_size=self.beam_size,
            vad_filter=self.vad,
            condition_on_previous_text=False,
        )
        total = float(getattr(info, "duration", 0.0) or 0.0)
        pieces = []
        for segment in segments:
            text = (segment.text or "").strip()
            if text:
                pieces.append(text)
            if on_progress and total > 0:
                on_progress(min(float(segment.end) / total, 1.0))
        if on_progress:
            on_progress(1.0)
        return TranscriptResult(" ".join(pieces).strip(), getattr(info, "language", None), total or None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — Task 1's 16 tests plus 8 engine tests (24 total)

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/engine.py services/remote-whisper/tests/test_engine.py
git commit -m "feat(whisper): engine adapter with lazy faster-whisper import and a fake for tests"
```

---

### Task 3: Streaming multipart parser

**Files:**
- Create: `services/remote-whisper/app/multipart.py`
- Test: `services/remote-whisper/tests/test_multipart.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `boundary_from_content_type(value: str) -> bytes | None`;
  `MultipartTooLarge(Exception)`; `MalformedMultipart(Exception)`;
  `parse_multipart(rfile, content_length: int, boundary: bytes, dest_path: Path, max_bytes: int,
  file_field: str = "file", chunk_size: int = 1 << 20) -> tuple[dict[str, str], dict | None]`
  where the second element is `{"filename": str, "bytes": int}` when a file part was written.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_multipart.py`:

```python
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import multipart as M  # noqa: E402

BOUNDARY = b"----testboundary"


def build_body(fields=(), file_part=None):
    """fields: iterable of (name, value). file_part: (field, filename, bytes)."""
    out = []
    for name, value in fields:
        out += [
            b"--" + BOUNDARY + b"\r\n",
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode() + b"\r\n",
        ]
    if file_part:
        field, filename, payload = file_part
        out += [
            b"--" + BOUNDARY + b"\r\n",
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: audio/wav\r\n\r\n",
            payload,
            b"\r\n",
        ]
    out.append(b"--" + BOUNDARY + b"--\r\n")
    return b"".join(out)


class BoundaryTest(unittest.TestCase):
    def test_extracts_quoted_and_bare_boundaries(self):
        self.assertEqual(
            M.boundary_from_content_type('multipart/form-data; boundary="abc"'), b"abc"
        )
        self.assertEqual(M.boundary_from_content_type("multipart/form-data; boundary=abc"), b"abc")

    def test_none_when_absent_or_wrong_type(self):
        self.assertIsNone(M.boundary_from_content_type("multipart/form-data"))
        self.assertIsNone(M.boundary_from_content_type("application/octet-stream"))


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "upload.bin"

    def tearDown(self):
        self.tmp.cleanup()

    def parse(self, body, max_bytes=1 << 20):
        return M.parse_multipart(
            io.BytesIO(body), len(body), BOUNDARY, self.dest, max_bytes, chunk_size=7
        )

    def test_reads_fields_and_writes_the_file(self):
        payload = b"RIFF" + bytes(range(256)) * 20
        fields, info = self.parse(
            build_body(fields=[("name", "Standup"), ("language", "he")],
                       file_part=("file", "rec.wav", payload))
        )
        self.assertEqual(fields, {"name": "Standup", "language": "he"})
        self.assertEqual(info, {"filename": "rec.wav", "bytes": len(payload)})
        self.assertEqual(self.dest.read_bytes(), payload)

    def test_payload_containing_the_boundary_prefix_survives_chunk_splits(self):
        payload = b"--" + BOUNDARY[:-1] + b"x" * 50 + b"\r\n--not-the-end\r\n"
        _, info = self.parse(build_body(file_part=("file", "a.wav", payload)))
        self.assertEqual(self.dest.read_bytes(), payload)
        self.assertEqual(info["bytes"], len(payload))

    def test_delimiter_straddling_two_reads_is_still_found(self):
        """The parser must not depend on a delimiter arriving inside one read.

        A stream that hands back at most 3 bytes per read guarantees the delimiter is split across
        reads. Without this, `chunk_size=7` alone proves nothing: the reader is free to return more
        than asked, and a small body can arrive whole on the first read.
        """

        class DribblingStream(io.BytesIO):
            reads = 0

            def read(self, size=-1):
                DribblingStream.reads += 1
                return super().read(3)

        payload = b"--" + BOUNDARY[:-1] + b"y" * 40 + b"\r\n"
        body = build_body(fields=[("name", "Dribble")], file_part=("file", "d.wav", payload))
        fields, info = M.parse_multipart(
            DribblingStream(body), len(body), BOUNDARY, self.dest, 1 << 20, chunk_size=7
        )
        self.assertEqual(fields, {"name": "Dribble"})
        self.assertEqual(info, {"filename": "d.wav", "bytes": len(payload)})
        self.assertEqual(self.dest.read_bytes(), payload)
        self.assertGreater(DribblingStream.reads, len(body) // 4)  # proves it really dribbled

    def test_empty_file_part_is_allowed(self):
        _, info = self.parse(build_body(file_part=("file", "empty.wav", b"")))
        self.assertEqual(info, {"filename": "empty.wav", "bytes": 0})
        self.assertEqual(self.dest.read_bytes(), b"")

    def test_no_file_part_returns_none_and_leaves_no_file(self):
        fields, info = self.parse(build_body(fields=[("name", "x")]))
        self.assertEqual(fields, {"name": "x"})
        self.assertIsNone(info)
        self.assertFalse(self.dest.exists())

    def test_oversize_file_raises_and_removes_the_partial_file(self):
        with self.assertRaises(M.MultipartTooLarge):
            self.parse(build_body(file_part=("file", "big.wav", b"x" * 500)), max_bytes=100)
        self.assertFalse(self.dest.exists())

    def test_truncated_body_raises_malformed(self):
        body = build_body(file_part=("file", "a.wav", b"12345"))[:40]
        with self.assertRaises(M.MalformedMultipart):
            M.parse_multipart(io.BytesIO(body), len(body), BOUNDARY, self.dest, 1 << 20)
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k Multipart -v`
Expected: FAIL — `ImportError: cannot import name 'multipart'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/multipart.py`:

```python
"""A streaming multipart/form-data reader.

`cgi.FieldStorage` is gone in Python 3.13 and buffered everything anyway; a 350MB meeting WAV must
go straight to disk. This reads the request body in chunks, keeps only a boundary-sized tail in
memory, and writes the file part as it goes.
"""
from __future__ import annotations

import re
from pathlib import Path

_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
_DISPOSITION_NAME = re.compile(r'name="([^"]*)"', re.IGNORECASE)
_DISPOSITION_FILENAME = re.compile(r'filename="([^"]*)"', re.IGNORECASE)


class MultipartTooLarge(Exception):
    pass


class MalformedMultipart(Exception):
    pass


def boundary_from_content_type(value: str) -> bytes | None:
    if not value or not value.lower().startswith("multipart/form-data"):
        return None
    match = _BOUNDARY_RE.search(value)
    return match.group(1).encode() if match else None


class _Reader:
    """Chunked reader over a fixed-length request body with a pushback buffer."""

    def __init__(self, rfile, content_length, chunk_size):
        self._rfile = rfile
        self._remaining = max(0, int(content_length))
        # No floor: the tests pass a tiny chunk_size deliberately, to force a boundary to straddle
        # two reads. A 1024-byte floor would swallow every test body whole and the split path would
        # never run. Production callers pass 1 MiB.
        self._chunk_size = max(1, int(chunk_size))
        self.buf = b""

    def fill(self, at_least):
        while len(self.buf) < at_least and self._remaining > 0:
            data = self._rfile.read(min(self._chunk_size, self._remaining))
            if not data:
                self._remaining = 0
                break
            self._remaining -= len(data)
            self.buf += data
        return len(self.buf) >= at_least

    def fill_more(self):
        """Pull one more chunk in — used while scanning for a boundary."""
        return self.fill(len(self.buf) + self._chunk_size)

    @property
    def exhausted(self):
        return self._remaining <= 0

    def read_until(self, needle):
        """Consume up to and including `needle`; returns what came before it."""
        while True:
            index = self.buf.find(needle)
            if index >= 0:
                head, self.buf = self.buf[:index], self.buf[index + len(needle):]
                return head
            if self.exhausted and not self.fill(len(self.buf) + 1):
                raise MalformedMultipart(f"expected {needle!r} in body")
            self.fill_more()


def _part_headers(reader):
    raw = reader.read_until(b"\r\n\r\n").decode("utf-8", "replace")
    name = filename = None
    for line in raw.split("\r\n"):
        if line.lower().startswith("content-disposition"):
            name_match = _DISPOSITION_NAME.search(line)
            file_match = _DISPOSITION_FILENAME.search(line)
            name = name_match.group(1) if name_match else None
            filename = file_match.group(1) if file_match else None
    return name, filename


def parse_multipart(rfile, content_length, boundary, dest_path, max_bytes,
                    file_field="file", chunk_size=1 << 20):
    """Returns (fields, file_info | None). The file part is written to dest_path."""
    delimiter = b"\r\n--" + boundary
    reader = _Reader(rfile, content_length, chunk_size)
    reader.read_until(b"--" + boundary)  # preamble + first delimiter
    fields: dict[str, str] = {}
    file_info = None
    dest_path = Path(dest_path)

    while True:
        if not reader.fill(2):
            raise MalformedMultipart("truncated after a boundary")
        if reader.buf[:2] == b"--":
            break  # closing boundary
        if reader.buf[:2] != b"\r\n":
            raise MalformedMultipart("boundary not followed by CRLF")
        reader.buf = reader.buf[2:]

        name, filename = _part_headers(reader)
        if name == file_field and filename is not None:
            file_info = {"filename": filename,
                         "bytes": _stream_part(reader, delimiter, dest_path, max_bytes)}
        else:
            value = _read_part(reader, delimiter)
            if name:
                fields[name] = value.decode("utf-8", "replace")
    return fields, file_info


def _read_part(reader, delimiter):
    return reader.read_until(delimiter)


def _stream_part(reader, delimiter, dest_path, max_bytes):
    """Write a part's body to disk, holding back only len(delimiter) bytes of tail."""
    written = 0
    keep = len(delimiter)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    handle = dest_path.open("wb")
    try:
        while True:
            index = reader.buf.find(delimiter)
            if index >= 0:
                handle.write(reader.buf[:index])
                written += index
                reader.buf = reader.buf[index + len(delimiter):]
                if written > max_bytes:
                    raise MultipartTooLarge(f"file part exceeds {max_bytes} bytes")
                return written
            if len(reader.buf) > keep:
                flushable = reader.buf[:-keep]
                handle.write(flushable)
                written += len(flushable)
                reader.buf = reader.buf[-keep:]
                if written > max_bytes:
                    raise MultipartTooLarge(f"file part exceeds {max_bytes} bytes")
            if reader.exhausted and not reader.fill(len(reader.buf) + 1):
                raise MalformedMultipart("file part is not terminated by a boundary")
            reader.fill_more()
    except Exception:
        handle.close()
        dest_path.unlink(missing_ok=True)
        raise
    finally:
        if not handle.closed:
            handle.close()
```

Keep the exception path exactly as shown: a failed or oversize upload must never leave a partial
file behind, which is why `_stream_part` unlinks `dest_path` before re-raising.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 32 tests total

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/multipart.py services/remote-whisper/tests/test_multipart.py
git commit -m "feat(whisper): streaming multipart parser that writes uploads straight to disk"
```

---

### Task 4: Worker and retention sweep

**Files:**
- Create: `services/remote-whisper/app/worker.py`
- Test: `services/remote-whisper/tests/test_worker.py`

**Interfaces:**
- Consumes: `JobStore` (Task 1), `FakeEngine` / `TranscriptResult` (Task 2).
- Produces: `Worker(store, engine, poll_interval=1.0, stop_event=None, retention_days=14,
  retention_interval=3600.0, clock=time.monotonic)` with `.run_once() -> str | None`,
  `.run()` (loop, for `threading.Thread(target=...)`), `.stop()`, `.sweep_retention(force=False) -> int`;
  and `unlink_audio(paths) -> list[str]` (the paths it could NOT remove; files already gone are not
  failures).

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_worker.py`:

```python
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
```

Note: `from tests.test_jobstore import Clock` relies on `services/remote-whisper/tests/__init__.py`,
which Task 1 already created — do not create it again.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k Worker -v`
Expected: FAIL — `ImportError: cannot import name 'worker'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/worker.py`:

```python
"""The transcription worker: one thread, one job at a time, model resident between jobs."""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path


def unlink_audio(paths) -> list[str]:
    """Delete audio files, returning the ones that could NOT be removed.

    A file that is already gone is not a failure — nothing is left on disk. A real OSError
    (read-only remount, permissions, stale NFS handle) is, and it must be reported rather than
    swallowed: the row is gone, so nothing will ever try that file again, and a silently orphaned
    350MB recording per meeting fills the PVC with no operator-visible cause.
    """
    failures = []
    for path in paths:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            continue
        except OSError:
            failures.append(str(path))
    return failures


class Worker:
    def __init__(self, store, engine, poll_interval=1.0, stop_event=None, retention_days=14,
                 retention_interval=3600.0, clock=time.monotonic, log=print):
        self.store = store
        self.engine = engine
        self.poll_interval = poll_interval
        self.stop_event = stop_event or threading.Event()
        self.retention_days = int(retention_days or 0)
        self.retention_interval = float(retention_interval)
        self.clock = clock
        self.log = log
        self._last_sweep = None

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        while not self.stop_event.is_set():
            # The loop outlives everything except stop(). run_once() guards the transcription
            # itself, but claim_next(), the file check and the retention sweep all touch the PVC
            # and the database, and any of them can raise (disk full, read-only remount, a
            # corrupted db page). An unhandled raise here would kill the only worker thread while
            # /healthz kept answering 200 — the service would look alive and never transcribe again.
            try:
                self.sweep_retention()
                if self.run_once() is None:
                    self.stop_event.wait(self.poll_interval)
            except Exception as exc:  # noqa: BLE001 - deliberately broad; see above
                self.log(f"[whisper] worker loop error: {exc}\n{traceback.format_exc()}")
                self.stop_event.wait(self.poll_interval)

    def run_once(self) -> str | None:
        job = self.store.claim_next()
        if job is None:
            return None
        job_id = job["id"]
        audio = Path(job["audio_path"])
        if not audio.is_file():
            self.log(f"[whisper] failed {job_id}: audio file is missing: {audio}")
            self._record_failure(job_id, f"audio file is missing: {audio}")
            return job_id
        try:
            result = self.engine.transcribe(
                audio,
                language=job.get("language") or None,
                on_progress=lambda value: self.store.set_progress(job_id, value),
            )
            self.store.finish(job_id, result.text, result.detected_language, result.duration_seconds)
            self.log(f"[whisper] done {job_id} ({job['name']})")
        except Exception as exc:  # noqa: BLE001 - a bad file must not kill the worker
            self.log(f"[whisper] failed {job_id}: {exc}\n{traceback.format_exc()}")
            self._record_failure(job_id, f"{type(exc).__name__}: {exc}")
        return job_id

    def _record_failure(self, job_id, message) -> None:
        """Write a failure into the job row. Recording a failure must never raise: this runs on the
        error path, where the database or volume may be exactly what is broken."""
        try:
            self.store.fail(job_id, message)
        except Exception as exc:  # noqa: BLE001 - last line of defence for the worker thread
            self.log(f"[whisper] could not record failure for {job_id}: {exc}")

    def sweep_retention(self, force=False) -> int:
        if self.retention_days <= 0:
            return 0
        now = self.clock()
        if not force and self._last_sweep is not None and (now - self._last_sweep) < self.retention_interval:
            return 0
        self._last_sweep = now
        paths = self.store.purge_finished(self.retention_days)
        failures = unlink_audio(paths)
        if paths and not failures:
            self.log(f"[whisper] retention removed {len(paths)} job(s)")
        elif failures:
            self.log(f"[whisper] retention removed {len(paths)} job(s) but {len(failures)} audio "
                     f"file(s) could NOT be deleted and are now orphaned on disk: "
                     f"{', '.join(failures[:3])}")
        return len(paths)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 41 tests total

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/worker.py services/remote-whisper/tests/test_worker.py
git commit -m "feat(whisper): worker thread with per-job failure isolation and retention sweep"
```

---

### Task 5: HTTP API

**Files:**
- Create: `services/remote-whisper/app/server.py`
- Test: `services/remote-whisper/tests/test_server.py`

**Interfaces:**
- Consumes: `JobStore` (Task 1), `parse_multipart` / `boundary_from_content_type` /
  `MultipartTooLarge` / `MalformedMultipart` (Task 3), and — in the shim test only — `Worker`
  (Task 4) with `FakeEngine` (Task 2).
- Produces: `EngineState()` with `.ready` (bool property), `.error`, `.mark_ready()`,
  `.mark_failed(exc)`; `ALLOWED_AUDIO_EXTENSIONS: set[str]`;
  `make_handler(store, engine_state, audio_dir: Path, static_dir: Path, max_upload_bytes: int,
  sync_timeout: float = 7200.0, sync_poll: float = 1.0) -> type[BaseHTTPRequestHandler]`;
  `serve(handler_cls, host: str, port: int) -> ThreadingHTTPServer`.

> **Naming note (refines the spec's wording):** uploaded audio is stored at
> `<data-dir>/audio/<random-hex><ext>` rather than `<job-id><ext>` — the file has to exist before the
> row that would supply the job id. The row's `audio_path` is authoritative either way.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_server.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k Server -v`
Expected: FAIL — `ImportError: cannot import name 'server'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/server.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 62 tests total

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/server.py services/remote-whisper/tests/test_server.py
git commit -m "feat(whisper): job API, OpenAI-compatible sync shim, health probes and static serving"
```

---

### Task 6: Process entrypoint

**Files:**
- Create: `services/remote-whisper/app/__main__.py`
- Test: `services/remote-whisper/tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: `Config` dataclass with fields `host, port, data_dir, model_path, compute_type, threads,
  beam_size, vad, language, retention_days, max_upload_bytes, sync_timeout, fake_engine`;
  `build_config(argv: list[str] | None, environ: dict) -> Config`; `build_engine(config)`;
  `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_main.py`:

```python
import contextlib
import io
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.__main__ as M  # noqa: E402
from app.__main__ import build_config, build_engine  # noqa: E402
from app.engine import FakeEngine, FasterWhisperEngine  # noqa: E402


class ConfigTest(unittest.TestCase):
    def test_defaults_match_the_image_layout(self):
        config = build_config([], {})
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.data_dir, Path("/data"))
        self.assertEqual(config.model_path, Path("/models/faster-whisper-large-v3"))
        self.assertEqual(config.compute_type, "int8")
        self.assertEqual(config.threads, 0)
        self.assertEqual(config.beam_size, 1)
        self.assertTrue(config.vad)
        self.assertIsNone(config.language)
        self.assertEqual(config.retention_days, 14)
        self.assertEqual(config.max_upload_bytes, 1073741824)
        self.assertEqual(config.sync_timeout, 7200.0)
        self.assertFalse(config.fake_engine)

    def test_environment_overrides_defaults(self):
        config = build_config([], {
            "WHISPER_PORT": "9000",
            "WHISPER_DATA_DIR": "/var/whisper",
            "WHISPER_MODEL_PATH": "/models/medium",
            "WHISPER_COMPUTE_TYPE": "int8_float32",
            "WHISPER_THREADS": "6",
            "WHISPER_BEAM_SIZE": "5",
            "WHISPER_VAD": "false",
            "WHISPER_LANGUAGE": "he",
            "WHISPER_RETENTION_DAYS": "0",
            "WHISPER_MAX_UPLOAD_BYTES": "2048",
            "WHISPER_SYNC_TIMEOUT": "60",
        })
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.data_dir, Path("/var/whisper"))
        self.assertEqual(config.model_path, Path("/models/medium"))
        self.assertEqual(config.compute_type, "int8_float32")
        self.assertEqual(config.threads, 6)
        self.assertEqual(config.beam_size, 5)
        self.assertFalse(config.vad)
        self.assertEqual(config.language, "he")
        self.assertEqual(config.retention_days, 0)
        self.assertEqual(config.max_upload_bytes, 2048)
        self.assertEqual(config.sync_timeout, 60.0)

    def test_flags_beat_the_environment(self):
        config = build_config(["--port", "1234", "--language", "en", "--no-vad"],
                              {"WHISPER_PORT": "9000", "WHISPER_LANGUAGE": "he",
                               "WHISPER_VAD": "true"})
        self.assertEqual(config.port, 1234)
        self.assertEqual(config.language, "en")
        self.assertFalse(config.vad)

    def test_vad_accepts_the_usual_truthy_spellings(self):
        for raw, expected in [("1", True), ("true", True), ("TRUE", True), ("yes", True),
                              ("0", False), ("false", False), ("no", False), ("", True)]:
            self.assertIs(build_config([], {"WHISPER_VAD": raw}).vad, expected, raw)

    def test_a_malformed_numeric_environment_value_warns_and_falls_back(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            config = build_config([], {"WHISPER_PORT": "not-a-port"})
        self.assertEqual(config.port, 8080)
        self.assertIn("WHISPER_PORT", stderr.getvalue())

    def test_an_empty_environment_value_falls_back_silently(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            config = build_config([], {"WHISPER_THREADS": ""})
        self.assertEqual(config.threads, 0)
        self.assertEqual(stderr.getvalue(), "")


class EngineSelectionTest(unittest.TestCase):
    def test_fake_engine_flag_selects_the_fake(self):
        engine = build_engine(build_config(["--fake-engine"], {}))
        self.assertIsInstance(engine, FakeEngine)

    def test_default_selects_faster_whisper_with_the_configured_knobs(self):
        engine = build_engine(build_config(
            ["--model-path", "/models/x", "--compute-type", "int8", "--threads", "4",
             "--beam-size", "2", "--no-vad"], {}))
        self.assertIsInstance(engine, FasterWhisperEngine)
        self.assertEqual(engine.model_path, "/models/x")
        self.assertEqual(engine.threads, 4)
        self.assertEqual(engine.beam_size, 2)
        self.assertFalse(engine.vad)


class ShutdownTest(unittest.TestCase):
    """The signal window this covers is the one that matters: in production the model takes minutes
    to load, and a rollout can deliver SIGTERM in the middle of it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_build_engine = M.build_engine

    def tearDown(self):
        M.build_engine = self.original_build_engine
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.tmp.cleanup()

    def test_a_signal_during_the_model_load_still_shuts_down_cleanly(self):
        class SignallingEngine(FakeEngine):
            def load(inner_self):  # noqa: N805 - inner class, deliberate
                os.kill(os.getpid(), signal.SIGTERM)  # arrives mid-load
                super().load()

        M.build_engine = lambda config: SignallingEngine()
        exit_code = M.main(["--fake-engine", "--data-dir", self.tmp.name, "--port", "0"])
        self.assertEqual(exit_code, 0)

    def test_a_signal_before_the_load_skips_it_entirely(self):
        loads = []

        class RecordingEngine(FakeEngine):
            def load(inner_self):  # noqa: N805 - inner class, deliberate
                loads.append(True)
                super().load()

        M.build_engine = lambda config: RecordingEngine()
        original_serve = M.serve

        def serve_then_signal(handler_cls, host, port):
            httpd = original_serve(handler_cls, host, port)
            os.kill(os.getpid(), signal.SIGTERM)  # arrives before the load begins
            return httpd

        M.serve = serve_then_signal
        try:
            exit_code = M.main(["--fake-engine", "--data-dir", self.tmp.name, "--port", "0"])
        finally:
            M.serve = original_serve
        self.assertEqual(exit_code, 0)
        self.assertEqual(loads, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k Config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.__main__'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/__main__.py`:

```python
"""Entrypoint: `python -m app`. Serves immediately, loads the model in the background, then works.

Order matters. The HTTP server starts first so /healthz answers straight away and Kubernetes can
tell "still loading a 3GB model" (startup probe, /readyz 503) apart from "crashed".
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .engine import FakeEngine, FasterWhisperEngine
from .jobstore import JobStore
from .server import EngineState, make_handler, serve
from .worker import Worker

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8080,
    "data_dir": "/data",
    "model_path": "/models/faster-whisper-large-v3",
    "compute_type": "int8",
    "threads": 0,
    "beam_size": 1,
    "vad": True,
    "language": None,
    "retention_days": 14,
    "max_upload_bytes": 1073741824,
    "sync_timeout": 7200.0,
}
TRUTHY = {"1", "true", "yes", "on"}
FALSEY = {"0", "false", "no", "off"}

# How long to wait for the worker thread after asking it to stop. Long enough for an in-flight
# result to reach the database, short enough to stay well inside a pod's termination grace period.
# A worker mid-transcription will not make it — that job is requeued on the next start by design.
WORKER_JOIN_SECONDS = 10


@dataclass
class Config:
    host: str
    port: int
    data_dir: Path
    model_path: Path
    compute_type: str
    threads: int
    beam_size: int
    vad: bool
    language: str | None
    retention_days: int
    max_upload_bytes: int
    sync_timeout: float
    fake_engine: bool


def _env_number(environ, key, default, cast):
    raw = (environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        sys.stderr.write(f"[whisper] ignoring invalid {key}={raw!r}, using {default}\n")
        return default


def _env_bool(environ, key, default):
    raw = (environ.get(key) or "").strip().lower()
    if raw in TRUTHY:
        return True
    if raw in FALSEY:
        return False
    return default


def build_config(argv=None, environ=None) -> Config:
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(prog="python -m app", description=__doc__)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--beam-size", type=int, default=None)
    parser.add_argument("--vad", dest="vad", action="store_true", default=None)
    parser.add_argument("--no-vad", dest="vad", action="store_false", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--retention-days", type=int, default=None)
    parser.add_argument("--max-upload-bytes", type=int, default=None)
    parser.add_argument("--sync-timeout", type=float, default=None)
    parser.add_argument("--fake-engine", action="store_true",
                        help="scripted engine for UI work; never use in the image")
    args = parser.parse_args(argv)

    def pick(flag, env_key, default, cast=None):
        if flag is not None:
            return flag
        if cast is None:
            return (environ.get(env_key) or "").strip() or default
        return _env_number(environ, env_key, default, cast)

    language = args.language if args.language is not None else (
        (environ.get("WHISPER_LANGUAGE") or "").strip() or None)
    return Config(
        host=pick(args.host, "WHISPER_HOST", DEFAULTS["host"]),
        port=pick(args.port, "WHISPER_PORT", DEFAULTS["port"], int),
        data_dir=Path(pick(args.data_dir, "WHISPER_DATA_DIR", DEFAULTS["data_dir"])),
        model_path=Path(pick(args.model_path, "WHISPER_MODEL_PATH", DEFAULTS["model_path"])),
        compute_type=pick(args.compute_type, "WHISPER_COMPUTE_TYPE", DEFAULTS["compute_type"]),
        threads=pick(args.threads, "WHISPER_THREADS", DEFAULTS["threads"], int),
        beam_size=pick(args.beam_size, "WHISPER_BEAM_SIZE", DEFAULTS["beam_size"], int),
        vad=args.vad if args.vad is not None else _env_bool(environ, "WHISPER_VAD", DEFAULTS["vad"]),
        language=language,
        retention_days=pick(args.retention_days, "WHISPER_RETENTION_DAYS",
                            DEFAULTS["retention_days"], int),
        max_upload_bytes=pick(args.max_upload_bytes, "WHISPER_MAX_UPLOAD_BYTES",
                              DEFAULTS["max_upload_bytes"], int),
        sync_timeout=pick(args.sync_timeout, "WHISPER_SYNC_TIMEOUT", DEFAULTS["sync_timeout"], float),
        fake_engine=args.fake_engine,
    )


def build_engine(config: Config):
    if config.fake_engine:
        return FakeEngine(text="(fake engine) transcript", language=config.language or "en")
    return FasterWhisperEngine(config.model_path, compute_type=config.compute_type,
                               threads=config.threads, beam_size=config.beam_size, vad=config.vad)


def main(argv=None) -> int:
    config = build_config(argv)
    if config.threads:  # keep CTranslate2 inside the pod's CPU quota
        os.environ.setdefault("OMP_NUM_THREADS", str(config.threads))

    audio_dir = config.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(config.data_dir / "whisper.db")
    recovered = store.requeue_running()
    if recovered:
        print(f"[whisper] requeued {recovered} job(s) interrupted by a restart", flush=True)

    engine_state = EngineState()
    static_dir = Path(__file__).resolve().parent / "static"
    handler = make_handler(store, engine_state, audio_dir, static_dir,
                           max_upload_bytes=config.max_upload_bytes,
                           sync_timeout=config.sync_timeout)
    httpd = serve(handler, config.host, config.port)
    threading.Thread(target=httpd.serve_forever, name="http", daemon=True).start()
    print(f"[whisper] serving on http://{config.host}:{config.port}", flush=True)

    engine = build_engine(config)
    worker = Worker(store, engine, retention_days=config.retention_days)
    stopping = threading.Event()

    def shutdown(signum, _frame):
        print(f"[whisper] signal {signum}, shutting down", flush=True)
        worker.stop()
        stopping.set()

    # Installed BEFORE the model loads, not after. Loading a 3GB model takes minutes, and a
    # rollout can deliver SIGTERM in the middle of it. Handlers registered after the load would
    # leave that whole window on the OS default disposition: the process would die instantly,
    # the server would never shut down, and the database would never close.
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if stopping.is_set():
        print("[whisper] asked to stop before the model loaded; skipping the load", flush=True)
    else:
        print(f"[whisper] loading model from {config.model_path} "
              f"(compute_type={config.compute_type}, threads={config.threads or 'auto'})", flush=True)
        try:
            engine.load()
        except Exception as exc:  # noqa: BLE001 - stay up so /readyz can explain why
            engine_state.mark_failed(exc)
            print(f"[whisper] MODEL LOAD FAILED: {exc}", file=sys.stderr, flush=True)
        else:
            engine_state.mark_ready()
            print("[whisper] model ready", flush=True)

    worker_thread = None
    if engine_state.ready and not stopping.is_set():
        worker_thread = threading.Thread(target=worker.run, name="worker", daemon=True)
        worker_thread.start()

    stopping.wait()
    worker.stop()
    if worker_thread is not None:
        # Give an in-flight result time to reach the database before it closes. Without this,
        # finish()/fail() can hit a closed connection: the transcript is discarded, the log claims
        # a failure for a job that actually succeeded, and requeue_running() redoes the whole
        # transcription on the next boot.
        worker_thread.join(timeout=WORKER_JOIN_SECONDS)
        if worker_thread.is_alive():
            print(f"[whisper] worker still busy after {WORKER_JOIN_SECONDS}s; its job will be "
                  "requeued on the next start", flush=True)
    httpd.shutdown()
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 69 tests total

- [ ] **Step 5: Smoke-test the real process**

```bash
cd /home/user/second-brain/services/remote-whisper
rm -rf /tmp/whisper-smoke && mkdir -p /tmp/whisper-smoke
python3 -m app --fake-engine --data-dir /tmp/whisper-smoke --port 8899 --retention-days 0 &
sleep 2
python3 -c "
import urllib.request, json, time
print(urllib.request.urlopen('http://127.0.0.1:8899/readyz').read())
urllib.request.urlopen(urllib.request.Request(
    'http://127.0.0.1:8899/api/jobs?filename=smoke.wav&name=Smoke',
    data=b'RIFFsmoke', headers={'Content-Type': 'application/octet-stream'}, method='POST'))
time.sleep(2)
print(json.loads(urllib.request.urlopen('http://127.0.0.1:8899/api/jobs').read())['stats'])
"
kill %1
```

Expected: `{"ready": true}`, then stats showing `"done": 1`.

- [ ] **Step 6: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/__main__.py services/remote-whisper/tests/test_main.py
git commit -m "feat(whisper): process entrypoint with deferred model load and graceful shutdown"
```

---

### Task 7: Queue UI

**Files:**
- Create: `services/remote-whisper/app/static/logic.js`, `services/remote-whisper/app/static/index.html`,
  `services/remote-whisper/app/static/app.js`, `services/remote-whisper/app/static/style.css`
- Test: `services/remote-whisper/tests/test_logic.js`

**Interfaces:**
- Consumes: the API from Task 5 (`GET /api/jobs`, `GET /api/jobs/{id}`,
  `GET /api/jobs/{id}/transcript`, `POST /api/jobs?filename=&name=`).
- Produces: `window.WhisperLogic` / `module.exports` with `formatDuration(seconds)`,
  `formatBytes(n)`, `percentText(progress)`, `statusLabel(job)`, `metaText(job)`,
  `sortJobs(jobs)`, `summaryText(stats, modelReady)`, `isActive(job)`.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_logic.js`:

```js
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const L = require("../app/static/logic.js");

test("formatDuration renders human units and handles nulls", () => {
  assert.equal(L.formatDuration(0), "0s");
  assert.equal(L.formatDuration(45), "45s");
  assert.equal(L.formatDuration(95), "1m 35s");
  assert.equal(L.formatDuration(3725), "1h 2m");
  assert.equal(L.formatDuration(null), "—");
  assert.equal(L.formatDuration(undefined), "—");
});

test("formatBytes uses binary units", () => {
  assert.equal(L.formatBytes(0), "0 B");
  assert.equal(L.formatBytes(1023), "1023 B");
  assert.equal(L.formatBytes(1024), "1.0 KB");
  assert.equal(L.formatBytes(5 * 1024 * 1024), "5.0 MB");
  assert.equal(L.formatBytes(null), "—");
});

test("percentText rounds and clamps", () => {
  assert.equal(L.percentText(0), "0%");
  assert.equal(L.percentText(0.4213), "42%");
  assert.equal(L.percentText(1), "100%");
  assert.equal(L.percentText(1.5), "100%");
  assert.equal(L.percentText(null), "0%");
});

test("statusLabel is human and covers every status", () => {
  assert.equal(L.statusLabel({ status: "queued" }), "Queued");
  assert.equal(L.statusLabel({ status: "running" }), "Transcribing");
  assert.equal(L.statusLabel({ status: "done" }), "Done");
  assert.equal(L.statusLabel({ status: "failed" }), "Failed");
});

test("metaText explains what each status is waiting on", () => {
  assert.equal(
    L.metaText({ status: "queued", queue_position: 3, bytes: 2048 }),
    "3rd in queue · 2.0 KB"
  );
  assert.equal(L.metaText({ status: "queued", queue_position: 1, bytes: 1024 }), "Next up · 1.0 KB");
  assert.equal(
    L.metaText({ status: "running", progress: 0.5, elapsed_seconds: 60, eta_seconds: 60 }),
    "50% · 1m 0s elapsed · ~1m 0s left"
  );
  assert.equal(
    L.metaText({ status: "running", progress: 0, elapsed_seconds: 5, eta_seconds: null }),
    "0% · 5s elapsed · estimating…"
  );
  assert.equal(
    L.metaText({ status: "done", elapsed_seconds: 720, duration_seconds: 1800,
                 detected_language: "he" }),
    "Took 12m 0s for 30m 0s of audio · he"
  );
  assert.equal(L.metaText({ status: "failed", error: "boom" }), "boom");
  assert.equal(L.metaText({ status: "failed", error: null }), "Failed");
});

test("sortJobs puts running first, then the queue in order, then finished newest-first", () => {
  const jobs = [
    { id: "d", status: "done", created_at: "2026-09-15T09:00:00+00:00" },
    { id: "q2", status: "queued", queue_position: 2, created_at: "2026-09-15T09:05:00+00:00" },
    { id: "f", status: "failed", created_at: "2026-09-15T09:02:00+00:00" },
    { id: "r", status: "running", created_at: "2026-09-15T09:04:00+00:00" },
    { id: "q1", status: "queued", queue_position: 1, created_at: "2026-09-15T09:03:00+00:00" },
  ];
  assert.deepEqual(L.sortJobs(jobs).map((j) => j.id), ["r", "q1", "q2", "f", "d"]);
});

test("sortJobs does not mutate its input", () => {
  const jobs = [{ id: "a", status: "done", created_at: "x" }, { id: "b", status: "running" }];
  L.sortJobs(jobs);
  assert.deepEqual(jobs.map((j) => j.id), ["a", "b"]);
});

test("summaryText reports the queue and a loading model", () => {
  assert.equal(
    L.summaryText({ queued: 2, running: 1, done: 5, failed: 1 }, true),
    "1 transcribing · 2 queued · 5 done · 1 failed"
  );
  assert.equal(
    L.summaryText({ queued: 0, running: 0, done: 0, failed: 0 }, false),
    "Loading the model — jobs will start once it is ready"
  );
});

test("isActive marks jobs the page should keep polling for", () => {
  assert.equal(L.isActive({ status: "running" }), true);
  assert.equal(L.isActive({ status: "queued" }), true);
  assert.equal(L.isActive({ status: "done" }), false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain && node --test services/remote-whisper/tests/test_logic.js`
Expected: FAIL — `Cannot find module '../app/static/logic.js'`

- [ ] **Step 3: Write minimal implementation**

Create `services/remote-whisper/app/static/logic.js`:

```js
// Pure helpers for the queue page. No DOM, no fetch — so `node --test` can cover them.
"use strict";

const STATUS_LABELS = { queued: "Queued", running: "Transcribing", done: "Done", failed: "Failed" };
const STATUS_ORDER = { running: 0, queued: 1, failed: 2, done: 3 };

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "—";
  const total = Math.max(0, Math.round(Number(seconds)));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes}m ${total % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || Number.isNaN(Number(bytes))) return "—";
  const n = Number(bytes);
  if (n < 1024) return `${Math.round(n)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

function percentText(progress) {
  const value = Number(progress);
  if (!Number.isFinite(value) || value <= 0) return "0%";
  return `${Math.round(Math.min(value, 1) * 100)}%`;
}

function statusLabel(job) {
  return STATUS_LABELS[job && job.status] || "Unknown";
}

function ordinal(n) {
  const suffixes = { 1: "st", 2: "nd", 3: "rd" };
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${suffixes[n % 10] || "th"}`;
}

function metaText(job) {
  if (!job) return "";
  if (job.status === "queued") {
    const position = job.queue_position === 1 ? "Next up" : `${ordinal(job.queue_position)} in queue`;
    return `${position} · ${formatBytes(job.bytes)}`;
  }
  if (job.status === "running") {
    const eta = job.eta_seconds ? `~${formatDuration(job.eta_seconds)} left` : "estimating…";
    return `${percentText(job.progress)} · ${formatDuration(job.elapsed_seconds)} elapsed · ${eta}`;
  }
  if (job.status === "done") {
    const parts = [`Took ${formatDuration(job.elapsed_seconds)} for ${formatDuration(job.duration_seconds)} of audio`];
    if (job.detected_language) parts.push(job.detected_language);
    return parts.join(" · ");
  }
  return job.error || "Failed";
}

function sortJobs(jobs) {
  return (jobs || []).slice().sort((a, b) => {
    const rank = (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9);
    if (rank !== 0) return rank;
    if (a.status === "queued" && b.status === "queued") {
      return (a.queue_position || 0) - (b.queue_position || 0);
    }
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  });
}

function summaryText(stats, modelReady) {
  const s = stats || {};
  if (!modelReady) return "Loading the model — jobs will start once it is ready";
  return [
    `${s.running || 0} transcribing`,
    `${s.queued || 0} queued`,
    `${s.done || 0} done`,
    `${s.failed || 0} failed`,
  ].join(" · ");
}

function isActive(job) {
  return !!job && (job.status === "queued" || job.status === "running");
}

const API = {
  formatDuration, formatBytes, percentText, statusLabel, metaText, sortJobs, summaryText, isActive,
};

if (typeof module !== "undefined" && module.exports) module.exports = API;
if (typeof window !== "undefined") window.WhisperLogic = API;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain && node --test services/remote-whisper/tests/test_logic.js`
Expected: PASS — 9 tests

- [ ] **Step 5: Write the page shell**

Create `services/remote-whisper/app/static/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Whisper queue</title>
    <link rel="stylesheet" href="style.css" />
  </head>
  <body>
    <header>
      <h1>Whisper queue</h1>
      <p id="summary" class="summary">Loading…</p>
      <p id="banner" class="banner" hidden></p>
    </header>

    <section id="dropzone" class="dropzone" tabindex="0" aria-label="Upload audio to transcribe">
      <p><strong>Drop audio here</strong> or <button type="button" id="pick">choose a file</button></p>
      <p class="hint">wav, mp3, m4a, flac, ogg, webm — transcribed with whisper-large-v3 on CPU</p>
      <input type="file" id="file" accept="audio/*" hidden />
      <div id="uploads" class="uploads"></div>
    </section>

    <main>
      <ul id="jobs" class="jobs"></ul>
      <p id="empty" class="empty" hidden>Nothing in the queue yet.</p>
    </main>

    <script src="logic.js"></script>
    <script src="app.js"></script>
  </body>
</html>
```

- [ ] **Step 6: Write the page behaviour**

Create `services/remote-whisper/app/static/app.js`:

```js
// Queue page: polls the API, renders rows, uploads dropped files, expands finished transcripts.
"use strict";
(function () {
  const L = window.WhisperLogic;
  const POLL_VISIBLE_MS = 2000;
  const POLL_HIDDEN_MS = 5000;

  const els = {
    summary: document.getElementById("summary"),
    banner: document.getElementById("banner"),
    jobs: document.getElementById("jobs"),
    empty: document.getElementById("empty"),
    dropzone: document.getElementById("dropzone"),
    file: document.getElementById("file"),
    pick: document.getElementById("pick"),
    uploads: document.getElementById("uploads"),
  };

  const expanded = new Set();
  const transcripts = new Map();
  let timer = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function showBanner(message) {
    els.banner.textContent = message || "";
    els.banner.hidden = !message;
  }

  function renderTranscript(job) {
    const wrap = node("div", "transcript");
    const text = transcripts.has(job.id) ? transcripts.get(job.id) : "Loading transcript…";
    wrap.appendChild(node("pre", "transcript-body", text));
    const actions = node("div", "transcript-actions");
    const copy = node("button", "", "Copy");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(transcripts.get(job.id) || "");
        copy.textContent = "Copied";
        setTimeout(() => (copy.textContent = "Copy"), 1500);
      } catch (err) {
        showBanner(`Could not copy: ${err.message || err}`);
      }
    });
    const download = node("a", "button-link", "Download .txt");
    download.href = `api/jobs/${job.id}/transcript`;
    actions.appendChild(copy);
    actions.appendChild(download);
    wrap.appendChild(actions);
    return wrap;
  }

  function renderJob(job) {
    const item = node("li", `job job-${job.status}`);
    const head = node("div", "job-head");
    head.appendChild(node("span", "job-name", job.name || job.filename));
    head.appendChild(node("span", `pill pill-${job.status}`, L.statusLabel(job)));
    item.appendChild(head);

    const bar = node("div", "bar");
    const fill = node("div", "bar-fill");
    fill.style.width = job.status === "done" ? "100%" : L.percentText(job.progress);
    bar.appendChild(fill);
    item.appendChild(bar);
    item.appendChild(node("div", "job-meta", L.metaText(job)));

    if (job.status === "done" || job.status === "failed") {
      const toggle = node("button", "toggle", expanded.has(job.id) ? "Hide transcript" : "Show transcript");
      toggle.type = "button";
      if (job.status === "failed") toggle.textContent = expanded.has(job.id) ? "Hide error" : "Show error";
      toggle.addEventListener("click", () => {
        if (expanded.has(job.id)) expanded.delete(job.id);
        else {
          expanded.add(job.id);
          if (job.status === "done" && !transcripts.has(job.id)) loadTranscript(job.id);
        }
        tick();
      });
      item.appendChild(toggle);
      if (expanded.has(job.id)) {
        item.appendChild(job.status === "done" ? renderTranscript(job) : node("pre", "transcript-body", job.error || ""));
      }
    }
    return item;
  }

  async function loadTranscript(jobId) {
    try {
      const response = await fetch(`api/jobs/${jobId}`, { cache: "no-store" });
      const job = await response.json();
      transcripts.set(jobId, job.transcript || "(empty transcript)");
    } catch (err) {
      transcripts.set(jobId, `Could not load transcript: ${err.message || err}`);
    }
    tick();
  }

  function render(payload) {
    els.summary.textContent = L.summaryText(payload.stats, payload.model_ready);
    const jobs = L.sortJobs(payload.jobs);
    els.jobs.replaceChildren(...jobs.map(renderJob));
    els.empty.hidden = jobs.length > 0;
  }

  async function tick() {
    try {
      const response = await fetch("api/jobs", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
      showBanner("");
    } catch (err) {
      showBanner(`Cannot reach the service: ${err.message || err}`);
    }
  }

  function schedule() {
    if (timer) clearInterval(timer);
    timer = setInterval(tick, document.hidden ? POLL_HIDDEN_MS : POLL_VISIBLE_MS);
  }

  function upload(file) {
    const row = node("div", "upload", `Uploading ${file.name}… 0%`);
    els.uploads.appendChild(row);
    const query = `?filename=${encodeURIComponent(file.name)}&name=${encodeURIComponent(file.name.replace(/\.[^.]+$/, ""))}`;
    const request = new XMLHttpRequest();
    request.open("POST", `api/jobs${query}`);
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        row.textContent = `Uploading ${file.name}… ${Math.round((event.loaded / event.total) * 100)}%`;
      }
    });
    request.addEventListener("load", () => {
      if (request.status === 201) {
        row.remove();
        tick();
      } else {
        let message = `HTTP ${request.status}`;
        try {
          message = JSON.parse(request.responseText).error || message;
        } catch (err) {
          /* keep the status line */
        }
        row.className = "upload upload-failed";
        row.textContent = `${file.name}: ${message}`;
      }
    });
    request.addEventListener("error", () => {
      row.className = "upload upload-failed";
      row.textContent = `${file.name}: upload failed`;
    });
    request.send(file);
  }

  function wireUploads() {
    els.pick.addEventListener("click", () => els.file.click());
    els.file.addEventListener("change", () => {
      Array.from(els.file.files || []).forEach(upload);
      els.file.value = "";
    });
    ["dragenter", "dragover"].forEach((type) =>
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.add("dragging");
      })
    );
    ["dragleave", "drop"].forEach((type) =>
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.remove("dragging");
      })
    );
    els.dropzone.addEventListener("drop", (event) => {
      Array.from(event.dataTransfer.files || []).forEach(upload);
    });
  }

  document.addEventListener("visibilitychange", schedule);
  wireUploads();
  tick();
  schedule();
})();
```

- [ ] **Step 7: Write the stylesheet**

Create `services/remote-whisper/app/static/style.css` with, at minimum: a `:root` light palette and
a `@media (prefers-color-scheme: dark)` override; `body` capped at `min(900px, 100% - 2rem)` centred
with system-font stack; `.dropzone` as a dashed-border block with a `.dragging` accent state;
`.jobs` as an unstyled list of `.job` cards; `.bar` a 6px track with `.bar-fill` transitioning
`width 0.4s ease`; `.pill-queued/.pill-running/.pill-done/.pill-failed` in grey/blue/green/red;
`.transcript-body` with `white-space: pre-wrap`, a `max-height: 40vh` scroll and a monospace stack;
`.banner` red and `.upload-failed` red; everything legible at 360px wide with no horizontal scroll.

- [ ] **Step 8: Verify the UI against the real service**

```bash
cd /home/user/second-brain/services/remote-whisper
rm -rf /tmp/whisper-ui && mkdir -p /tmp/whisper-ui
python3 -m app --fake-engine --data-dir /tmp/whisper-ui --port 8899 &
sleep 2
python3 -c "
import urllib.request
for name in ('alpha', 'beta'):
    urllib.request.urlopen(urllib.request.Request(
        f'http://127.0.0.1:8899/api/jobs?filename={name}.wav&name={name}',
        data=b'RIFF' + b'0' * 1000, headers={'Content-Type': 'application/octet-stream'},
        method='POST'))
"
curl -s http://127.0.0.1:8899/ | head -5
curl -s http://127.0.0.1:8899/api/jobs | python3 -m json.tool | head -20
kill %1
```

Expected: the HTML shell comes back, and the JSON lists both jobs progressing to `done`.

- [ ] **Step 9: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/app/static services/remote-whisper/tests/test_logic.js
git commit -m "feat(whisper): queue page with live progress, drag-drop upload and transcript view"
```

---

### Task 8: Container image

**Files:**
- Create: `services/remote-whisper/Dockerfile`, `services/remote-whisper/requirements.txt`,
  `services/remote-whisper/.dockerignore`
- Test: `services/remote-whisper/tests/test_image_contract.py`

**Interfaces:**
- Consumes: `app/` (Tasks 1–7), `DEFAULTS` from `app/__main__.py`.
- Produces: an image whose entrypoint is `python -m app`, with `WHISPER_MODEL_PATH` and
  `WHISPER_DATA_DIR` defaulting to `/models/faster-whisper-large-v3` and `/data`; build args
  `PYTHON_VERSION`, `MODEL_REPO`, `MODEL_REVISION`, `MODEL_DIR`.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_image_contract.py`. This guards the thing that actually
breaks in practice: the Dockerfile and the app drifting apart on paths, ports and env names.

```python
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.__main__ import DEFAULTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "requirements.txt").read_text(encoding="utf-8")


class ImageContractTest(unittest.TestCase):
    def test_entrypoint_runs_the_app_module(self):
        self.assertIn('ENTRYPOINT ["python", "-m", "app"]', DOCKERFILE)

    def test_env_defaults_match_the_application_defaults(self):
        env = dict(re.findall(r"^ENV\s+(\w+)=(\S+)", DOCKERFILE, re.MULTILINE))
        self.assertEqual(env.get("WHISPER_MODEL_PATH"), str(DEFAULTS["model_path"]))
        self.assertEqual(env.get("WHISPER_DATA_DIR"), str(DEFAULTS["data_dir"]))
        self.assertEqual(env.get("WHISPER_PORT"), str(DEFAULTS["port"]))

    def test_exposes_the_default_port(self):
        self.assertIn(f"EXPOSE {DEFAULTS['port']}", DOCKERFILE)

    def test_runs_as_a_non_root_user(self):
        self.assertRegex(DOCKERFILE, r"^USER\s+10001", re.MULTILINE)

    def test_model_stage_is_separate_and_parameterised(self):
        self.assertIn("AS model", DOCKERFILE)
        self.assertIn("ARG MODEL_REPO=", DOCKERFILE)
        self.assertIn("ARG MODEL_REVISION=", DOCKERFILE)
        self.assertIn("COPY --from=model", DOCKERFILE)

    def test_requirements_pin_faster_whisper_exactly(self):
        self.assertRegex(REQUIREMENTS, r"^faster-whisper==\d+\.\d+\.\d+", re.MULTILINE)

    def test_no_cuda_or_gpu_base_image(self):
        self.assertNotIn("cuda", DOCKERFILE.lower())
        self.assertNotIn("nvidia", DOCKERFILE.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k ImageContract -v`
Expected: FAIL — `FileNotFoundError: .../Dockerfile`

- [ ] **Step 3: Write the requirements file**

Create `services/remote-whisper/requirements.txt`:

```
# Image-only dependencies. NEVER install these into the vault — the vault's own code and tests are
# stdlib-only so a fresh air-gapped clone works with no pip install (see the app/engine.py docstring).
faster-whisper==1.1.1
```

- [ ] **Step 4: Write the Dockerfile**

Create `services/remote-whisper/Dockerfile`:

```dockerfile
# CPU-only whisper-large-v3 transcription service.
#
# Stage 1 is the only part that needs the internet: it downloads the CTranslate2 weights. Build this
# on a connected machine (scripts/remote_whisper/build-image.sh), then `docker save` the result and
# push it into the air-gapped Harbor registry.
ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION} AS model
ARG MODEL_REPO=Systran/faster-whisper-large-v3
ARG MODEL_REVISION=main
ARG MODEL_DIR=/models/faster-whisper-large-v3
RUN pip install --no-cache-dir "huggingface_hub==0.26.2"
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('${MODEL_REPO}', revision='${MODEL_REVISION}', local_dir='${MODEL_DIR}', \
    allow_patterns=['*.bin', '*.json', '*.txt'])" \
    && du -sh ${MODEL_DIR}

FROM python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.title="remote-whisper" \
      org.opencontainers.image.description="CPU-only whisper-large-v3 transcription queue + UI" \
      org.opencontainers.image.source="https://github.com/adamkopelman/second-brain"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WHISPER_MODEL_PATH=/models/faster-whisper-large-v3 \
    WHISPER_DATA_DIR=/data \
    WHISPER_PORT=8080

WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt
COPY --from=model /models /models
COPY app /srv/app

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin whisper \
    && mkdir -p /data \
    && chown -R whisper:whisper /data /srv

USER 10001
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3).status==200 else 1)"]
ENTRYPOINT ["python", "-m", "app"]
```

Create `services/remote-whisper/.dockerignore`:

```
tests/
**/__pycache__/
**/*.pyc
.pytest_cache/
*.md
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v`
Expected: PASS — 76 tests total

- [ ] **Step 6: Verify the runtime stage builds (network permitting)**

The model stage needs Hugging Face access and ~4GB of disk, which this session may not have. Verify
what you can, and do not fake the rest:

```bash
cd /home/user/second-brain/services/remote-whisper
docker build --target runtime --build-arg PYTHON_VERSION=3.12-slim -t remote-whisper:contract-check . 2>&1 | tail -20
```

If it fails on `COPY --from=model` or on network access, that is expected here — record the exact
error in the commit message body and leave the build to `build-image.sh` on the user's connected
machine. Do **not** edit the Dockerfile to make a local build pass by dropping the model stage.

- [ ] **Step 7: Commit**

```bash
cd /home/user/second-brain
git add services/remote-whisper/Dockerfile services/remote-whisper/requirements.txt services/remote-whisper/.dockerignore services/remote-whisper/tests/test_image_contract.py
git commit -m "feat(whisper): multi-stage CPU image with the large-v3 weights baked in"
```

---

### Task 9: Helm chart

**Files:**
- Create: `deploy/helm/remote-whisper/Chart.yaml`, `values.yaml`, `.helmignore`,
  `templates/_helpers.tpl`, `templates/configmap.yaml`, `templates/pvc.yaml`,
  `templates/deployment.yaml`, `templates/service.yaml`, `templates/ingress.yaml`,
  `templates/NOTES.txt`, `templates/tests/test-connection.yaml`;
  `scripts/remote_whisper/lint-chart.sh`
- Test: `services/remote-whisper/tests/test_chart_contract.py`

**Interfaces:**
- Consumes: the image from Task 8 and the env var contract from `app/__main__.py`.
- Produces: a chart named `remote-whisper` whose `values.yaml` exposes `image.*`,
  `imagePullSecrets`, `persistence.*`, `model.source` (`image`|`pvc`), `model.pvc.*`, `whisper.*`,
  `resources.*`, `service.*`, `ingress.*`, `probes.startup.*`, and the standard scheduling keys;
  and the helper `remote-whisper.threads` that derives CTranslate2's thread count from
  `resources.limits.cpu`.

- [ ] **Step 1: Write the failing test**

Create `services/remote-whisper/tests/test_chart_contract.py` — a stdlib guard for chart/app drift
that runs even where `helm` is not installed:

```python
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.__main__ import DEFAULTS  # noqa: E402

CHART = Path(__file__).resolve().parents[3] / "deploy" / "helm" / "remote-whisper"
KNOWN_ENV = {
    "WHISPER_HOST", "WHISPER_PORT", "WHISPER_DATA_DIR", "WHISPER_MODEL_PATH",
    "WHISPER_COMPUTE_TYPE", "WHISPER_THREADS", "WHISPER_BEAM_SIZE", "WHISPER_VAD",
    "WHISPER_LANGUAGE", "WHISPER_RETENTION_DAYS", "WHISPER_MAX_UPLOAD_BYTES",
    "WHISPER_SYNC_TIMEOUT", "OMP_NUM_THREADS",
}


def read(*parts):
    return (CHART.joinpath(*parts)).read_text(encoding="utf-8")


class ChartContractTest(unittest.TestCase):
    def test_chart_metadata_is_present(self):
        chart = read("Chart.yaml")
        self.assertIn("name: remote-whisper", chart)
        self.assertRegex(chart, r"^version: \d+\.\d+\.\d+", re.MULTILINE)
        self.assertRegex(chart, r"^appVersion:", re.MULTILINE)

    def test_every_templated_env_var_is_one_the_app_reads(self):
        rendered = "".join(read("templates", name) for name in
                           ("configmap.yaml", "deployment.yaml"))
        for name in set(re.findall(r"\b(WHISPER_[A-Z_]+|OMP_NUM_THREADS)\b", rendered)):
            self.assertIn(name, KNOWN_ENV, f"{name} is templated but the app never reads it")

    def test_app_defaults_all_have_a_values_entry(self):
        values = read("values.yaml")
        for key in ("computeType", "threads", "beamSize", "vad", "language", "retentionDays",
                    "maxUploadBytes"):
            self.assertIn(f"{key}:", values, f"values.yaml is missing whisper.{key}")
        self.assertIn(str(DEFAULTS["max_upload_bytes"]), values)
        self.assertIn(str(DEFAULTS["retention_days"]), values)

    def test_single_replica_and_recreate_are_not_configurable(self):
        deployment = read("templates", "deployment.yaml")
        self.assertIn("replicas: 1", deployment)
        self.assertIn("type: Recreate", deployment)
        self.assertNotIn(".Values.replicaCount", deployment)

    def test_startup_probe_guards_the_slow_model_load(self):
        deployment = read("templates", "deployment.yaml")
        self.assertIn("startupProbe", deployment)
        self.assertIn("/readyz", deployment)
        self.assertIn("/healthz", deployment)

    def test_values_document_that_there_is_no_authentication(self):
        self.assertRegex(read("values.yaml"), r"(?i)no authentication")

    def test_no_gpu_resources_anywhere_in_the_chart(self):
        for path in CHART.rglob("*.yaml"):
            self.assertNotIn("nvidia.com/gpu", path.read_text(encoding="utf-8"), str(path))

    def test_model_source_supports_image_and_pvc(self):
        values = read("values.yaml")
        self.assertIn("source: image", values)
        deployment = read("templates", "deployment.yaml")
        self.assertIn('eq .Values.model.source "pvc"', deployment)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -k ChartContract -v`
Expected: FAIL — `FileNotFoundError: .../deploy/helm/remote-whisper/Chart.yaml`

- [ ] **Step 3: Write Chart.yaml, .helmignore and values.yaml**

`deploy/helm/remote-whisper/Chart.yaml`:

```yaml
apiVersion: v2
name: remote-whisper
description: CPU-only whisper-large-v3 transcription service with a queue/progress web UI
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords: [whisper, transcription, speech-to-text, cpu, air-gapped]
home: https://github.com/adamkopelman/second-brain
sources:
  - https://github.com/adamkopelman/second-brain/tree/master/services/remote-whisper
maintainers:
  - name: adamkopelman
```

`deploy/helm/remote-whisper/.helmignore`:

```
.DS_Store
.git/
*.tgz
```

`deploy/helm/remote-whisper/values.yaml`:

```yaml
# remote-whisper — CPU-only whisper-large-v3 with a queue/progress UI.
#
# SECURITY: this service has NO AUTHENTICATION, by design. Anyone who can reach its Service or
# Ingress can submit audio and read every transcript. Only expose it on a trusted network.

image:
  # Push the image built by scripts/remote_whisper/build-image.sh into your own registry and
  # point this at it, e.g. harbor.internal/second-brain/remote-whisper
  repository: harbor.example.local/second-brain/remote-whisper
  tag: ""            # defaults to .Chart.AppVersion
  pullPolicy: IfNotPresent

# Harbor robot-account secret, e.g. [{name: harbor-pull}]
imagePullSecrets: []

nameOverride: ""
fullnameOverride: ""

# Uploaded audio + the SQLite queue. Keep this enabled: without it, a restart loses the queue.
persistence:
  enabled: true
  size: 20Gi
  storageClass: ""
  accessMode: ReadWriteOnce
  existingClaim: ""

model:
  # image = use the ~3GB weights baked into the image (no volume needed)
  # pvc   = mount your own model directory instead, so you can swap large-v3 for
  #         distil-large-v3 or medium without rebuilding the image
  source: image
  path: /models/faster-whisper-large-v3
  pvc:
    claimName: ""
    subPath: ""

whisper:
  computeType: int8        # int8 (fastest on CPU) | int8_float32 | float32
  threads: ""              # "" = derive from resources.limits.cpu
  beamSize: 1              # 1 = greedy; higher is slower and rarely better on meeting audio
  vad: true                # voice-activity filter; also suppresses large-v3's silence hallucinations
  language: ""             # "" = detect per recording (keep empty for mixed Hebrew/English)
  retentionDays: 14        # delete finished jobs + their audio after N days; 0 = keep forever
  maxUploadBytes: 1073741824
  syncTimeout: 7200        # /v1/audio/transcriptions holds the connection this long

# One CPU transcription saturates every core it gets. Raising limits.cpu is the main throughput
# lever — the pod's thread count follows it automatically.
resources:
  requests:
    cpu: "2"
    memory: 3Gi
  limits:
    cpu: "4"
    memory: 6Gi

service:
  type: ClusterIP          # ClusterIP | NodePort | LoadBalancer
  port: 80
  nodePort: null           # only used when type is NodePort

ingress:
  enabled: false
  className: ""
  host: whisper.example.local
  path: /
  pathType: Prefix
  tls: []
  # Defaults sized for large audio uploads and the long synchronous shim. Drop or replace these
  # if your controller is not ingress-nginx.
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 1024m
    nginx.ingress.kubernetes.io/proxy-read-timeout: "7200"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "7200"

# Loading a 3GB model takes minutes on a slow node; the startup probe is what stops Kubernetes
# from killing the pod before it finishes. failureThreshold * periodSeconds = the budget.
probes:
  startup:
    failureThreshold: 60
    periodSeconds: 10
  readiness:
    periodSeconds: 10
    timeoutSeconds: 3
  liveness:
    periodSeconds: 30
    timeoutSeconds: 5

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop: ["ALL"]

extraEnv: []               # [{name: ..., value: ...}]
podAnnotations: {}
podLabels: {}
nodeSelector: {}
tolerations: []
affinity: {}
# stop() cannot interrupt a transcription mid-call, so a rollout or pod delete during a long job
# waits this long and then SIGKILLs it. Survivable by design: a killed job is left `running`, and
# the next startup requeues it (JobStore.requeue_running), so the work restarts rather than being
# lost. 300s lets a short job finish; an hour-long grace period would hang every rollout instead.
terminationGracePeriodSeconds: 300
```

- [ ] **Step 4: Write the templates**

`templates/_helpers.tpl`:

```yaml
{{- define "remote-whisper.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "remote-whisper.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "remote-whisper.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "remote-whisper.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "remote-whisper.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "remote-whisper.selectorLabels" -}}
app.kubernetes.io/name: {{ include "remote-whisper.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "remote-whisper.image" -}}
{{- printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) -}}
{{- end -}}

{{- define "remote-whisper.dataClaim" -}}
{{- if .Values.persistence.existingClaim -}}
{{- .Values.persistence.existingClaim -}}
{{- else -}}
{{- printf "%s-data" (include "remote-whisper.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
CTranslate2 spawns one thread per host core unless told otherwise, which thrashes against the
pod's CPU quota. Derive the count from resources.limits.cpu ("2", "1500m") unless set explicitly.
*/}}
{{- define "remote-whisper.threads" -}}
{{- if .Values.whisper.threads -}}
{{- .Values.whisper.threads | quote -}}
{{- else -}}
{{- $cpu := .Values.resources.limits.cpu | default "" | toString -}}
{{- if hasSuffix "m" $cpu -}}
{{- max 1 (div (int (trimSuffix "m" $cpu)) 1000) | quote -}}
{{- else if $cpu -}}
{{- max 1 (int (float64 $cpu)) | quote -}}
{{- else -}}
{{- "0" | quote -}}
{{- end -}}
{{- end -}}
{{- end -}}
```

`templates/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "remote-whisper.fullname" . }}
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
data:
  WHISPER_HOST: "0.0.0.0"
  WHISPER_PORT: "8080"
  WHISPER_DATA_DIR: "/data"
  WHISPER_MODEL_PATH: {{ .Values.model.path | quote }}
  WHISPER_COMPUTE_TYPE: {{ .Values.whisper.computeType | quote }}
  WHISPER_THREADS: {{ include "remote-whisper.threads" . }}
  OMP_NUM_THREADS: {{ include "remote-whisper.threads" . }}
  WHISPER_BEAM_SIZE: {{ .Values.whisper.beamSize | quote }}
  WHISPER_VAD: {{ .Values.whisper.vad | quote }}
  WHISPER_LANGUAGE: {{ .Values.whisper.language | quote }}
  WHISPER_RETENTION_DAYS: {{ .Values.whisper.retentionDays | quote }}
  WHISPER_MAX_UPLOAD_BYTES: {{ .Values.whisper.maxUploadBytes | quote }}
  WHISPER_SYNC_TIMEOUT: {{ .Values.whisper.syncTimeout | quote }}
```

`templates/pvc.yaml`:

```yaml
{{- if and .Values.persistence.enabled (not .Values.persistence.existingClaim) }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ printf "%s-data" (include "remote-whisper.fullname" .) }}
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
spec:
  accessModes: [{{ .Values.persistence.accessMode | quote }}]
  resources:
    requests:
      storage: {{ .Values.persistence.size | quote }}
  {{- with .Values.persistence.storageClass }}
  storageClassName: {{ . | quote }}
  {{- end }}
{{- end }}
```

`templates/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "remote-whisper.fullname" . }}
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
spec:
  # Pinned: one CPU transcription uses every core it is given, and the data PVC is ReadWriteOnce.
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels: {{- include "remote-whisper.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        {{- with .Values.podAnnotations }}{{- toYaml . | nindent 8 }}{{- end }}
      labels:
        {{- include "remote-whisper.selectorLabels" . | nindent 8 }}
        {{- with .Values.podLabels }}{{- toYaml . | nindent 8 }}{{- end }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets: {{- toYaml . | nindent 8 }}
      {{- end }}
      securityContext: {{- toYaml .Values.podSecurityContext | nindent 8 }}
      terminationGracePeriodSeconds: {{ .Values.terminationGracePeriodSeconds }}
      containers:
        - name: whisper
          image: {{ include "remote-whisper.image" . | quote }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          securityContext: {{- toYaml .Values.securityContext | nindent 12 }}
          ports:
            - name: http
              containerPort: 8080
          envFrom:
            - configMapRef:
                name: {{ include "remote-whisper.fullname" . }}
          {{- with .Values.extraEnv }}
          env: {{- toYaml . | nindent 12 }}
          {{- end }}
          # The model load takes minutes; the startup probe is the budget for it, and only after it
          # passes do readiness/liveness start.
          startupProbe:
            httpGet:
              path: /readyz
              port: http
            failureThreshold: {{ .Values.probes.startup.failureThreshold }}
            periodSeconds: {{ .Values.probes.startup.periodSeconds }}
          readinessProbe:
            httpGet:
              path: /readyz
              port: http
            periodSeconds: {{ .Values.probes.readiness.periodSeconds }}
            timeoutSeconds: {{ .Values.probes.readiness.timeoutSeconds }}
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: {{ .Values.probes.liveness.periodSeconds }}
            timeoutSeconds: {{ .Values.probes.liveness.timeoutSeconds }}
          resources: {{- toYaml .Values.resources | nindent 12 }}
          volumeMounts:
            - name: data
              mountPath: /data
            {{- if eq .Values.model.source "pvc" }}
            - name: model
              mountPath: {{ .Values.model.path }}
              {{- with .Values.model.pvc.subPath }}
              subPath: {{ . | quote }}
              {{- end }}
              readOnly: true
            {{- end }}
      volumes:
        - name: data
          {{- if .Values.persistence.enabled }}
          persistentVolumeClaim:
            claimName: {{ include "remote-whisper.dataClaim" . }}
          {{- else }}
          emptyDir: {}
          {{- end }}
        {{- if eq .Values.model.source "pvc" }}
        - name: model
          persistentVolumeClaim:
            claimName: {{ required "model.pvc.claimName is required when model.source=pvc" .Values.model.pvc.claimName }}
            readOnly: true
        {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector: {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations: {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity: {{- toYaml . | nindent 8 }}
      {{- end }}
```

`templates/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "remote-whisper.fullname" . }}
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  selector: {{- include "remote-whisper.selectorLabels" . | nindent 4 }}
  ports:
    - name: http
      port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      {{- if and (eq .Values.service.type "NodePort") .Values.service.nodePort }}
      nodePort: {{ .Values.service.nodePort }}
      {{- end }}
```

`templates/ingress.yaml`:

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "remote-whisper.fullname" . }}
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations: {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- with .Values.ingress.className }}
  ingressClassName: {{ . | quote }}
  {{- end }}
  {{- with .Values.ingress.tls }}
  tls: {{- toYaml . | nindent 4 }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: {{ .Values.ingress.path }}
            pathType: {{ .Values.ingress.pathType }}
            backend:
              service:
                name: {{ include "remote-whisper.fullname" . }}
                port:
                  number: {{ .Values.service.port }}
{{- end }}
```

`templates/NOTES.txt`:

```
remote-whisper is installed as {{ include "remote-whisper.fullname" . }}.

The pod stays "not ready" until it has loaded the model — that is normal and takes a few minutes:

  kubectl -n {{ .Release.Namespace }} rollout status deploy/{{ include "remote-whisper.fullname" . }} --timeout=15m
  kubectl -n {{ .Release.Namespace }} logs deploy/{{ include "remote-whisper.fullname" . }} -f

Open the queue page at:
{{- if .Values.ingress.enabled }}
  http{{ if .Values.ingress.tls }}s{{ end }}://{{ .Values.ingress.host }}{{ .Values.ingress.path }}
{{- else if eq .Values.service.type "NodePort" }}
  http://<any-node-ip>:{{ .Values.service.nodePort | default "<assigned-nodePort>" }}
  kubectl -n {{ .Release.Namespace }} get svc {{ include "remote-whisper.fullname" . }} -o jsonpath='{.spec.ports[0].nodePort}{"\n"}'
{{- else }}
  kubectl -n {{ .Release.Namespace }} port-forward svc/{{ include "remote-whisper.fullname" . }} 8080:{{ .Values.service.port }}
  then http://127.0.0.1:8080
{{- end }}

Point Obsidian at that same URL: Settings -> Record Meeting -> "Remote Whisper service URL".

This service has NO AUTHENTICATION. Anyone who can reach it can submit audio and read transcripts.

Throughput: whisper-large-v3 on {{ .Values.resources.limits.cpu }} CPU is roughly 0.5-1.5x realtime
and jobs run one at a time. Raise resources.limits.cpu to go faster.
```

`templates/tests/test-connection.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: {{ include "remote-whisper.fullname" . }}-test
  labels: {{- include "remote-whisper.labels" . | nindent 4 }}
  annotations:
    helm.sh/hook: test
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
spec:
  restartPolicy: Never
  {{- with .Values.imagePullSecrets }}
  imagePullSecrets: {{- toYaml . | nindent 4 }}
  {{- end }}
  containers:
    - name: probe
      image: {{ include "remote-whisper.image" . | quote }}
      command:
        - python
        - -c
        - |
          import json, sys, urllib.request
          url = "http://{{ include "remote-whisper.fullname" . }}:{{ .Values.service.port }}/healthz"
          with urllib.request.urlopen(url, timeout=10) as response:
              body = json.loads(response.read())
          print(url, response.status, body)
          sys.exit(0 if response.status == 200 else 1)
```

- [ ] **Step 5: Write the chart lint script**

Create `scripts/remote_whisper/lint-chart.sh`:

```bash
#!/usr/bin/env bash
# Lint and render the remote-whisper chart across the value permutations that matter.
# Skips cleanly (exit 0) when helm is not installed, so it is safe in any test run.
set -euo pipefail

CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../deploy/helm/remote-whisper" && pwd)"

if ! command -v helm >/dev/null 2>&1; then
  echo "SKIP: helm is not installed — install Helm 3 to lint the chart (https://helm.sh/docs/intro/install/)"
  exit 0
fi

echo "==> helm lint"
helm lint "$CHART_DIR"

render() {
  local label="$1"; shift
  echo "==> helm template ($label)"
  helm template rw "$CHART_DIR" "$@"
}

expect() {
  local haystack="$1" needle="$2"
  if ! grep -qF -- "$needle" <<<"$haystack"; then
    echo "FAIL: expected to find '$needle'" >&2
    exit 1
  fi
}

base="$(render defaults)"
expect "$base" "replicas: 1"
expect "$base" "type: Recreate"
expect "$base" 'WHISPER_THREADS: "4"'          # derived from the default limits.cpu: "4"
expect "$base" "startupProbe"
expect "$base" "kind: PersistentVolumeClaim"

millicpu="$(render millicpu --set resources.limits.cpu=1500m)"
expect "$millicpu" 'WHISPER_THREADS: "1"'

explicit="$(render explicit-threads --set whisper.threads=3)"
expect "$explicit" 'WHISPER_THREADS: "3"'

ingress="$(render ingress --set ingress.enabled=true --set ingress.host=whisper.internal)"
expect "$ingress" "kind: Ingress"
expect "$ingress" "host: \"whisper.internal\""

nodeport="$(render nodeport --set service.type=NodePort --set service.nodePort=31080)"
expect "$nodeport" "nodePort: 31080"

modelpvc="$(render model-from-pvc --set model.source=pvc --set model.pvc.claimName=whisper-models)"
expect "$modelpvc" "claimName: whisper-models"

if helm template rw "$CHART_DIR" --set model.source=pvc >/dev/null 2>&1; then
  echo "FAIL: model.source=pvc without a claimName should be rejected" >&2
  exit 1
fi

echo "OK: chart lints and renders correctly across all permutations"
```

Make it executable: `chmod +x scripts/remote_whisper/lint-chart.sh`.

- [ ] **Step 6: Run both test suites**

Run: `cd /home/user/second-brain/services/remote-whisper && python3 -m unittest discover -s tests -t . -v && bash scripts/remote_whisper/lint-chart.sh`
Expected: PASS — 84 Python tests; the lint script either prints `OK: chart lints and renders
correctly across all permutations` or the `SKIP:` line if Helm is absent. If Helm can be installed
in your environment, install it and get the real `OK` — a skipped chart check has verified nothing.

- [ ] **Step 7: Commit**

```bash
cd /home/user/second-brain
git add deploy/helm/remote-whisper scripts/remote_whisper/lint-chart.sh services/remote-whisper/tests/test_chart_contract.py
git commit -m "feat(whisper): Helm chart with derived thread count, model PVC override and probes"
```

---

### Task 10: `--service-url` mode in the transcription script

**Files:**
- Modify: `scripts/transcribe_meetings.py` (add functions after `transcribe_remote`, extend
  `process()` and `main()`)
- Test: `scripts/tests/test_transcribe_meetings.py` (append)

**Interfaces:**
- Consumes: the API from Task 5.
- Produces: `submit_job(service_url, wav, name, language=None, timeout=60) -> str`;
  `poll_job(service_url, job_id, timeout=7200, interval=2.0, on_progress=None, sleep=time.sleep) -> dict`;
  `transcribe_service(wav, service_url, name, timeout=7200, on_progress=None) -> str`;
  `process(vault, whisper_bin, model, remote_url, api_key, service_url=None, service_timeout=7200,
  on_progress=None)` — the five existing positional parameters keep their order and meaning.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_transcribe_meetings.py`:

```python
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _FakeService:
    """A stand-in for the remote-whisper API: one job, scripted status responses."""

    def __init__(self, statuses, transcript="remote transcript", language="he"):
        self.statuses = list(statuses)
        self.transcript = transcript
        self.language = language
        self.uploads = []
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _json(self, obj, status=200):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                service.uploads.append({
                    "path": self.path,
                    "body": self.rfile.read(length),
                    "content_type": self.headers.get("Content-Type"),
                })
                self._json({"id": "a" * 32, "status": "queued"}, 201)

            def do_GET(self):
                state = service.statuses.pop(0) if service.statuses else {"status": "done"}
                job = {"id": "a" * 32, "status": state["status"],
                       "progress": state.get("progress", 0.0),
                       "error": state.get("error"),
                       "transcript": service.transcript if state["status"] == "done" else None,
                       "detected_language": service.language}
                self._json(job)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def test_submit_job_posts_the_audio_with_filename_and_name(tmp_path):
    service = _FakeService([{"status": "done"}])
    try:
        wav = tmp_path / "rec.wav"
        wav.write_bytes(b"RIFFdata")
        job_id = T.submit_job(service.url, wav, "Board sync", language="he")
    finally:
        service.close()
    assert job_id == "a" * 32
    upload = service.uploads[0]
    assert upload["body"] == b"RIFFdata"
    assert upload["content_type"] == "application/octet-stream"
    assert "filename=rec.wav" in upload["path"]
    assert "name=Board+sync" in upload["path"] or "name=Board%20sync" in upload["path"]
    assert "language=he" in upload["path"]


def test_poll_job_reports_progress_then_returns_the_finished_job(tmp_path):
    service = _FakeService([
        {"status": "queued"},
        {"status": "running", "progress": 0.5},
        {"status": "done"},
    ])
    seen = []
    try:
        job = T.poll_job(service.url, "a" * 32, timeout=30, interval=0,
                         on_progress=lambda pct: seen.append(pct), sleep=lambda _s: None)
    finally:
        service.close()
    assert job["status"] == "done"
    assert 50 in seen


def test_transcribe_service_returns_the_transcript(tmp_path):
    service = _FakeService([{"status": "done"}])
    try:
        wav = tmp_path / "rec.wav"
        wav.write_bytes(b"RIFFdata")
        text = T.transcribe_service(wav, service.url, "Meeting", timeout=30)
    finally:
        service.close()
    assert text == "remote transcript"


def test_transcribe_service_raises_on_a_failed_job(tmp_path):
    service = _FakeService([{"status": "failed", "error": "model missing"}])
    try:
        wav = tmp_path / "rec.wav"
        wav.write_bytes(b"RIFFdata")
        try:
            T.transcribe_service(wav, service.url, "Meeting", timeout=30)
            raise AssertionError("expected a failure")
        except RuntimeError as exc:
            assert "model missing" in str(exc)
    finally:
        service.close()


def test_process_uses_the_service_when_given_one_and_writes_the_note(tmp_path):
    vault = _mk_vault(tmp_path)
    service = _FakeService([{"status": "done"}], transcript="שלום עולם")
    progress = []
    try:
        results = T.process(vault, Path("fake-bin"), Path("fake-model"), None, None,
                            service_url=service.url, service_timeout=30,
                            on_progress=lambda pct, name: progress.append((pct, name)))
    finally:
        service.close()
    assert results == ["OK (transcribed): 2026-09-10_10-00-00 Meeting.md"]
    note = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "שלום עולם" in note
    assert "transcription_status: done" in note
    assert "summary_status: pending" in note


def test_process_records_a_service_failure_in_the_note(tmp_path):
    vault = _mk_vault(tmp_path)
    service = _FakeService([{"status": "failed", "error": "ct2 crashed"}])
    try:
        results = T.process(vault, Path("fake-bin"), Path("fake-model"), None, None,
                            service_url=service.url, service_timeout=30)
    finally:
        service.close()
    assert results[0].startswith("FAILED")
    note = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "transcription_status: failed" in note
    assert "ct2 crashed" in note


def test_service_url_takes_precedence_over_remote_url(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_remote", lambda *a, **k: "should not be used")
    monkeypatch.setattr(T, "transcribe_service", lambda *a, **k: "from the service")
    T.process(vault, Path("fake-bin"), Path("fake-model"), "https://api.example/v1", "sk-x",
              service_url="http://whisper.internal")
    note = (vault / "Meetings" / "2026-09-10_10-00-00 Meeting.md").read_text(encoding="utf-8")
    assert "from the service" in note


def test_main_accepts_service_url_without_a_local_whisper_binary(tmp_path, monkeypatch, capsys):
    vault = _mk_vault(tmp_path)
    monkeypatch.setattr(T, "transcribe_service", lambda *a, **k: "ok text")
    exit_code = T.main([str(vault), "--service-url", "http://whisper.internal"])
    assert exit_code == 0
    assert "OK (transcribed)" in capsys.readouterr().out


def test_main_prints_progress_lines_the_plugin_can_parse(tmp_path, monkeypatch, capsys):
    vault = _mk_vault(tmp_path)

    def fake_service(wav, url, name, timeout=7200, on_progress=None):
        if on_progress:
            on_progress(42)
        return "done text"

    monkeypatch.setattr(T, "transcribe_service", fake_service)
    T.main([str(vault), "--service-url", "http://whisper.internal"])
    out = capsys.readouterr().out
    assert "PROGRESS 42 2026-09-10_10-00-00 Meeting.md" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain && python3 -m pytest scripts/tests/test_transcribe_meetings.py -q`
Expected: FAIL — `AttributeError: module 'transcribe_meetings' has no attribute 'submit_job'`

- [ ] **Step 3: Write the implementation**

In `scripts/transcribe_meetings.py`, add `time` and `urllib.parse` to the existing import line, then
insert after `transcribe_remote`:

```python
def submit_job(service_url, wav: Path, name: str, language: str | None = None, timeout: int = 60) -> str:
    """Upload audio to the remote-whisper job API. Returns the new job id."""
    params = {"filename": wav.name, "name": name}
    if language:
        params["language"] = language
    url = f"{service_url.rstrip('/')}/api/jobs?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=wav.read_bytes(), method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["id"]


def poll_job(service_url, job_id, timeout=7200, interval=2.0, on_progress=None,
             sleep=time.sleep) -> dict:
    """Poll a job until it finishes. Reports integer percentages through on_progress."""
    url = f"{service_url.rstrip('/')}/api/jobs/{job_id}"
    deadline = time.monotonic() + timeout
    last_pct = -1
    while True:
        with urllib.request.urlopen(url, timeout=60) as resp:
            job = json.loads(resp.read().decode("utf-8"))
        if on_progress:
            pct = int(round((job.get("progress") or 0) * 100))
            if pct != last_pct:
                on_progress(pct)
                last_pct = pct
        if job.get("status") in ("done", "failed"):
            return job
        if time.monotonic() >= deadline:
            raise TimeoutError(f"job {job_id} still {job.get('status')} after {timeout}s")
        sleep(interval)


def transcribe_service(wav: Path, service_url: str, name: str, timeout=7200,
                       on_progress=None) -> str:
    """Transcribe through the remote-whisper service (upload, wait, return the text)."""
    job_id = submit_job(service_url, wav, name)
    job = poll_job(service_url, job_id, timeout=timeout, on_progress=on_progress)
    if job.get("status") != "done":
        raise RuntimeError(job.get("error") or "remote transcription failed")
    return (job.get("transcript") or "").strip()
```

Change `process()` to accept and use the new mode (the five existing positional parameters stay
exactly where they are, so the current tests keep passing):

```python
def process(vault: Path, whisper_bin: Path, model: Path, remote_url: str | None,
            api_key: str | None, service_url: str | None = None, service_timeout: int = 7200,
            on_progress=None) -> list[str]:
```

and inside the loop, replace the single `transcript = (...)` expression with:

```python
        try:
            if service_url:
                report = ((lambda pct: on_progress(pct, note_path.name)) if on_progress else None)
                transcript = transcribe_service(wav, service_url, note_path.stem,
                                                timeout=service_timeout, on_progress=report)
            elif remote_url:
                transcript = transcribe_remote(wav, remote_url, api_key)
            else:
                transcript = transcribe_local(wav, whisper_bin, model)
```

In `main()`, add the flags and pass them through:

```python
    ap.add_argument("--service-url", default=None,
                    help="remote-whisper service base URL (e.g. http://whisper.internal); "
                         "uses the job API so progress is reported while it runs")
    ap.add_argument("--service-timeout", type=int, default=7200,
                    help="how long to wait for a remote-whisper job (default 2h — "
                         "large-v3 on CPU is slow)")
```

then relax the local-binary check and wire progress reporting:

```python
    if not args.service_url and not args.remote_url and not whisper_bin.is_file():
        print(f"error: whisper binary not found at {whisper_bin} "
              "(pass --service-url or --remote-url to use a remote model instead)", file=sys.stderr)
        return 1

    def report(pct, note_name):
        # The Obsidian plugin parses these lines to update its progress notice.
        print(f"PROGRESS {pct} {note_name}", flush=True)

    results = process(vault, whisper_bin, model, args.remote_url, args.api_key,
                      service_url=args.service_url, service_timeout=args.service_timeout,
                      on_progress=report if args.service_url else None)
```

Finally, extend the module docstring's first paragraph with one sentence: transcription can run
locally against the vendored whisper.cpp, against an OpenAI-compatible endpoint (`--remote-url`), or
against the vault's own remote-whisper service (`--service-url`), which reports progress while it
works.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/second-brain && python3 -m pytest scripts/tests/ -q`
Expected: PASS — 101 passed, 1 skipped (92 + 9 new), with no existing test modified

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add scripts/transcribe_meetings.py scripts/tests/test_transcribe_meetings.py
git commit -m "feat(whisper): --service-url transcription mode with progress reporting"
```

---

### Task 11: Obsidian plugin wiring

**Files:**
- Modify: `.obsidian/plugins/record-meeting/lib.js` (append two helpers + exports),
  `.obsidian/plugins/record-meeting/main.js`, `.obsidian/plugins/record-meeting/manifest.json`
- Test: `.obsidian/plugins/record-meeting/test/lib.test.js` (append, keeping the file's existing
  hand-rolled `test()` harness — do not switch it to `node:test`)

**Interfaces:**
- Consumes: `--service-url` / `--service-timeout` and the `PROGRESS <pct> <note>` stdout contract
  from Task 10.
- Produces: `parseProgressLine(line) -> {percent, note} | null`;
  `buildTranscribeArgs({scriptPath, basePath, serviceUrl, serviceTimeout}) -> string[]`;
  `progressNoticeText(state) -> string`; plugin settings `{serviceUrl: string}` persisted via
  `loadData`/`saveData`.

- [ ] **Step 1: Write the failing test**

Append to `.obsidian/plugins/record-meeting/test/lib.test.js`:

```js
const { parseProgressLine, buildTranscribeArgs, progressNoticeText } = require("../lib.js");

test("parseProgressLine reads the percentage and the note name", () => {
  assert.deepStrictEqual(parseProgressLine("PROGRESS 42 2026-09-10_10-00-00 Meeting.md"), {
    percent: 42,
    note: "2026-09-10_10-00-00 Meeting.md",
  });
  assert.deepStrictEqual(parseProgressLine("PROGRESS 0 A.md"), { percent: 0, note: "A.md" });
  assert.deepStrictEqual(parseProgressLine("PROGRESS 100 A.md"), { percent: 100, note: "A.md" });
});

test("parseProgressLine ignores other output", () => {
  assert.strictEqual(parseProgressLine("OK (transcribed): A.md"), null);
  assert.strictEqual(parseProgressLine("PROGRESS notanumber A.md"), null);
  assert.strictEqual(parseProgressLine("PROGRESS 42"), null);
  assert.strictEqual(parseProgressLine(""), null);
  assert.strictEqual(parseProgressLine(undefined), null);
});

test("buildTranscribeArgs stays local when no service URL is configured", () => {
  assert.deepStrictEqual(
    buildTranscribeArgs({ scriptPath: "/v/scripts/transcribe_meetings.py", basePath: "/v" }),
    ["/v/scripts/transcribe_meetings.py", "/v"]
  );
  assert.deepStrictEqual(
    buildTranscribeArgs({ scriptPath: "/s.py", basePath: "/v", serviceUrl: "   " }),
    ["/s.py", "/v"]
  );
});

test("buildTranscribeArgs passes a trimmed service URL and timeout through", () => {
  assert.deepStrictEqual(
    buildTranscribeArgs({
      scriptPath: "/s.py",
      basePath: "/v",
      serviceUrl: "  http://whisper.internal/  ",
      serviceTimeout: 3600,
    }),
    ["/s.py", "/v", "--service-url", "http://whisper.internal", "--service-timeout", "3600"]
  );
});

test("progressNoticeText describes what is happening", () => {
  assert.strictEqual(progressNoticeText({}), "Transcribing pending meeting recordings…");
  assert.strictEqual(
    progressNoticeText({ percent: 0, note: "A Meeting.md" }),
    "Transcribing A Meeting.md — queued on the cluster…"
  );
  assert.strictEqual(
    progressNoticeText({ percent: 42, note: "A Meeting.md" }),
    "Transcribing A Meeting.md — 42%"
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain && node --test .obsidian/plugins/record-meeting/test/lib.test.js`
Expected: FAIL — `parseProgressLine is not a function`

- [ ] **Step 3: Write the lib.js helpers**

Append to `.obsidian/plugins/record-meeting/lib.js`, before `module.exports`:

```js
// The transcription script prints `PROGRESS <pct> <note name>` while a cluster job runs; the plugin
// turns those lines into a live Notice. Kept here (pure) so it is testable with plain `node`.
const PROGRESS_RE = /^PROGRESS (\d{1,3}) (.+)$/;

function parseProgressLine(line) {
  const match = PROGRESS_RE.exec(String(line || "").trim());
  if (!match) return null;
  const percent = Number(match[1]);
  if (!Number.isFinite(percent) || percent < 0 || percent > 100) return null;
  return { percent, note: match[2] };
}

function buildTranscribeArgs({ scriptPath, basePath, serviceUrl, serviceTimeout }) {
  const args = [scriptPath, basePath];
  const url = String(serviceUrl || "").trim().replace(/\/+$/, "");
  if (url) {
    args.push("--service-url", url);
    args.push("--service-timeout", String(serviceTimeout || 7200));
  }
  return args;
}

function progressNoticeText(state) {
  if (!state || state.percent === undefined || state.percent === null) {
    return "Transcribing pending meeting recordings…";
  }
  if (state.percent === 0) return `Transcribing ${state.note} — queued on the cluster…`;
  return `Transcribing ${state.note} — ${state.percent}%`;
}
```

and extend the exports line to:

```js
module.exports = {
  timestampSlug,
  buildWavBuffer,
  meetingNoteContent,
  parseProgressLine,
  buildTranscribeArgs,
  progressNoticeText,
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/second-brain && node --test .obsidian/plugins/record-meeting/test/lib.test.js`
Expected: PASS

- [ ] **Step 5: Wire the settings tab and live progress into main.js**

In `.obsidian/plugins/record-meeting/main.js`:

1. Extend the requires:

```js
const { Plugin, Notice, PluginSettingTab, Setting, setIcon, requestUrl } = require("obsidian");
const { timestampSlug, buildWavBuffer, meetingNoteContent, parseProgressLine,
        buildTranscribeArgs, progressNoticeText } = require("./lib.js");
```

2. Add near the other constants:

```js
const DEFAULT_SETTINGS = { serviceUrl: "", serviceTimeout: 7200 };
```

3. In `onload()`, load settings first and register the tab and the queue command:

```js
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.addSettingTab(new RecordMeetingSettingTab(this.app, this));

    this.addCommand({
      id: "open-transcription-queue",
      name: "Open transcription queue",
      checkCallback: (checking) => {
        const url = String(this.settings.serviceUrl || "").trim();
        if (checking) return !!url;
        window.open(url, "_blank");
        return true;
      },
    });
```

4. Replace `transcribePending()` with a version that streams progress:

```js
  async saveSettings() {
    await this.saveData(this.settings);
  }

  async transcribePending() {
    const basePath = this.getBasePath();
    if (!basePath) {
      new Notice("Transcription requires the desktop app.");
      return;
    }
    const scriptPath = path.join(basePath, "scripts", "transcribe_meetings.py");
    const args = buildTranscribeArgs({
      scriptPath,
      basePath,
      serviceUrl: this.settings.serviceUrl,
      serviceTimeout: this.settings.serviceTimeout,
    });
    const remote = args.length > 2;

    // 0 = stays until we hide it; a cluster job can take an hour.
    const notice = new Notice(progressNoticeText({}), 0);
    try {
      const output = await this.runPython(args, (line) => {
        const progress = parseProgressLine(line);
        if (progress) notice.setMessage(progressNoticeText(progress));
      });
      const lastLine = output.trim().split("\n").filter((l) => !l.startsWith("PROGRESS")).pop();
      notice.hide();
      new Notice(lastLine || "No pending meeting recordings.");
      console.log("[record-meeting] transcribe output:\n" + output);
    } catch (e) {
      notice.hide();
      const where = remote ? "Remote transcription" : "Transcription";
      new Notice(`${where} failed: ${e.message || e}`);
      console.error("[record-meeting] transcribe error", e);
    }
  }
```

5. Change `runPython` to take the full arg list and an optional line callback, emitting each complete
stdout line as it arrives:

```js
  runPython(args, onLine) {
    return new Promise((resolve, reject) => {
      const tryNext = (i) => {
        if (i >= PYTHON_CANDIDATES.length) {
          reject(new Error("No Python interpreter found (tried python, python3, py)"));
          return;
        }
        const child = spawn(PYTHON_CANDIDATES[i], args, { windowsHide: true });
        let stdout = "";
        let stderr = "";
        let pending = "";
        let spawnFailed = false;
        child.stdout.on("data", (d) => {
          const chunk = d.toString();
          stdout += chunk;
          if (!onLine) return;
          pending += chunk;
          const lines = pending.split("\n");
          pending = lines.pop();
          lines.forEach((line) => onLine(line));
        });
        child.stderr.on("data", (d) => (stderr += d.toString()));
        child.on("error", () => {
          spawnFailed = true;
          tryNext(i + 1);
        });
        child.on("close", (code) => {
          if (spawnFailed) return;
          if (onLine && pending.trim()) onLine(pending);
          if (code === 0) resolve(stdout);
          else reject(new Error(stderr.trim() || `exit code ${code}`));
        });
      };
      tryNext(0);
    });
  }
```

6. Add the settings tab class at the bottom of the file, after the plugin class:

```js
class RecordMeetingSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Record Meeting" });

    new Setting(containerEl)
      .setName("Remote Whisper service URL")
      .setDesc(
        "Base URL of the remote-whisper service (e.g. http://whisper.internal). When set, the " +
          "captions button uploads recordings to the cluster and shows live progress. Leave empty " +
          "to transcribe locally with the vendored whisper.cpp model."
      )
      .addText((text) =>
        text
          .setPlaceholder("http://whisper.internal")
          .setValue(this.plugin.settings.serviceUrl)
          .onChange(async (value) => {
            this.plugin.settings.serviceUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Test connection")
      .setDesc("Checks /healthz on the URL above.")
      .addButton((button) =>
        button.setButtonText("Test").onClick(async () => {
          const url = String(this.plugin.settings.serviceUrl || "").trim().replace(/\/+$/, "");
          if (!url) {
            new Notice("Set a service URL first.");
            return;
          }
          button.setDisabled(true);
          try {
            const response = await requestUrl({ url: `${url}/healthz` });
            const ready = response.json && response.json.ready;
            new Notice(ready ? "Service is up and the model is loaded." :
                               "Service is up, but the model is still loading.");
          } catch (e) {
            new Notice(`Could not reach ${url}: ${e.message || e}`);
          } finally {
            button.setDisabled(false);
          }
        })
      );

    new Setting(containerEl)
      .setName("Job timeout (seconds)")
      .setDesc("How long to wait for a cluster job. whisper-large-v3 on CPU is slow — default 7200.")
      .addText((text) =>
        text.setValue(String(this.plugin.settings.serviceTimeout)).onChange(async (value) => {
          const parsed = Number(value);
          this.plugin.settings.serviceTimeout = Number.isFinite(parsed) && parsed > 0 ? parsed : 7200;
          await this.plugin.saveSettings();
        })
      );
  }
}

module.exports.RecordMeetingSettingTab = RecordMeetingSettingTab;
```

Note: `module.exports` is already assigned the plugin class, so the last line attaches the tab as a
property rather than replacing the export — Obsidian loads the default export as the plugin.

7. Bump `manifest.json` to `"version": "1.1.0"` and update its `description` to mention the
remote-whisper service with live progress.

- [ ] **Step 6: Verify the plugin's JS parses and the suites still pass**

```bash
cd /home/user/second-brain
node --check .obsidian/plugins/record-meeting/main.js
node --check .obsidian/plugins/record-meeting/lib.js
node --test .obsidian/plugins/record-meeting/test/lib.test.js scripts/dashboard_static/logic.test.js scripts/dashboard_static/recorder.test.js services/remote-whisper/tests/test_logic.js
python3 -m pytest scripts/tests/ -q
```

Expected: `node --check` silent, all JS tests pass (54 baseline + the new ones), Python 101 passed.

- [ ] **Step 7: Commit**

```bash
cd /home/user/second-brain
git add .obsidian/plugins/record-meeting
git commit -m "feat(record-meeting): remote-whisper settings tab with live transcription progress"
```

---

### Task 12: Documentation

**Files:**
- Create: `docs/gtd/remote-whisper.md`
- Modify: `docs/gtd/meeting-recording.md` (replace the "Optional: a remote Whisper API instead"
  section), `README.md` (docs list), `.claude/skills/gtd-transcribe-meeting/SKILL.md`
- Test: none (prose) — but every command in the docs must be copy-pasteable and consistent with the
  code written in Tasks 1–11.

- [ ] **Step 1: Write `docs/gtd/remote-whisper.md`**

Required sections, in this order, with exact commands:

1. **What this is** — a CPU-only whisper-large-v3 service for the air-gapped cluster; accuracy over
   the vendored `ggml-tiny.bin`; the queue page is the progress UI; one job at a time.
2. **How the pieces fit** — the ASCII diagram from the spec's *Architecture* section.
3. **Build the image (connected machine)**:
   ```bash
   cd services/remote-whisper
   ../../scripts/remote_whisper/build-image.sh --version 0.1.0
   # -> dist/remote-whisper-0.1.0-image.tar.gz and dist/remote-whisper-0.1.0.tgz
   ```
4. **Push into Harbor (air-gapped side)**:
   ```bash
   export HARBOR=harbor.internal/second-brain
   scripts/remote_whisper/push-to-harbor.sh remote-whisper-0.1.0-image.tar.gz remote-whisper-0.1.0.tgz
   ```
5. **Install**:
   ```bash
   helm install whisper oci://$HARBOR/charts/remote-whisper --version 0.1.0 \
     --namespace whisper --create-namespace \
     --set image.repository=$HARBOR/remote-whisper \
     --set ingress.enabled=true --set ingress.host=whisper.internal \
     --set resources.limits.cpu=8 --set resources.limits.memory=8Gi
   kubectl -n whisper rollout status deploy/whisper-remote-whisper --timeout=15m
   ```
6. **Values reference** — a table of every `values.yaml` key with its default and what it does,
   matching Task 9 exactly.
7. **Point Obsidian at it** — Settings → Record Meeting → service URL, Test connection, then the
   captions ribbon icon behaves as before but runs on the cluster with a live progress notice; empty
   URL restores the local path.
8. **Use it from the command line**:
   ```bash
   python scripts/transcribe_meetings.py . --service-url http://whisper.internal
   curl -s -X POST --data-binary @meeting.wav \
     -H 'Content-Type: application/octet-stream' \
     'http://whisper.internal/api/jobs?filename=meeting.wav&name=Board%20sync'
   curl -s http://whisper.internal/api/jobs | python -m json.tool
   curl -s http://whisper.internal/api/jobs/<id>/transcript
   ```
9. **API reference** — the endpoint table from the spec.
10. **Throughput and tuning** — 0.5–1.5× realtime; raise `resources.limits.cpu` first (threads
    follow it automatically); then `model.source=pvc` with `distil-large-v3` or `medium`; keep
    `beamSize: 1`; keep `vad: true` (it also suppresses large-v3's hallucinations on silence).
11. **Security** — no authentication, in bold; meeting audio and transcripts are readable by anyone
    who can reach the Service/Ingress; `retentionDays` controls how long audio lingers on the PVC.
12. **Troubleshooting** — the pod is "not ready" for minutes (normal: model load; watch the log for
    `model ready`); `413`/timeout on upload through Ingress (the `proxy-body-size` /
    `proxy-read-timeout` annotations); `MODEL LOAD FAILED` in the log with `/readyz` returning the
    reason; a job stuck in `queued` because `/readyz` never went green; `Recreate` means a rollout
    waits for the old pod to release the RWO volume; jobs requeued after a restart. Also state
    plainly: **a rollout or pod delete during a transcription kills that job** — `stop()` cannot
    interrupt the model mid-call, so after `terminationGracePeriodSeconds` (default 300) the pod is
    SIGKILLed, the job is left `running`, and the next startup requeues it from the top. Nothing is
    lost but the CPU time already spent, so prefer to roll out when the queue is empty. And: a log
    line reading `retention removed N job(s) but M audio file(s) could NOT be deleted` means
    orphaned recordings are filling the PVC — check volume permissions and remove them by hand.
13. **Local development** — `python3 -m app --fake-engine --data-dir /tmp/whisper --port 8899`, and
    the test commands for both suites.

- [ ] **Step 2: Replace the remote section in `docs/gtd/meeting-recording.md`**

Swap the existing "## Optional: a remote Whisper API instead" section for a "## Transcribing on the
cluster (remote Whisper)" section that says: the vault can transcribe against its own
whisper-large-v3 service instead of the vendored `tiny` model; set the URL in Settings → Record
Meeting (or pass `--service-url`); the captions button then shows live progress and the queue page
shows what is running; with no URL set nothing changes; the older `--remote-url` flag still works for
any OpenAI-compatible endpoint. Link to `remote-whisper.md`. Keep every other section untouched,
including "How it works offline" — add one sentence there noting the local path is still the default.

- [ ] **Step 3: Update `README.md` and the skill**

- `README.md`: add `docs/gtd/remote-whisper.md` to the docs list with a one-line description, next to
  the `meeting-recording.md` entry.
- `.claude/skills/gtd-transcribe-meeting/SKILL.md`: document that `--service-url` may be passed
  through (and that the plugin's configured URL is used automatically when the user runs the script
  from Obsidian), without changing the skill's default behaviour.

- [ ] **Step 4: Verify every command in the docs**

```bash
cd /home/user/second-brain
grep -n "python scripts/transcribe_meetings.py" docs/gtd/remote-whisper.md
python3 scripts/transcribe_meetings.py --help | head -20        # flags match the docs
bash scripts/remote_whisper/lint-chart.sh                        # values table matches the chart
```

Expected: `--service-url` and `--service-timeout` appear in `--help` exactly as documented, and the
values table lists the same keys as `values.yaml`.

- [ ] **Step 5: Commit**

```bash
cd /home/user/second-brain
git add docs/gtd/remote-whisper.md docs/gtd/meeting-recording.md README.md .claude/skills/gtd-transcribe-meeting/SKILL.md
git commit -m "docs(whisper): operator and user guide for the remote transcription service"
```

---

### Task 13: Air-gap bundle

**Files:**
- Create: `scripts/package_remote_whisper.py`, `scripts/remote_whisper/build-image.sh`,
  `scripts/remote_whisper/push-to-harbor.sh`, `scripts/remote_whisper/INSTALL.md`
- Modify: `.gitignore`
- Test: `scripts/tests/test_package_remote_whisper.py`

**Interfaces:**
- Consumes: everything from Tasks 1–12.
- Produces: `chart_version(chart_yaml_text) -> str`; `collect_entries(root) -> list[tuple[Path, str]]`;
  `manifest_text(entries) -> str`; `build_bundle(root, out_dir, version=None) -> Path`;
  `main(argv=None) -> int`; and the committed artifact
  `dist/remote-whisper-bundle-<version>.zip`.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_package_remote_whisper.py`:

```python
import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import package_remote_whisper as P

ROOT = Path(__file__).resolve().parents[2]


def test_chart_version_is_read_from_chart_yaml():
    assert P.chart_version("apiVersion: v2\nname: remote-whisper\nversion: 1.2.3\n") == "1.2.3"


def test_chart_version_rejects_a_chart_without_a_version():
    try:
        P.chart_version("name: remote-whisper\n")
        raise AssertionError("expected a failure")
    except ValueError as exc:
        assert "version" in str(exc)


def test_bundle_contains_the_service_chart_scripts_and_vault_changes(tmp_path):
    bundle = P.build_bundle(ROOT, tmp_path)
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
    prefix = bundle.stem  # remote-whisper-bundle-<version>
    for expected in (
        f"{prefix}/INSTALL.md",
        f"{prefix}/MANIFEST.txt",
        f"{prefix}/service/Dockerfile",
        f"{prefix}/service/requirements.txt",
        f"{prefix}/service/app/__main__.py",
        f"{prefix}/service/app/static/app.js",
        f"{prefix}/service/tests/test_server.py",
        f"{prefix}/chart/Chart.yaml",
        f"{prefix}/chart/values.yaml",
        f"{prefix}/chart/templates/deployment.yaml",
        f"{prefix}/scripts/build-image.sh",
        f"{prefix}/scripts/push-to-harbor.sh",
        f"{prefix}/vault-changes/scripts/transcribe_meetings.py",
        f"{prefix}/vault-changes/.obsidian/plugins/record-meeting/main.js",
        f"{prefix}/vault-changes/.obsidian/plugins/record-meeting/lib.js",
        f"{prefix}/vault-changes/docs/gtd/remote-whisper.md",
    ):
        assert expected in names, expected


def test_bundle_excludes_caches_and_the_model(tmp_path):
    bundle = P.build_bundle(ROOT, tmp_path)
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert not [n for n in names if n.endswith(".bin") or n.endswith(".tar.gz")]


def test_manifest_hashes_match_the_archived_bytes(tmp_path):
    bundle = P.build_bundle(ROOT, tmp_path)
    prefix = bundle.stem
    with zipfile.ZipFile(bundle) as zf:
        manifest = zf.read(f"{prefix}/MANIFEST.txt").decode("utf-8")
        listed = {}
        for line in manifest.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            digest, name = line.split(None, 1)
            listed[name.strip()] = digest
        assert listed, "manifest lists no files"
        for name, digest in listed.items():
            actual = hashlib.sha256(zf.read(f"{prefix}/{name}")).hexdigest()
            assert actual == digest, name


def test_rebuilding_produces_identical_bytes(tmp_path):
    first = P.build_bundle(ROOT, tmp_path / "a").read_bytes()
    second = P.build_bundle(ROOT, tmp_path / "b").read_bytes()
    assert first == second


def test_bundle_name_carries_the_chart_version(tmp_path):
    version = P.chart_version((ROOT / "deploy/helm/remote-whisper/Chart.yaml").read_text())
    bundle = P.build_bundle(ROOT, tmp_path)
    assert bundle.name == f"remote-whisper-bundle-{version}.zip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/second-brain && python3 -m pytest scripts/tests/test_package_remote_whisper.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'package_remote_whisper'`

- [ ] **Step 3: Write the packaging script**

Create `scripts/package_remote_whisper.py`:

```python
#!/usr/bin/env python3
"""Build the air-gap bundle for the remote Whisper service. Stdlib only.

Produces dist/remote-whisper-bundle-<chart version>.zip: the service source, the Helm chart, the
build/push scripts, an INSTALL guide, a sha256 manifest, and copies of every vault file that changed
so they can be dropped into an air-gapped clone of this vault.

The image tar is deliberately NOT in here: it is ~4GB and needs Docker plus internet to produce.
Run scripts/remote_whisper/build-image.sh on a connected machine for that.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

VERSION_RE = re.compile(r"^version:\s*([0-9A-Za-z.+-]+)\s*$", re.MULTILINE)
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)  # deterministic archives

EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".git", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".bin", ".tgz", ".tar", ".gz", ".zip"}

# (source path relative to the repo root, destination prefix inside the bundle)
TREES = [
    ("services/remote-whisper", "service"),
    ("deploy/helm/remote-whisper", "chart"),
]
SCRIPTS = [
    ("scripts/remote_whisper/build-image.sh", "scripts/build-image.sh"),
    ("scripts/remote_whisper/push-to-harbor.sh", "scripts/push-to-harbor.sh"),
    ("scripts/remote_whisper/lint-chart.sh", "scripts/lint-chart.sh"),
    ("scripts/remote_whisper/INSTALL.md", "INSTALL.md"),
]
# Files the air-gapped vault needs updating with, kept at their vault-relative paths.
VAULT_CHANGES = [
    "scripts/transcribe_meetings.py",
    "scripts/package_remote_whisper.py",
    ".obsidian/plugins/record-meeting/main.js",
    ".obsidian/plugins/record-meeting/lib.js",
    ".obsidian/plugins/record-meeting/manifest.json",
    ".obsidian/plugins/record-meeting/test/lib.test.js",
    "docs/gtd/remote-whisper.md",
    "docs/gtd/meeting-recording.md",
    ".claude/skills/gtd-transcribe-meeting/SKILL.md",
]


def chart_version(chart_yaml: str) -> str:
    match = VERSION_RE.search(chart_yaml)
    if not match:
        raise ValueError("Chart.yaml has no top-level 'version:' field")
    return match.group(1)


def _skip(path: Path) -> bool:
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def collect_entries(root: Path) -> list[tuple[Path, str]]:
    """Returns [(absolute source path, bundle-relative destination)], sorted by destination."""
    entries: list[tuple[Path, str]] = []
    for source_dir, prefix in TREES:
        base = root / source_dir
        for path in base.rglob("*"):
            if path.is_file() and not _skip(path.relative_to(base)):
                entries.append((path, f"{prefix}/{path.relative_to(base).as_posix()}"))
    for source, destination in SCRIPTS:
        path = root / source
        if path.is_file():
            entries.append((path, destination))
    for relative in VAULT_CHANGES:
        path = root / relative
        if path.is_file():
            entries.append((path, f"vault-changes/{relative}"))
    return sorted(entries, key=lambda item: item[1])


def manifest_text(entries: list[tuple[Path, str]]) -> str:
    lines = ["# sha256  path (relative to this bundle's root)"]
    for path, destination in entries:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {destination}")
    return "\n".join(lines) + "\n"


def build_bundle(root: Path, out_dir: Path, version: str | None = None) -> Path:
    root = Path(root).resolve()
    version = version or chart_version(
        (root / "deploy/helm/remote-whisper/Chart.yaml").read_text(encoding="utf-8"))
    entries = collect_entries(root)
    if not entries:
        raise RuntimeError("nothing to bundle — run this from the repo root")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"remote-whisper-bundle-{version}"
    target = out_dir / f"{name}.zip"
    if target.exists():
        target.unlink()

    executable = {"scripts/build-image.sh", "scripts/push-to-harbor.sh", "scripts/lint-chart.sh"}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, destination in entries:
            info = zipfile.ZipInfo(f"{name}/{destination}", date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if destination in executable else 0o644) << 16
            zf.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(f"{name}/MANIFEST.txt", date_time=FIXED_TIMESTAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        zf.writestr(info, manifest_text(entries))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="repo root (default: this script's parent)")
    parser.add_argument("--out", default=None, help="output directory (default: <root>/dist)")
    parser.add_argument("--version", default=None, help="override the bundle version")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    out_dir = Path(args.out) if args.out else root / "dist"
    bundle = build_bundle(root, out_dir, args.version)
    size_mb = bundle.stat().st_size / (1024 * 1024)
    with zipfile.ZipFile(bundle) as zf:
        count = len(zf.namelist())
    print(f"{bundle} ({count} files, {size_mb:.2f} MB)")
    print("Next: build the image on a connected machine with scripts/remote_whisper/build-image.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write the build script**

Create `scripts/remote_whisper/build-image.sh` (run on a machine with Docker **and** internet):

```bash
#!/usr/bin/env bash
# Build the remote-whisper image (downloads the whisper-large-v3 CTranslate2 weights), save it as a
# transferable tar, and package the Helm chart. Run this OUTSIDE the air gap.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_DIR="$REPO_ROOT/services/remote-whisper"
CHART_DIR="$REPO_ROOT/deploy/helm/remote-whisper"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/dist}"
IMAGE_NAME="${IMAGE_NAME:-remote-whisper}"
MODEL_REPO="${MODEL_REPO:-Systran/faster-whisper-large-v3}"
MODEL_REVISION="${MODEL_REVISION:-main}"
VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --image-name) IMAGE_NAME="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "usage: build-image.sh [--version X.Y.Z] [--image-name NAME] [--out DIR]"
      echo "env: MODEL_REPO, MODEL_REVISION, OUT_DIR"
      exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }

if [[ -z "$VERSION" ]]; then
  VERSION="$(sed -n 's/^version:[[:space:]]*//p' "$CHART_DIR/Chart.yaml" | head -1)"
fi
[[ -n "$VERSION" ]] || { echo "could not determine a version" >&2; exit 1; }

mkdir -p "$OUT_DIR"
TAG="$IMAGE_NAME:$VERSION"

echo "==> building $TAG (this downloads ~3GB of model weights)"
docker build \
  --build-arg "MODEL_REPO=$MODEL_REPO" \
  --build-arg "MODEL_REVISION=$MODEL_REVISION" \
  -t "$TAG" "$SERVICE_DIR"

echo "==> resolved dependency versions in the image"
docker run --rm --entrypoint python "$TAG" -c \
  "import faster_whisper, ctranslate2; print('faster-whisper', faster_whisper.__version__, '/ ctranslate2', ctranslate2.__version__)"

IMAGE_TAR="$OUT_DIR/$IMAGE_NAME-$VERSION-image.tar.gz"
echo "==> saving $IMAGE_TAR"
docker save "$TAG" | gzip -9 > "$IMAGE_TAR"

if command -v helm >/dev/null 2>&1; then
  echo "==> packaging the chart"
  helm package "$CHART_DIR" --destination "$OUT_DIR" --version "$VERSION" --app-version "$VERSION"
else
  echo "WARNING: helm not found — chart not packaged. Install Helm 3 and re-run, or copy" >&2
  echo "         deploy/helm/remote-whisper/ into the air gap and 'helm package' it there." >&2
fi

echo "==> done"
for artifact in "$IMAGE_TAR" "$OUT_DIR/$IMAGE_NAME-$VERSION.tgz"; do
  [[ -f "$artifact" ]] && printf '%s  %s\n' "$(sha256sum "$artifact" | cut -d' ' -f1)" "$artifact"
done
echo "Transfer those into the air gap, then run push-to-harbor.sh there."
```

- [ ] **Step 5: Write the Harbor push script**

Create `scripts/remote_whisper/push-to-harbor.sh` (run **inside** the air gap):

```bash
#!/usr/bin/env bash
# Load the transferred image into Docker, push it to Harbor, and push the chart as an OCI artifact.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: HARBOR=harbor.internal/second-brain push-to-harbor.sh <image.tar.gz> [chart.tgz]

env:
  HARBOR        required, e.g. harbor.internal/second-brain
  IMAGE_NAME    image name inside the project (default: remote-whisper)
  CHART_REPO    chart path inside Harbor (default: $HARBOR/charts)
EOF
}

[[ $# -ge 1 ]] || { usage; exit 2; }
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

IMAGE_TAR="$1"
CHART_TGZ="${2:-}"
: "${HARBOR:?set HARBOR to your registry project, e.g. harbor.internal/second-brain}"
IMAGE_NAME="${IMAGE_NAME:-remote-whisper}"
CHART_REPO="${CHART_REPO:-$HARBOR/charts}"

command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
[[ -f "$IMAGE_TAR" ]] || { echo "no such file: $IMAGE_TAR" >&2; exit 1; }

echo "==> loading $IMAGE_TAR"
LOADED="$(docker load -i "$IMAGE_TAR" | sed -n 's/^Loaded image: //p' | head -1)"
[[ -n "$LOADED" ]] || { echo "could not determine the loaded image tag" >&2; exit 1; }
VERSION="${LOADED##*:}"
TARGET="$HARBOR/$IMAGE_NAME:$VERSION"

echo "==> tagging $LOADED as $TARGET"
docker tag "$LOADED" "$TARGET"
echo "==> pushing $TARGET (run 'docker login $HARBOR' first if this fails)"
docker push "$TARGET"

if [[ -n "$CHART_TGZ" ]]; then
  command -v helm >/dev/null || { echo "helm is required to push the chart" >&2; exit 1; }
  echo "==> pushing chart $CHART_TGZ to oci://$CHART_REPO"
  helm push "$CHART_TGZ" "oci://$CHART_REPO"
fi

cat <<EOF

==> done. Install with:

helm install whisper oci://$CHART_REPO/remote-whisper --version $VERSION \\
  --namespace whisper --create-namespace \\
  --set image.repository=$HARBOR/$IMAGE_NAME \\
  --set ingress.enabled=true --set ingress.host=whisper.internal \\
  --set resources.limits.cpu=8 --set resources.limits.memory=8Gi

kubectl -n whisper rollout status deploy/whisper-remote-whisper --timeout=15m
EOF
```

`chmod +x` both scripts.

- [ ] **Step 6: Write `scripts/remote_whisper/INSTALL.md`**

The guide that ships *inside* the zip, written for someone who has only the zip. Sections, in order:
what is in the bundle (the tree from the spec); prerequisites (Docker + internet on the build
machine; Harbor + Helm 3 + kubectl in the air gap; no GPU needed); step 1 build
(`scripts/build-image.sh --version <v>`, ~4GB output, what it downloads); step 2 transfer (the two
artifacts and their sha256s from `MANIFEST.txt`); step 3 push
(`HARBOR=... scripts/push-to-harbor.sh ...`); step 4 install (the `helm install` command, and
`kubectl rollout status` with a 15m timeout because of the model load); step 5 verify (`curl
http://<host>/healthz`, open the queue page, drag a short wav onto it); step 6 update the vault
(copy `vault-changes/` over an air-gapped clone at the same relative paths, then set the service URL
in Obsidian → Settings → Record Meeting); how to run the tests offline (`python3 -m unittest discover
-s service/tests -t service` and `node --test service/tests/test_logic.js`); the no-authentication
warning; and a throughput note (one job at a time, 0.5–1.5× realtime, raise `resources.limits.cpu`).

- [ ] **Step 7: Ignore build outputs but keep the bundle**

Append to `.gitignore`:

```
# Build outputs from scripts/remote_whisper/build-image.sh (multi-GB) — the source bundle is kept
dist/*
!dist/remote-whisper-bundle-*.zip
```

- [ ] **Step 8: Run the tests and build the real bundle**

```bash
cd /home/user/second-brain
chmod +x scripts/remote_whisper/build-image.sh scripts/remote_whisper/push-to-harbor.sh scripts/remote_whisper/lint-chart.sh
bash -n scripts/remote_whisper/build-image.sh
bash -n scripts/remote_whisper/push-to-harbor.sh
python3 -m pytest scripts/tests/ -q
python3 scripts/package_remote_whisper.py
unzip -l dist/remote-whisper-bundle-0.1.0.zip | tail -5
```

Expected: `bash -n` silent for both scripts; 108 Python tests passing; the zip built and listed.

- [ ] **Step 9: Commit**

```bash
cd /home/user/second-brain
git add scripts/package_remote_whisper.py scripts/remote_whisper scripts/tests/test_package_remote_whisper.py .gitignore
git commit -m "feat(whisper): deterministic air-gap bundle with Harbor build and push scripts"
git add -f dist/remote-whisper-bundle-*.zip
git commit -m "chore(whisper): commit the air-gap bundle zip for offline import"
```

---

## Final verification

- [ ] **Run every suite and confirm the numbers**

```bash
cd /home/user/second-brain
(cd services/remote-whisper && python3 -m unittest discover -s tests -t . 2>&1 | tail -3)
python3 -m pytest scripts/tests/ -q 2>&1 | tail -3
node --test scripts/dashboard_static/logic.test.js scripts/dashboard_static/recorder.test.js \
  .obsidian/plugins/record-meeting/test/lib.test.js services/remote-whisper/tests/test_logic.js 2>&1 | tail -8
bash scripts/remote_whisper/lint-chart.sh
node --check .obsidian/plugins/record-meeting/main.js
```

Expected: service suite 84 tests, `scripts/tests` 108 passed / 1 skipped (up from 92/1), JS suites
all passing with none of the 54 baseline tests lost, chart lint `OK` (or an explicit `SKIP` if Helm
is unavailable), `node --check` silent.

- [ ] **End-to-end smoke test with the fake engine**

```bash
cd /home/user/second-brain
rm -rf /tmp/whisper-e2e && mkdir -p /tmp/whisper-e2e
(cd services/remote-whisper && python3 -m app --fake-engine --data-dir /tmp/whisper-e2e --port 8899 &)
sleep 3
python3 - <<'PY'
import subprocess, urllib.request, json, wave, tempfile, os
from pathlib import Path
vault = Path(tempfile.mkdtemp())
(vault / "Meetings" / "recordings").mkdir(parents=True)
wav = vault / "Meetings" / "recordings" / "2026-09-15_10-00-00.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x00" * 16000)
(vault / "Meetings" / "2026-09-15_10-00-00 Meeting.md").write_text(
    '---\ntype: meeting\ndate: 2026-09-15\n'
    'recording: "[[Meetings/recordings/2026-09-15_10-00-00.wav]]"\n'
    'transcription_status: pending\n---\n\n## Transcript\n\n## Action items\n- [ ]  #next\n',
    encoding="utf-8")
print(subprocess.run(["python3", "scripts/transcribe_meetings.py", str(vault),
                      "--service-url", "http://127.0.0.1:8899"],
                     capture_output=True, text=True).stdout)
print((vault / "Meetings" / "2026-09-15_10-00-00 Meeting.md").read_text(encoding="utf-8")[:400])
print(json.loads(urllib.request.urlopen("http://127.0.0.1:8899/api/jobs").read())["stats"])
PY
pkill -f "python3 -m app --fake-engine" || true
```

Expected: `PROGRESS` lines then `OK (transcribed)`, the note containing the fake transcript with
`transcription_status: done` and `summary_status: pending`, and stats showing one `done` job.

- [ ] **Confirm the vault still has no third-party imports**

```bash
cd /home/user/second-brain
grep -rn "^import \|^from " services/remote-whisper/app scripts/*.py | \
  grep -v -E "^\S+:(import|from) (__future__|argparse|datetime|hashlib|http|io|json|os|pathlib|re|signal|sqlite3|subprocess|sys|tempfile|threading|time|traceback|urllib|uuid|wave|zipfile|dataclasses|typing|collections|email|shutil|wsgiref|socketserver)" | \
  grep -v "from \." || echo "OK: stdlib only"
```

Expected: `OK: stdlib only` — faster-whisper must appear **only** inside `FasterWhisperEngine.load()`.

- [ ] **Rebuild the bundle so the committed zip matches the final tree, then push**

```bash
cd /home/user/second-brain
python3 scripts/package_remote_whisper.py
git add -f dist/remote-whisper-bundle-*.zip
git commit -m "chore(whisper): refresh the air-gap bundle" || echo "bundle unchanged"
git push -u origin claude/remote-whisper-helm-chart-uuyary
```

---

## Self-Review

**Spec coverage:** every spec section maps to a task — Architecture/Layout → Tasks 1–7; Job model and
state machine → Task 1; Engine interface → Task 2; HTTP API (including the `/v1` shim and the
streaming upload requirement) → Tasks 3 and 5; Web UI → Task 7; Image → Task 8; Helm chart → Task 9;
Client integration → Tasks 10 and 11; Air-gap bundle → Task 13; Testing approach → the test step of
every task plus Final verification; Open risks → documented in Task 12's throughput, security and
troubleshooting sections.

**Two deliberate refinements of the spec**, both noted inline where they occur: `app/multipart.py`
exists as its own module (the spec's layout folded it into `server.py`), and uploaded audio is named
by a random hex id rather than the job id (the file must exist before the row that would name it).

**Known gaps, stated rather than hidden:** the image cannot be built in this session (no Hugging Face
access, ~4GB of disk), so Task 8 Step 6 verifies only the runtime stage and hands the real build to
`build-image.sh`; and `helm` may be absent, in which case `lint-chart.sh` skips — Task 9 Step 6 says
plainly that a skipped chart check has verified nothing.
