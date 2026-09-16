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
