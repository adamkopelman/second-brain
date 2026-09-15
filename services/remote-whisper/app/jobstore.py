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
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs (status, created_at, id);
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
        """Atomically move the oldest queued job to running. FIFO is the database's job, not ours."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, id LIMIT 1"
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
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
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
            "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, id"
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
