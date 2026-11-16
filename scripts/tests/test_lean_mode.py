import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lean_mode as L


def _root(r: Path):
    for n in ("brainstorming", "writing-skills", "gtd-status"):
        (r / ".claude/skills" / n).mkdir(parents=True)
        (r / ".claude/skills" / n / "SKILL.md").write_text("x")
    (r / ".claude/settings.local.json").write_text(json.dumps({"permissions": {"deny": ["Read(./secret)"]}}))
    return r


def test_on_off_round_trip(tmp_path, capsys):
    r = _root(tmp_path)
    L.main(["on", "--root", str(r)])
    assert not (r / ".claude/skills/brainstorming").exists()
    assert (r / ".claude/skills-dev/writing-skills/SKILL.md").exists()
    assert (r / ".claude/skills/gtd-status").exists()
    s = json.loads((r / ".claude/settings.local.json").read_text())
    assert "Read(./vendor/**)" in s["permissions"]["deny"] and "Read(./secret)" in s["permissions"]["deny"]
    assert s["disabledMcpjsonServers"] == ["outlook"]
    L.main(["on", "--root", str(r)])  # idempotent
    L.main(["off", "--root", str(r)])
    assert (r / ".claude/skills/brainstorming/SKILL.md").exists()
    assert not (r / ".claude/skills-dev").exists()
    s = json.loads((r / ".claude/settings.local.json").read_text())
    assert s == {"permissions": {"deny": ["Read(./secret)"]}}


def test_keep_outlook(tmp_path, capsys):
    r = _root(tmp_path)
    L.main(["on", "--keep-outlook", "--root", str(r)])
    s = json.loads((r / ".claude/settings.local.json").read_text())
    assert "disabledMcpjsonServers" not in s
