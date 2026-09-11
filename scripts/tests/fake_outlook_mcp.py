"""Stand-in for outlook-mcp-rs in tests: answers `initialize` and `tools/call list_events` over
stdio JSON-RPC. argv[1] picks a mode: ok (default), error (tool error), hang (never answers)."""
import json
import sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

MODE = sys.argv[1] if len(sys.argv) > 1 else "ok"
EVENTS = [
    {"id": "1", "subject": "סנכרון שבועי", "start": "2026-09-11T09:30:00", "end": "2026-09-11T10:00:00",
     "location": "Room 1", "all_day": False, "my_response": "accepted", "required_attendees": "Dana; Omer"},
    {"id": "2", "subject": "Declined thing", "start": "2026-09-11T08:00:00", "end": "2026-09-11T09:00:00",
     "location": "", "all_day": False, "my_response": "declined", "required_attendees": ""},
    {"id": "3", "subject": "Holiday", "start": "2026-09-12T00:00:00", "end": "2026-09-13T00:00:00",
     "location": "", "all_day": True, "my_response": "organizer", "required_attendees": ""},
]

for line in sys.stdin:
    msg = json.loads(line)
    if MODE == "hang" or "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "0"}}
    elif msg["method"] == "tools/call":
        args = msg["params"].get("arguments", {})
        if MODE == "error" or msg["params"]["name"] != "list_events" or "start_date" not in args or "end_date" not in args:
            result = {"content": [{"type": "text", "text": "Outlook is not running"}], "isError": True}
        else:
            result = {"content": [{"type": "text", "text": json.dumps(EVENTS, ensure_ascii=False)}], "isError": False}
    else:
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
