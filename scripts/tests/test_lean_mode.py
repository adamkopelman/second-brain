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
    assert s["outputStyle"] == "GTD Lean"
    assert s["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "12000"
    assert "lean_guard.sh" in s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    L.main(["on", "--context", "256000", "--no-thinking", "--root", str(r)])  # idempotent, adds
    s = json.loads((r / ".claude/settings.local.json").read_text())
    assert len(s["hooks"]["PreToolUse"]) == 1
    assert s["env"]["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "256000" and s["env"]["MAX_THINKING_TOKENS"] == "0"
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


def test_off_keeps_users_own_style_and_hooks(tmp_path, capsys):
    r = _root(tmp_path)
    mine = {"outputStyle": "Concise", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}]}}
    (r / ".claude/settings.local.json").write_text(json.dumps(mine))
    L.main(["on", "--root", str(r)])
    s = json.loads((r / ".claude/settings.local.json").read_text())
    assert s["outputStyle"] == "Concise" and len(s["hooks"]["PreToolUse"]) == 2
    L.main(["off", "--root", str(r)])
    assert json.loads((r / ".claude/settings.local.json").read_text()) == mine
