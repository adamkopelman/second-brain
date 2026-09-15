"""The transcription worker: one thread, one job at a time, model resident between jobs."""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path


def unlink_audio(paths) -> int:
    removed = 0
    for path in paths:
        try:
            Path(path).unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return removed


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
            self.sweep_retention()
            if self.run_once() is None:
                self.stop_event.wait(self.poll_interval)

    def run_once(self) -> str | None:
        job = self.store.claim_next()
        if job is None:
            return None
        job_id = job["id"]
        audio = Path(job["audio_path"])
        if not audio.is_file():
            self.store.fail(job_id, f"audio file is missing: {audio}")
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
            self.store.fail(job_id, f"{type(exc).__name__}: {exc}")
            self.log(f"[whisper] failed {job_id}: {exc}\n{traceback.format_exc()}")
        return job_id

    def sweep_retention(self, force=False) -> int:
        if self.retention_days <= 0:
            return 0
        now = self.clock()
        if not force and self._last_sweep is not None and (now - self._last_sweep) < self.retention_interval:
            return 0
        self._last_sweep = now
        paths = self.store.purge_finished(self.retention_days)
        unlink_audio(paths)
        if paths:
            self.log(f"[whisper] retention removed {len(paths)} job(s)")
        return len(paths)
