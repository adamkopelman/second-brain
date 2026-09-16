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

    stopping = threading.Event()
    worker = Worker(store, engine, retention_days=config.retention_days)
    if engine_state.ready:
        threading.Thread(target=worker.run, name="worker", daemon=True).start()

    def shutdown(signum, _frame):
        print(f"[whisper] signal {signum}, shutting down", flush=True)
        worker.stop()
        stopping.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    stopping.wait()
    httpd.shutdown()
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
