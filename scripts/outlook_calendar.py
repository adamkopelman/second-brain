#!/usr/bin/env python3
"""Outlook calendar for the local dashboard, read through the vendored outlook-mcp-rs MCP server
(spoken to directly over stdio JSON-RPC). stdlib only. Read-only: only `list_events` is ever called."""
from __future__ import annotations
import datetime as _dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BIN = REPO_ROOT / "vendor" / "outlook-mcp-rs" / "outlook-mcp-rs.exe"
PROTOCOL_VERSION = "2024-11-05"


class OutlookUnavailable(Exception):
    pass


def resolve_command() -> list[str] | None:
    """$OUTLOOK_MCP_BIN (what .mcp.json uses), else the vendored Windows binary."""
    env = os.environ.get("OUTLOOK_MCP_BIN")
    if env and Path(env).is_file():
        return [env]
    if sys.platform == "win32" and DEFAULT_BIN.is_file():
        return [str(DEFAULT_BIN)]
    return None


def call_list_events(command: list[str], start: _dt.date, end: _dt.date, timeout: float = 60) -> list[dict]:
    """Start the MCP server, handshake, call list_events once, shut it down."""
    try:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise OutlookUnavailable(f"could not start the Outlook MCP server: {e}") from e
    watchdog = threading.Timer(timeout, proc.kill)  # a hung server gets killed, which ends readline()
    watchdog.start()
    try:
        def send(msg: dict) -> None:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        def recv(want_id: int) -> dict:
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise OutlookUnavailable("the Outlook MCP server exited or timed out")
                line = line.strip()
                if line.startswith("{"):
                    msg = json.loads(line)
                    if msg.get("id") == want_id:
                        return msg

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "gtd-dashboard", "version": "1"}}})
        recv(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "list_events",
            "arguments": {"start_date": start.isoformat(), "end_date": end.isoformat()}}})
        msg = recv(2)
    except (OSError, ValueError) as e:  # broken pipe, malformed JSON
        raise OutlookUnavailable(f"talking to the Outlook MCP server failed: {e}") from e
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    if "error" in msg:
        raise OutlookUnavailable(msg["error"].get("message", "list_events failed"))
    result = msg.get("result", {})
    text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    if result.get("isError"):
        raise OutlookUnavailable(text or "list_events failed")
    try:
        events = json.loads(text or "[]")
    except ValueError as e:
        raise OutlookUnavailable(f"unexpected list_events output: {text[:80]!r}") from e
    return events if isinstance(events, list) else []


def query_window(today: _dt.date, days: int) -> tuple[_dt.date, _dt.date]:
    """The date range to ask list_events for. outlook-mcp-rs hands dates to Outlook month-first,
    and on a day-first locale (e.g. en-IL) Outlook reads them the other way round — 2026-09-11 turns
    into 9 Nov. Dates whose day equals their month (1 Jan, 2 Feb … 12 Dec) read the same either way,
    so ask for the tightest such range around [today, today + days] and trim the result afterwards."""
    need_end = today + _dt.timedelta(days=days)
    candidates = [_dt.date(y, m, m) for y in (today.year - 1, today.year, today.year + 1) for m in range(1, 13)]
    return (max(c for c in candidates if c <= today), min(c for c in candidates if c >= need_end))


def normalize(events: list[dict]) -> list[dict]:
    """Just what the dashboard shows, declined meetings dropped, sorted by day (all-day first)."""
    out = []
    for e in events:
        start = str(e.get("start") or "")
        if len(start) < 10 or e.get("my_response") == "declined":
            continue
        out.append({
            "subject": e.get("subject") or "(no subject)",
            "start": start[:16],
            "end": str(e.get("end") or "")[:16],
            "date": start[:10],
            "all_day": bool(e.get("all_day")),
            "location": e.get("location") or "",
            "attendees": e.get("required_attendees") or "",
        })
    out.sort(key=lambda x: (x["date"], not x["all_day"], x["start"]))
    return out


class CalendarCache:
    """Keeps the next `days` days of events fresh from a background thread, so /api/state never
    waits on Outlook; snapshot() is always instant."""

    def __init__(self, command, ttl=60, days=7, fetch=call_list_events, today=_dt.date.today):
        self._command, self._ttl, self._days, self._fetch, self._today = command, ttl, days, fetch, today
        self._lock = threading.Lock()
        if command:
            self._state = {"status": "loading", "error": None, "events": [], "updated": None}
        else:
            self._state = {"status": "unavailable", "error": "Outlook MCP server not found "
                           "(set OUTLOOK_MCP_BIN — see docs/gtd/outlook.md)", "events": [], "updated": None}

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)

    def refresh(self) -> None:
        if not self._command:
            return
        today = self._today()
        first, last = today.isoformat(), (today + _dt.timedelta(days=self._days)).isoformat()
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        try:
            events = normalize(self._fetch(self._command, *query_window(today, self._days)))
            events = [e for e in events if first <= e["date"] < last]
            new = {"status": "ok", "error": None, "events": events, "updated": stamp}
        except OutlookUnavailable as e:
            new = {"status": "unavailable", "error": str(e), "events": [], "updated": stamp}
        with self._lock:
            self._state = new

    def start(self) -> None:
        def loop():
            while True:
                self.refresh()
                time.sleep(self._ttl)
        threading.Thread(target=loop, daemon=True, name="outlook-calendar").start()
