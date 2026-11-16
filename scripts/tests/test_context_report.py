import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import context_report as C


def _transcript(p: Path):
    lines = [
        {"type": "user", "message": {"role": "user", "content": "what's next?"}},
        {"type": "assistant", "message": {"model": "deepseek-v4-flash", "usage": {"input_tokens": 10000},
         "content": [{"type": "thinking", "thinking": "t" * 4000},
                     {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "/v/Big.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": "x" * 40000}]}},
        {"type": "assistant", "message": {"usage": {"input_tokens": 20500},
         "content": [{"type": "tool_use", "id": "b", "name": "Read", "input": {"file_path": "/v/Big.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "content": "x" * 400}]}},
        {"type": "system", "subtype": "compact_boundary"},
        {"type": "attachment", "attachment": {"type": "prompt_snapshot", "x": "z" * 99999}},
        {"type": "attachment", "attachment": {"type": "skill_listing", "x": "s" * 1000}},
        {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "text", "text": "q" * 99999}]}},
        {"type": "assistant", "message": {"usage": {"input_tokens": 9000}, "content": [{"type": "text", "text": "Done."}]}},
    ]
    p.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return p


def test_report_attributes_reads_jumps_and_repeats(tmp_path):
    out = "\n".join(C.report(_transcript(tmp_path / "s.jsonl"), 5))
    assert "compactions 1" in out and "deepseek-v4-flash" in out
    assert "10.0k  Read   /v/Big.md" in out
    assert "×2  /v/Big.md" in out
    assert "+ 10.5k  Read /v/Big.md" in out
    assert "skill_listing" in out and "prompt_snapshot" not in out
    assert "qqqq" not in out and "model replies (text)" in out
    assert "Most results are file reads" in out


def test_finds_latest_session_for_project(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    proj = tmp_path / "My Vault"
    proj.mkdir()
    import re
    d = tmp_path / "cfg/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(proj.resolve()))
    d.mkdir(parents=True)
    _transcript(d / "one.jsonl")
    assert C.sessions(proj) == [d / "one.jsonl"]
