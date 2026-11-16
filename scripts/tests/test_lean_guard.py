import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / ".claude/hooks/lean_guard.py"


def run(ev):
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(ev), capture_output=True, text=True)
    assert r.returncode == 0
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def _files(tmp):
    (tmp / "big.md").write_text("x" * 20000)
    (tmp / "small.md").write_text("hi")
    return str(tmp)


def test_read_big_without_limit_denied_with_limit_allowed(tmp_path):
    cwd = _files(tmp_path)
    out = run({"tool_name": "Read", "tool_input": {"file_path": "big.md"}, "cwd": cwd})
    assert out["permissionDecision"] == "deny" and "offset/limit" in out["permissionDecisionReason"]
    assert run({"tool_name": "Read", "tool_input": {"file_path": "big.md", "limit": 100}, "cwd": cwd}) is None
    assert run({"tool_name": "Read", "tool_input": {"file_path": "small.md"}, "cwd": cwd}) is None
    assert run({"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "missing.md")}, "cwd": cwd}) is None


def test_bash_dumps_and_recursive_listing(tmp_path):
    cwd = _files(tmp_path)
    assert run({"tool_name": "Bash", "tool_input": {"command": "cat big.md"}, "cwd": cwd})
    assert run({"tool_name": "Bash", "tool_input": {"command": "cat big.md | head -20"}, "cwd": cwd}) is None
    assert run({"tool_name": "Bash", "tool_input": {"command": "cat small.md"}, "cwd": cwd}) is None
    assert run({"tool_name": "Bash", "tool_input": {"command": "ls -R"}, "cwd": cwd})
    assert run({"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": cwd}) is None


def test_write_over_big_file_denied_new_file_allowed(tmp_path):
    cwd = _files(tmp_path)
    assert run({"tool_name": "Write", "tool_input": {"file_path": "big.md", "content": "y"}, "cwd": cwd})
    assert run({"tool_name": "Write", "tool_input": {"file_path": "new.md", "content": "y"}, "cwd": cwd}) is None


def test_garbage_input_allows(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout == ""
