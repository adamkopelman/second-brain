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
