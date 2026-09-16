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
