import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import outlook_calendar as OC

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_outlook_mcp.py")]
D1, D2 = dt.date(2026, 9, 11), dt.date(2026, 9, 18)


def test_call_list_events_speaks_mcp_over_stdio():
    events = OC.call_list_events(FAKE, D1, D2)
    assert [e["subject"] for e in events] == ["סנכרון שבועי", "Declined thing", "Holiday"]


def test_call_list_events_raises_unavailable_on_a_tool_error():
    with pytest.raises(OC.OutlookUnavailable, match="not running"):
        OC.call_list_events(FAKE + ["error"], D1, D2)


def test_call_list_events_times_out_on_a_hung_server():
    with pytest.raises(OC.OutlookUnavailable):
        OC.call_list_events(FAKE + ["hang"], D1, D2, timeout=2)


def test_call_list_events_raises_unavailable_when_the_binary_is_missing(tmp_path):
    with pytest.raises(OC.OutlookUnavailable):
        OC.call_list_events([str(tmp_path / "missing.exe")], D1, D2)


def test_normalize_drops_declined_trims_times_and_sorts_all_day_first():
    out = OC.normalize([
        {"subject": "Late", "start": "2026-09-11T15:00:00", "end": "2026-09-11T16:00:00", "all_day": False},
        {"subject": "Declined", "start": "2026-09-11T08:00:00", "end": "2026-09-11T09:00:00", "my_response": "declined"},
        {"subject": "Off", "start": "2026-09-11T00:00:00", "end": "2026-09-12T00:00:00", "all_day": True},
        {"subject": "", "start": "2026-09-11T10:00:00", "end": "2026-09-11T10:30:00", "location": "Zoom",
         "required_attendees": "Dana"},
        {"subject": "No start"},
    ])
    assert [e["subject"] for e in out] == ["Off", "(no subject)", "Late"]
    assert out[1] == {"subject": "(no subject)", "start": "2026-09-11T10:00", "end": "2026-09-11T10:30",
                      "date": "2026-09-11", "all_day": False, "location": "Zoom", "attendees": "Dana"}


def test_calendar_cache_reports_loading_then_ok():
    cache = OC.CalendarCache(["x"], fetch=lambda cmd, s, e: [
        {"subject": "A", "start": "2026-09-11T10:00:00", "end": "2026-09-11T11:00:00"}],
        today=lambda: D1)
    assert cache.snapshot()["status"] == "loading"
    cache.refresh()
    snap = cache.snapshot()
    assert snap["status"] == "ok"
    assert snap["events"][0]["subject"] == "A"
    assert snap["updated"]


def test_calendar_cache_passes_a_week_window_to_the_fetcher():
    seen = []
    cache = OC.CalendarCache(["x"], fetch=lambda cmd, s, e: seen.append((cmd, s, e)) or [], today=lambda: D1)
    cache.refresh()
    assert seen == [(["x"], D1, D1 + dt.timedelta(days=7))]


def test_calendar_cache_without_a_command_is_unavailable():
    snap = OC.CalendarCache(None).snapshot()
    assert snap["status"] == "unavailable"
    assert "not found" in snap["error"]


def test_calendar_cache_reports_a_failed_fetch_as_unavailable():
    def boom(*_):
        raise OC.OutlookUnavailable("Outlook is not running")
    cache = OC.CalendarCache(["x"], fetch=boom)
    cache.refresh()
    snap = cache.snapshot()
    assert (snap["status"], snap["error"], snap["events"]) == ("unavailable", "Outlook is not running", [])
