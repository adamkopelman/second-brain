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
