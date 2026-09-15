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
