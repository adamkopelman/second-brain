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
