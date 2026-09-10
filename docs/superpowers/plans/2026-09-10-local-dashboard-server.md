# Local Dashboard Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, `127.0.0.1`-only web dashboard (stdlib Python backend + vanilla JS
frontend) that shows the vault's GTD state on one no-scroll screen and lets the user complete,
create, edit, and delete tasks (and create projects) with the changes written straight to the
real `.md` files.

**Architecture:** Three focused Python modules (`dashboard_parser.py` reads vault state,
`dashboard_writer.py` performs safe exact-line-match writes, `dashboard_server.py` wires both into
an `http.server` HTTP API and serves the static frontend) plus a small static frontend split into
pure testable logic (`logic.js`) and thin DOM wiring (`app.js`).

**Tech Stack:** Python 3.9+ stdlib only (`http.server`, `pathlib`, `re`, `json`, `argparse`) —
zero installs. Frontend: vanilla JS, no build step, no framework. Tests: `pytest` (backend, already
used by this repo's `gtd-setup` tests) and Node's built-in `node:test` (frontend, zero installs —
this machine runs Node 22).

**Spec:** `docs/superpowers/specs/2026-09-10-local-dashboard-server-design.md`

## Global Constraints

- Stdlib-only Python, no `pip install` — matches `scripts/build_dashboard.py` and `gtd-setup`'s
  existing convention.
- The HTTP server binds to `"127.0.0.1"` only, **never** `"0.0.0.0"` or `""`.
- Every mutating operation re-reads its target file from disk immediately before writing, and
  matches the target line by **exact current text**, not a stored line number. A missing match
  raises `LineNotFoundError`; more than one match raises `AmbiguousLineError`. Both map to HTTP 409
  — the write must be refused, never applied to the wrong line.
- Reuse `scripts/build_dashboard.py`'s existing regexes/constants (`TASK_RE`, `TAG_RE`, `FIELD_RE`,
  `LINK_RE`, `_clean`, `CONTENT`, `CONTEXTS`) rather than redefining them — this is a DRY
  requirement, not a suggestion; those regexes are already correct and tested.
- Follow this repo's existing test-file convention: `scripts/tests/test_<module>.py`, importing the
  module under test via `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` (see
  `scripts/tests/test_build_dashboard.py` for the exact pattern).
- No real browser/DOM/E2E testing (would add an npm dependency this repo doesn't have) — frontend
  logic worth testing lives in dependency-free pure functions in `logic.js`, tested via
  `node --test`; `app.js`'s DOM wiring is verified manually in a real browser instead.
- The Obsidian `Dashboard.md`/QuickAdd setup from earlier this session is untouched by this plan —
  it keeps working independently as a fallback.

---

### Task 1: Vault state parser

**Files:**
- Create: `scripts/dashboard_parser.py`
- Test: `scripts/tests/test_dashboard_parser.py`

**Interfaces:**
- Produces: `iter_tasks_with_location(vault: Path) -> Iterator[dict]`, yielding
  `{"file": str, "line_text": str, "done": bool, "text": str, "tags": list[str], "fields": dict[str,str], "project": str | None}`
  per task checkbox line found under any of `build_dashboard.CONTENT`'s folders (README.md
  excluded). `file` is vault-relative with forward slashes. `project` is the containing file's
  stem when that file lives directly under `10 Projects/`, else `None`.
- Produces: `collect_state(vault: Path) -> dict` returning
  `{"inbox_count": int, "tasks_by_context": dict[str, list[dict]], "waiting": list[dict], "due_soon": list[dict], "active_projects": list[dict], "someday_projects": list[dict]}`.
  Task dicts in `tasks_by_context`/`due_soon` carry `{text, file, line_text, project, context, due}`
  (`due_soon` additionally carries `overdue: bool`); `waiting` dicts carry
  `{text, file, line_text, project, since}`. Project dicts carry
  `{name, file, review, review_overdue}` (active) or `{name, file}` (someday).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/tests/test_dashboard_parser.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_parser as P

def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "00 Inbox" / "loose.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-09\n---\n- [ ] loose item\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "README.md").write_text("# Projects\n")
    (vault / "10 Projects" / "Website Redesign.md").write_text(
        "---\ntype: project\nstatus: active\narea: \"[[Career]]\"\n"
        "created: 2026-09-01\nreview: 2026-09-15\n---\n"
        "# Website Redesign\n\n## Next actions\n"
        "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]\n"
        "- [x] Done already #next #computer\n\n"
        "## Waiting for\n"
        "- [ ] Logo files #waiting [[Design Agency]] [since:: 2026-09-05]\n")
    (vault / "10 Projects" / "Plan Family Trip.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: 2026-08-20\nreview: 2026-09-03\n---\n"
        "# Plan Family Trip\n\n## Next actions\n")
    (vault / "10 Projects" / "Learn Spanish.md").write_text(
        "---\ntype: project\nstatus: someday\ncreated: 2026-09-01\nreview: 2026-12-01\n---\n"
        "# Learn Spanish\n")

def test_iter_tasks_with_location_finds_file_and_exact_line(tmp_path):
    _mk_vault(tmp_path)
    tasks = list(P.iter_tasks_with_location(tmp_path))
    wireframe = next(t for t in tasks if "wireframe" in t["text"])
    assert wireframe["file"] == "10 Projects/Website Redesign.md"
    assert wireframe["line_text"] == "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]"
    assert wireframe["done"] is False
    assert wireframe["project"] == "Website Redesign"
    assert "#next" in wireframe["tags"] and "#computer" in wireframe["tags"]
    assert wireframe["fields"] == {"due": "2026-09-12"}
    done_task = next(t for t in tasks if t["text"] == "Done already")
    assert done_task["done"] is True
    inbox_task = next(t for t in tasks if t["text"] == "loose item")
    assert inbox_task["project"] is None
    assert inbox_task["file"] == "00 Inbox/loose.md"

def test_collect_state_counts_and_groups(tmp_path):
    _mk_vault(tmp_path)
    state = P.collect_state(tmp_path)
    assert state["inbox_count"] == 1
    assert len(state["tasks_by_context"]["#computer"]) == 1
    assert state["tasks_by_context"]["#computer"][0]["text"] == "Finalize homepage wireframe"
    assert len(state["waiting"]) == 1
    assert state["waiting"][0]["since"] == "2026-09-05"
    assert len(state["due_soon"]) == 1  # due 2026-09-12 is within 7 days of "today" in fixture-independent terms
    names = {p["name"] for p in state["active_projects"]}
    assert names == {"Website Redesign", "Plan Family Trip"}
    trip = next(p for p in state["active_projects"] if p["name"] == "Plan Family Trip")
    assert trip["review"] == "2026-09-03"
    assert trip["review_overdue"] is True  # 2026-09-03 is in the past relative to any real test run
    someday_names = {p["name"] for p in state["someday_projects"]}
    assert someday_names == {"Learn Spanish"}

def test_collect_state_on_empty_vault(tmp_path):
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "00 Inbox" / "README.md").write_text("# Inbox\n")
    state = P.collect_state(tmp_path)
    assert state["inbox_count"] == 0
    assert state["tasks_by_context"] == {}
    assert state["waiting"] == []
    assert state["active_projects"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_dashboard_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_parser'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/dashboard_parser.py
#!/usr/bin/env python3
"""Parse vault task/project state for the local dashboard server. stdlib only."""
from __future__ import annotations
import datetime as _dt
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard as BD


def iter_tasks_with_location(vault: Path):
    """Yield one dict per task checkbox line across all CONTENT folders (README excluded)."""
    vault = Path(vault)
    for d in BD.CONTENT:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            rel = str(p.relative_to(vault)).replace("\\", "/")
            for raw_line in p.read_text(encoding="utf-8").splitlines():
                m = BD.TASK_RE.match(raw_line)
                if not m:
                    continue
                body = m.group("b")
                tags = ["#" + t for t in BD.TAG_RE.findall(body)]
                fields = {k: v.strip() for k, v in BD.FIELD_RE.findall(body)}
                yield {
                    "file": rel,
                    "line_text": raw_line.rstrip(),
                    "done": m.group("m").lower() == "x",
                    "text": BD._clean(body),
                    "tags": tags,
                    "fields": fields,
                    "project": p.stem if d == "10 Projects" else None,
                }


def _project_frontmatter(p: Path) -> dict:
    text = p.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"')
    return fm


def collect_state(vault: Path) -> dict:
    vault = Path(vault)
    today = _dt.date.today()

    inbox_count = 0
    ib = vault / "00 Inbox"
    if ib.is_dir():
        inbox_count = len([p for p in ib.glob("*.md") if p.name != "README.md"])

    active_projects, someday_projects = [], []
    pj = vault / "10 Projects"
    if pj.is_dir():
        for p in sorted(pj.rglob("*.md")):
            if p.name == "README.md":
                continue
            fm = _project_frontmatter(p)
            status = fm.get("status", "")
            rel = str(p.relative_to(vault)).replace("\\", "/")
            if status == "active":
                review = fm.get("review")
                review_overdue = False
                if review:
                    try:
                        review_overdue = _dt.date.fromisoformat(review) <= today
                    except ValueError:
                        pass
                active_projects.append({
                    "name": p.stem, "file": rel, "review": review, "review_overdue": review_overdue,
                })
            elif status == "someday":
                someday_projects.append({"name": p.stem, "file": rel})

    tasks_by_context: dict[str, list[dict]] = {}
    waiting: list[dict] = []
    due_soon: list[dict] = []
    for t in iter_tasks_with_location(vault):
        if t["done"]:
            continue
        tags, fields = t["tags"], t["fields"]
        if "#waiting" in tags:
            waiting.append({
                "text": t["text"], "file": t["file"], "line_text": t["line_text"],
                "project": t["project"], "since": fields.get("since"),
            })
            continue
        if "#next" not in tags:
            continue
        sched = fields.get("scheduled")
        if sched:
            try:
                if _dt.date.fromisoformat(sched) > today:
                    continue
            except ValueError:
                pass
        ctx = next((c for c in BD.CONTEXTS if c in tags), "#anywhere")
        due = fields.get("due")
        entry = {
            "text": t["text"], "file": t["file"], "line_text": t["line_text"],
            "project": t["project"], "context": ctx, "due": due,
        }
        tasks_by_context.setdefault(ctx, []).append(entry)
        if due:
            try:
                due_date = _dt.date.fromisoformat(due)
                if due_date <= today + _dt.timedelta(days=7):
                    due_soon.append({**entry, "overdue": due_date < today})
            except ValueError:
                pass

    return {
        "inbox_count": inbox_count,
        "tasks_by_context": tasks_by_context,
        "waiting": waiting,
        "due_soon": due_soon,
        "active_projects": active_projects,
        "someday_projects": someday_projects,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_dashboard_parser.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard_parser.py scripts/tests/test_dashboard_parser.py
git commit -m "feat(dashboard): add vault state parser with per-line location tracking"
```

---

### Task 2: Safe write-back operations

**Files:**
- Create: `scripts/dashboard_writer.py`
- Test: `scripts/tests/test_dashboard_writer.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly, but is designed to be called with `(file, line_text)`
  pairs exactly as `dashboard_parser.iter_tasks_with_location`/`collect_state` produce them.
- Produces: `LineNotFoundError(Exception)`, `AmbiguousLineError(Exception)`.
- Produces: `complete_task(vault: Path, file: str, line_text: str) -> None`
- Produces: `delete_task(vault: Path, file: str, line_text: str) -> None`
- Produces: `edit_task(vault: Path, file: str, line_text: str, new_text: str | None = None, new_due: str | None = None) -> str`
  (returns the new line's text)
- Produces: `create_task(vault: Path, text: str, context: str, project: str | None = None) -> dict`
  returning `{"file": str, "line_text": str}`
- Produces: `create_project(vault: Path, title: str) -> str` returning the new file's vault-relative
  path

- [ ] **Step 1: Write the failing tests**

```python
# scripts/tests/test_dashboard_writer.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_writer as W
import pytest

def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# P\n\n## Next actions\n"
        "- [ ] Pick SSG #next #computer\n- [ ] Buy domain #next #computer\n")
    (vault / "10 Projects" / "NoHeading.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# NoHeading\n")
    (vault / "_templates").mkdir()
    (vault / "_templates" / "Project.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: {{date:YYYY-MM-DD}}\n"
        "review: {{date:YYYY-MM-DD}}\n---\n# {{title}}\n\n## Next actions\n")

def test_complete_task_flips_checkbox(tmp_path):
    _mk_vault(tmp_path)
    W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer")
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "- [x] Pick SSG #next #computer" in text
    assert "- [ ] Buy domain #next #computer" in text  # untouched

def test_complete_task_missing_line_raises(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(W.LineNotFoundError):
        W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] does not exist")

def test_complete_task_ambiguous_line_raises(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text() + "- [ ] Pick SSG #next #computer\n")  # duplicate the line
    with pytest.raises(W.AmbiguousLineError):
        W.complete_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer")

def test_delete_task_removes_the_line(tmp_path):
    _mk_vault(tmp_path)
    W.delete_task(tmp_path, "10 Projects/P.md", "- [ ] Buy domain #next #computer")
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "Buy domain" not in text
    assert "Pick SSG" in text

def test_edit_task_changes_text_and_preserves_tags(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Pick SSG #next #computer",
                            new_text="Pick a static site generator")
    assert new_line == "- [ ] Pick a static site generator #next #computer"
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "Pick a static site generator #next #computer" in text

def test_edit_task_sets_due_date(tmp_path):
    _mk_vault(tmp_path)
    new_line = W.edit_task(tmp_path, "10 Projects/P.md", "- [ ] Buy domain #next #computer",
                            new_due="2026-09-20")
    assert new_line == "- [ ] Buy domain #next #computer [due:: 2026-09-20]"

def test_edit_task_updates_existing_due_date(tmp_path):
    _mk_vault(tmp_path)
    p = tmp_path / "10 Projects" / "P.md"
    p.write_text(p.read_text().replace(
        "- [ ] Pick SSG #next #computer", "- [ ] Pick SSG #next #computer [due:: 2026-09-10]"))
    new_line = W.edit_task(tmp_path, "10 Projects/P.md",
                            "- [ ] Pick SSG #next #computer [due:: 2026-09-10]", new_due="2026-09-20")
    assert new_line == "- [ ] Pick SSG #next #computer [due:: 2026-09-20]"

def test_create_task_without_project_writes_one_file_to_inbox(tmp_path):
    _mk_vault(tmp_path)
    result = W.create_task(tmp_path, "Call the dentist", "phone")
    inbox_files = list((tmp_path / "00 Inbox").glob("*.md"))
    assert len(inbox_files) == 1
    assert result["file"] == "00 Inbox/" + inbox_files[0].name
    content = inbox_files[0].read_text()
    assert "type: inbox" in content
    assert "- [ ] Call the dentist #next #phone" in content
    assert result["line_text"] == "- [ ] Call the dentist #next #phone"

def test_create_task_with_project_inserts_under_next_actions(tmp_path):
    _mk_vault(tmp_path)
    result = W.create_task(tmp_path, "Ship v1", "computer", project="P")
    assert result["file"] == "10 Projects/P.md"
    text = (tmp_path / "10 Projects" / "P.md").read_text()
    assert "- [ ] Ship v1 #next #computer" in text

def test_create_task_with_project_creates_missing_heading(tmp_path):
    _mk_vault(tmp_path)
    W.create_task(tmp_path, "Do the thing", "anywhere", project="NoHeading")
    text = (tmp_path / "10 Projects" / "NoHeading.md").read_text()
    assert "## Next actions" in text
    assert "- [ ] Do the thing #next #anywhere" in text

def test_create_task_unknown_project_raises(tmp_path):
    _mk_vault(tmp_path)
    with pytest.raises(FileNotFoundError):
        W.create_task(tmp_path, "x", "computer", project="DoesNotExist")

def test_create_project_from_template(tmp_path):
    _mk_vault(tmp_path)
    rel = W.create_project(tmp_path, "New Idea")
    assert rel == "10 Projects/New Idea.md"
    text = (tmp_path / "10 Projects" / "New Idea.md").read_text()
    assert "# New Idea" in text
    assert "{{" not in text  # every template placeholder was substituted

def test_create_project_refuses_to_overwrite(tmp_path):
    _mk_vault(tmp_path)
    W.create_project(tmp_path, "New Idea")
    with pytest.raises(FileExistsError):
        W.create_project(tmp_path, "New Idea")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_dashboard_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_writer'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/dashboard_writer.py
#!/usr/bin/env python3
"""Write-back operations for the local dashboard server. stdlib only."""
from __future__ import annotations
import datetime as _dt
import re as _re
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard as BD


class LineNotFoundError(Exception):
    pass


class AmbiguousLineError(Exception):
    pass


def _find_line_index(lines: list[str], line_text: str) -> int:
    matches = [i for i, l in enumerate(lines) if l.rstrip() == line_text]
    if not matches:
        raise LineNotFoundError(f"line not found: {line_text!r}")
    if len(matches) > 1:
        raise AmbiguousLineError(f"line matched {len(matches)} times: {line_text!r}")
    return matches[0]


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def complete_task(vault: Path, file: str, line_text: str) -> None:
    path = Path(vault) / file
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    lines[i] = _re.sub(r"^(\s*-\s*\[)[ ](\].*)$", r"\1x\2", lines[i], count=1)
    _write_lines(path, lines)


def delete_task(vault: Path, file: str, line_text: str) -> None:
    path = Path(vault) / file
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    del lines[i]
    _write_lines(path, lines)


def edit_task(vault: Path, file: str, line_text: str,
               new_text: str | None = None, new_due: str | None = None) -> str:
    path = Path(vault) / file
    lines = _read_lines(path)
    i = _find_line_index(lines, line_text)
    m = _re.match(r"^(\s*-\s*\[[ xX]\]\s*)(.*)$", lines[i])
    prefix, body = m.group(1), m.group(2)

    tags = BD.TAG_RE.findall(body)
    fields = dict(BD.FIELD_RE.findall(body))
    links = BD.LINK_RE.findall(body)
    text = new_text.strip() if new_text is not None else BD._clean(body)

    if new_due is not None:
        fields["due"] = new_due

    parts = [text]
    parts += [f"#{t}" for t in tags]
    parts += [f"[{k}:: {v}]" for k, v in fields.items()]
    parts += [f"[[{l}]]" for l in links]
    new_body = " ".join(p for p in parts if p)
    lines[i] = prefix + new_body
    _write_lines(path, lines)
    return lines[i]


_SLUG_RE = _re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "item"


def create_task(vault: Path, text: str, context: str, project: str | None = None) -> dict:
    vault = Path(vault)
    today = _dt.date.today().isoformat()
    ctx = context if context.startswith("#") else f"#{context}"

    if not project:
        slug = _slugify(text)[:40]
        rel = f"00 Inbox/{today} {slug}.md"
        path = vault / rel
        n = 2
        while path.exists():
            rel = f"00 Inbox/{today} {slug}-{n}.md"
            path = vault / rel
            n += 1
        line_text = f"- [ ] {text} #next {ctx}"
        content = f"---\ntype: inbox\ncaptured: {today}\n---\n{line_text}\n"
        path.write_text(content, encoding="utf-8")
        return {"file": rel, "line_text": line_text}

    proj_path = vault / "10 Projects" / f"{project}.md"
    if not proj_path.is_file():
        raise FileNotFoundError(f"project not found: {project}")
    lines = _read_lines(proj_path)
    new_line = f"- [ ] {text} #next {ctx}"
    heading = "## Next actions"
    try:
        h_idx = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        lines = lines + ["", heading, "", new_line]
    else:
        insert_at = h_idx + 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
        j = insert_at
        while j < len(lines) and lines[j].lstrip().startswith("- ["):
            j += 1
        lines.insert(j, new_line)
    _write_lines(proj_path, lines)
    rel = str(proj_path.relative_to(vault)).replace("\\", "/")
    return {"file": rel, "line_text": new_line}


def create_project(vault: Path, title: str) -> str:
    vault = Path(vault)
    template = (vault / "_templates" / "Project.md").read_text(encoding="utf-8")
    today = _dt.date.today().isoformat()
    content = template.replace("{{title}}", title)
    content = _re.sub(r"\{\{date:YYYY-MM-DD\}\}", today, content)
    dest = vault / "10 Projects" / f"{title}.md"
    if dest.exists():
        raise FileExistsError(f"project already exists: {title}")
    dest.write_text(content, encoding="utf-8")
    return str(dest.relative_to(vault)).replace("\\", "/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_dashboard_writer.py -v`
Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard_writer.py scripts/tests/test_dashboard_writer.py
git commit -m "feat(dashboard): add safe exact-line-match write-back operations"
```

---

### Task 3: HTTP server — read endpoints and static file serving

**Files:**
- Create: `scripts/dashboard_server.py`
- Create: `scripts/dashboard_static/index.html` (minimal placeholder — Task 6 fills in the full UI; this task only needs a valid HTML file for the static-serving test to fetch)
- Test: `scripts/tests/test_dashboard_server.py`

**Interfaces:**
- Consumes: `dashboard_parser.collect_state` (Task 1).
- Produces: `make_handler(vault: Path) -> type[BaseHTTPRequestHandler]` — a handler class factory
  (needed because `BaseHTTPRequestHandler` takes no constructor args of its own; the vault path is
  captured via closure). Task 4 extends the same `Handler` class (adds `do_POST` branches) in the
  same file.
- Produces: `main(argv=None) -> int` — CLI entry point (`argparse`: positional `vault` default
  `"."`, `--port` default `8787`), starts a `ThreadingHTTPServer` bound to `"127.0.0.1"`.

- [ ] **Step 1: Write the placeholder static page**

```html
<!-- scripts/dashboard_static/index.html -->
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>GTD Dashboard</title></head>
<body><div id="board">Loading…</div></body>
</html>
```

- [ ] **Step 2: Write the failing tests**

```python
# scripts/tests/test_dashboard_server.py
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_server as S


def _mk_vault(vault: Path):
    (vault / "00 Inbox").mkdir(parents=True)
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n# P\n\n## Next actions\n"
        "- [ ] Pick SSG #next #computer\n")
    (vault / "_templates").mkdir()
    (vault / "_templates" / "Project.md").write_text(
        "---\ntype: project\nstatus: active\ncreated: {{date:YYYY-MM-DD}}\n"
        "review: {{date:YYYY-MM-DD}}\n---\n# {{title}}\n\n## Next actions\n")


def _start_server(vault: Path) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(vault))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_server_binds_localhost_only(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.shutdown()


def test_get_state_returns_current_tasks(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert any("Pick SSG" in t["text"] for t in data["tasks_by_context"]["#computer"])
    finally:
        server.shutdown()


def test_get_root_serves_index_html(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/") as r:
            assert r.status == 200
            assert r.headers["Content-Type"].startswith("text/html")
            body = r.read().decode()
        assert "<!doctype html>" in body.lower()
    finally:
        server.shutdown()


def test_get_unknown_path_returns_404(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        from urllib.error import HTTPError
        try:
            request.urlopen(f"http://127.0.0.1:{server.server_port}/nope")
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest scripts/tests/test_dashboard_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_server'`

- [ ] **Step 4: Write the implementation**

```python
# scripts/dashboard_server.py
#!/usr/bin/env python3
"""Local, 127.0.0.1-only dashboard server for the vault. stdlib only."""
from __future__ import annotations
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_parser as P
import dashboard_writer as W

STATIC_DIR = Path(__file__).resolve().parent / "dashboard_static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/logic.js": ("logic.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def make_handler(vault: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep test/console output quiet

        def _send_json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/state":
                self._send_json(P.collect_state(vault))
                return
            if path in STATIC_FILES:
                fname, ctype = STATIC_FILES[path]
                fpath = STATIC_DIR / fname
                if not fpath.is_file():
                    self._send_json({"error": "not found"}, 404)
                    return
                body = fpath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_json({"error": "not found"}, 404)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(vault))
    print(f"Dashboard server running at http://127.0.0.1:{a.port} (vault: {vault})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest scripts/tests/test_dashboard_server.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/dashboard_server.py scripts/dashboard_static/index.html scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): add HTTP server with /api/state and static file serving"
```

---

### Task 4: HTTP server — write endpoints

**Files:**
- Modify: `scripts/dashboard_server.py` (add `do_POST` to the `Handler` class from Task 3)
- Modify: `scripts/tests/test_dashboard_server.py` (append tests)

**Interfaces:**
- Consumes: `dashboard_writer.{complete_task, delete_task, edit_task, create_task, create_project, LineNotFoundError, AmbiguousLineError}`
  (Task 2), `Handler` class and `_send_json`/`_read_json` helpers (Task 3).
- Produces: `POST /api/complete-task`, `/api/delete-task`, `/api/edit-task`, `/api/new-task`,
  `/api/new-project` — each returns `{"ok": true, ...}` with HTTP 200 on success; `LineNotFoundError`/
  `AmbiguousLineError`/`FileExistsError` → HTTP 409 `{"error": "..."}`; `FileNotFoundError` → HTTP
  404; a missing required JSON field (`KeyError`) → HTTP 400.

- [ ] **Step 1: Write the failing tests**

```python
# append to scripts/tests/test_dashboard_server.py
from urllib.error import HTTPError


def _post(server, path, payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(f"http://127.0.0.1:{server.server_port}{path}", data=body,
                           method="POST", headers={"Content-Type": "application/json"})
    return request.urlopen(req)


def test_complete_task_writes_the_file(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/complete-task",
                    {"file": "10 Projects/P.md", "line_text": "- [ ] Pick SSG #next #computer"}) as r:
            assert r.status == 200
        text = (tmp_path / "10 Projects" / "P.md").read_text()
        assert "- [x] Pick SSG #next #computer" in text
    finally:
        server.shutdown()


def test_complete_task_conflict_when_line_missing(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/complete-task", {"file": "10 Projects/P.md", "line_text": "- [ ] nope"})
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 409
    finally:
        server.shutdown()


def test_new_task_without_project_creates_inbox_file(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/new-task", {"text": "Call dentist", "context": "phone"}) as r:
            data = json.loads(r.read())
        assert data["file"].startswith("00 Inbox/")
        assert (tmp_path / data["file"]).is_file()
    finally:
        server.shutdown()


def test_new_project_creates_from_template(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with _post(server, "/api/new-project", {"title": "New Idea"}) as r:
            data = json.loads(r.read())
        assert data["file"] == "10 Projects/New Idea.md"
        assert (tmp_path / "10 Projects" / "New Idea.md").is_file()
    finally:
        server.shutdown()


def test_delete_task_missing_required_field_is_bad_request(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        try:
            _post(server, "/api/delete-task", {"file": "10 Projects/P.md"})  # no line_text
            assert False, "expected HTTPError"
        except HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_dashboard_server.py -v`
Expected: FAIL — the new `test_complete_task_writes_the_file` etc. fail with 404/`Connection refused`-style errors (no `do_POST` handler exists yet)

- [ ] **Step 3: Add `do_POST` to the implementation**

First, add the missing import at the top of `scripts/dashboard_server.py`, directly below the
existing `import dashboard_parser as P` line:

```python
import dashboard_writer as W
```

Then add `do_POST` inside `class Handler`, directly after the existing `do_GET` method:

```python
# add inside class Handler in scripts/dashboard_server.py, after do_GET:
        def do_POST(self):
            path = urlparse(self.path).path
            try:
                data = self._read_json()
                if path == "/api/complete-task":
                    W.complete_task(vault, data["file"], data["line_text"])
                    self._send_json({"ok": True})
                elif path == "/api/delete-task":
                    W.delete_task(vault, data["file"], data["line_text"])
                    self._send_json({"ok": True})
                elif path == "/api/edit-task":
                    new_line = W.edit_task(vault, data["file"], data["line_text"],
                                            data.get("new_text"), data.get("new_due"))
                    self._send_json({"ok": True, "line_text": new_line})
                elif path == "/api/new-task":
                    result = W.create_task(vault, data["text"], data.get("context", "anywhere"),
                                            data.get("project"))
                    self._send_json({"ok": True, **result})
                elif path == "/api/new-project":
                    rel = W.create_project(vault, data["title"])
                    self._send_json({"ok": True, "file": rel})
                else:
                    self._send_json({"error": "not found"}, 404)
            except (W.LineNotFoundError, W.AmbiguousLineError, FileExistsError) as e:
                self._send_json({"error": str(e)}, 409)
            except FileNotFoundError as e:
                self._send_json({"error": str(e)}, 404)
            except KeyError as e:
                self._send_json({"error": f"missing field: {e}"}, 400)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_dashboard_server.py -v`
Expected: all 9 tests PASS (4 from Task 3 + 5 new)

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard_server.py scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): add write endpoints (complete/edit/delete task, new task/project)"
```

---

### Task 5: Frontend pure logic (filtering, rendering, overdue calculation)

**Files:**
- Create: `scripts/dashboard_static/logic.js`
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Consumes: the exact JSON shape `dashboard_parser.collect_state` produces (Task 1) — this module
  never fetches; it's called with that object already parsed.
- Produces (exported both as CommonJS `module.exports` for Node tests and as `window.DashboardLogic`
  for the browser): `escapeHtml(s) -> string`, `isOverdue(dateStr, today?) -> boolean`,
  `filterTasks(tasks, query) -> array`, `render(state, query, today) -> {kpis, tasksHtml, dueSoonHtml, waitingHtml, projectsHtml, somedayHtml}`
  where `kpis = {inbox, tasks, waiting, due}` (numbers) and the `*Html` fields are strings meant
  for `element.innerHTML =`. Task 6's `app.js` calls exactly this `render` signature.

- [ ] **Step 1: Write the failing tests**

```js
// scripts/dashboard_static/logic.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("./logic.js");

test("escapeHtml escapes the five XSS-relevant characters", () => {
  assert.equal(L.escapeHtml(`<a href="x">&'</a>`),
    "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
});

test("escapeHtml handles null/undefined safely", () => {
  assert.equal(L.escapeHtml(null), "");
  assert.equal(L.escapeHtml(undefined), "");
});

test("isOverdue is true only for a date strictly before today", () => {
  assert.equal(L.isOverdue("2026-09-01", "2026-09-10"), true);
  assert.equal(L.isOverdue("2026-09-10", "2026-09-10"), false);
  assert.equal(L.isOverdue("2026-09-11", "2026-09-10"), false);
  assert.equal(L.isOverdue(null, "2026-09-10"), false);
});

test("filterTasks matches text, project, or context case-insensitively", () => {
  const tasks = [
    { text: "Finalize homepage wireframe", project: "Website Redesign", context: "#computer" },
    { text: "Call hosting provider", project: "Website Redesign", context: "#phone" },
    { text: "Order flight", project: "Plan Family Trip", context: "#anywhere" },
  ];
  assert.equal(L.filterTasks(tasks, "").length, 3);
  assert.equal(L.filterTasks(tasks, "flight").length, 1);
  assert.equal(L.filterTasks(tasks, "WEBSITE").length, 2);
  assert.equal(L.filterTasks(tasks, "phone").length, 1);
});

test("render produces correct KPI counts for a populated state", () => {
  const state = {
    inbox_count: 2,
    tasks_by_context: {
      "#computer": [{ text: "Finalize homepage wireframe", file: "f.md",
        line_text: "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]",
        project: "Website Redesign", due: "2026-09-12" }],
      "#phone": [{ text: "Call hosting provider", file: "f.md",
        line_text: "- [ ] Call hosting provider #next #phone", project: "Website Redesign" }],
    },
    waiting: [{ text: "Logo files", file: "f.md", line_text: "- [ ] Logo files #waiting" }],
    due_soon: [{ text: "Finalize homepage wireframe", file: "f.md",
      line_text: "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]",
      due: "2026-09-12" }],
    active_projects: [{ name: "Website Redesign", file: "10 Projects/Website Redesign.md",
      review: "2026-09-15", review_overdue: false }],
    someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.deepEqual(out.kpis, { inbox: 2, tasks: 2, waiting: 1, due: 1 });
  assert.match(out.tasksHtml, /Finalize homepage wireframe/);
  assert.match(out.projectsHtml, /Website Redesign/);
  assert.equal(out.somedayHtml, '<p class="empty">None.</p>');
});

test("render escapes task text (no raw HTML injection)", () => {
  const state = {
    inbox_count: 0,
    tasks_by_context: { "#computer": [{ text: '<img src=x onerror=alert(1)>', file: "f.md",
      line_text: "x", project: null }] },
    waiting: [], due_soon: [], active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.doesNotMatch(out.tasksHtml, /<img/);
  assert.match(out.tasksHtml, /&lt;img/);
});

test("render respects the search query across sections", () => {
  const state = {
    inbox_count: 0,
    tasks_by_context: {
      "#computer": [{ text: "Finalize homepage wireframe", file: "f.md", line_text: "x",
        project: "Website Redesign" }],
      "#phone": [{ text: "Call hosting provider", file: "f.md", line_text: "y",
        project: "Website Redesign" }],
    },
    waiting: [], due_soon: [], active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "hosting", "2026-09-10");
  assert.doesNotMatch(out.tasksHtml, /Finalize/);
  assert.match(out.tasksHtml, /Call hosting provider/);
});

test("render marks an overdue due date distinctly from a future one", () => {
  const state = {
    inbox_count: 0, tasks_by_context: {}, waiting: [],
    due_soon: [
      { text: "Late one", file: "f.md", line_text: "x", due: "2026-09-01" },
      { text: "On time", file: "f.md", line_text: "y", due: "2026-09-14" },
    ],
    active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.match(out.dueSoonHtml, /class="due overdue"/);
  assert.match(out.dueSoonHtml, /class="due">/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: FAIL — `Cannot find module './logic.js'`

- [ ] **Step 3: Write the implementation**

```js
// scripts/dashboard_static/logic.js
// Pure rendering/filtering logic for the local dashboard. No DOM, no fetch —
// runs identically under Node's test runner and in the browser.
(function (root) {
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function isOverdue(dateStr, today) {
    if (!dateStr) return false;
    var d = new Date(dateStr + "T00:00:00");
    var t = today ? new Date(today + "T00:00:00") : new Date();
    t.setHours(0, 0, 0, 0);
    return d < t;
  }

  function filterTasks(tasks, query) {
    if (!query) return tasks;
    var q = query.toLowerCase();
    return tasks.filter(function (t) {
      return (t.text || "").toLowerCase().indexOf(q) !== -1 ||
        (t.project || "").toLowerCase().indexOf(q) !== -1 ||
        (t.context || "").toLowerCase().indexOf(q) !== -1;
    });
  }

  function taskLine(t, today) {
    var due = t.due
      ? '<span class="due' + (isOverdue(t.due, today) ? " overdue" : "") + '">' +
        escapeHtml(t.due) + "</span>"
      : "";
    var proj = t.project ? '<span class="proj">' + escapeHtml(t.project) + "</span>" : "";
    return '<li class="task" data-file="' + escapeHtml(t.file) + '" data-line="' +
      escapeHtml(t.line_text) + '">' +
      '<input type="checkbox" class="task-check">' +
      '<span class="task-text" contenteditable="true">' + escapeHtml(t.text) + "</span>" +
      proj + due +
      '<button class="task-delete" title="Delete">×</button>' +
      "</li>";
  }

  function renderTasksByContext(tasksByContext, query, today) {
    var ctxOrder = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"];
    var html = "";
    ctxOrder.forEach(function (ctx) {
      var items = filterTasks(tasksByContext[ctx] || [], query);
      if (!items.length) return;
      html += '<div class="ctx-col"><div class="ctx-h">' + escapeHtml(ctx.slice(1)) +
        " (" + items.length + ')</div><ul class="task-list">' +
        items.map(function (t) { return taskLine(t, today); }).join("") + "</ul></div>";
    });
    return html || '<p class="empty">No tasks.</p>';
  }

  function renderSimpleList(items, today) {
    if (!items.length) return '<p class="empty">Nothing here.</p>';
    return '<ul class="task-list">' +
      items.map(function (t) { return taskLine(t, today); }).join("") + "</ul>";
  }

  function renderProjects(projects) {
    if (!projects.length) return '<p class="empty">None.</p>';
    return "<ul>" + projects.map(function (p) {
      var pill = p.review_overdue
        ? '<span class="pill overdue">review overdue</span>'
        : (p.review ? '<span class="pill">review ' + escapeHtml(p.review) + "</span>" : "");
      return '<li><a href="obsidian://open?path=' + encodeURIComponent(p.file) + '">' +
        escapeHtml(p.name) + "</a>" + pill + "</li>";
    }).join("") + "</ul>";
  }

  function render(state, query, today) {
    var totalTasks = Object.keys(state.tasks_by_context || {}).reduce(function (n, k) {
      return n + state.tasks_by_context[k].length;
    }, 0);
    return {
      kpis: {
        inbox: state.inbox_count,
        tasks: totalTasks,
        waiting: (state.waiting || []).length,
        due: (state.due_soon || []).length,
      },
      tasksHtml: renderTasksByContext(state.tasks_by_context || {}, query, today),
      dueSoonHtml: renderSimpleList(state.due_soon || [], today),
      waitingHtml: renderSimpleList(state.waiting || [], today),
      projectsHtml: renderProjects(state.active_projects || []),
      somedayHtml: renderProjects(state.someday_projects || []),
    };
  }

  var api = { escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DashboardLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard_static/logic.js scripts/dashboard_static/logic.test.js
git commit -m "feat(dashboard): add pure frontend rendering/filtering logic with tests"
```

---

### Task 6: Frontend page, DOM wiring, and styling

**Files:**
- Modify: `scripts/dashboard_static/index.html` (replace Task 3's placeholder with the full page)
- Create: `scripts/dashboard_static/app.js`
- Create: `scripts/dashboard_static/style.css`

**Interfaces:**
- Consumes: `DashboardLogic.render(state, query, today)` (Task 5, loaded as a global via
  `<script src="logic.js">`), the API endpoints from Tasks 3-4 (`GET /api/state`,
  `POST /api/complete-task`, `/api/delete-task`, `/api/edit-task`, `/api/new-task`).
- Produces: nothing consumed by a later task — this is the outermost layer.

This task is **not unit-testable** (DOM wiring, `fetch`, `setInterval`, `localStorage` — see the
plan's Global Constraints on why real browser/E2E testing is out of scope). Its correctness is
verified manually in Step 3.

- [ ] **Step 1: Write the full page**

```html
<!-- scripts/dashboard_static/index.html -->
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GTD Dashboard</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div id="board">
  <header>
    <h1>GTD Dashboard</h1>
    <div class="kpis" id="kpis"></div>
    <div class="toolbar">
      <input id="search" type="text" placeholder="Search tasks... (press / to focus, n for new task)">
      <button id="theme-toggle" type="button" title="Toggle light/dark">Theme</button>
    </div>
  </header>
  <main class="grid">
    <section class="card span2"><h2>Tasks</h2><div id="tasks"></div></section>
    <section class="card"><h2>Due soon</h2><div id="due-soon"></div></section>
    <section class="card"><h2>Waiting for</h2><div id="waiting"></div></section>
    <section class="card"><h2>Active projects</h2><div id="projects"></div></section>
    <section class="card"><h2>Someday / Maybe</h2><div id="someday"></div></section>
  </main>
</div>
<div id="quick-add" class="modal hidden">
  <form id="quick-add-form">
    <input id="quick-add-text" type="text" placeholder="Task text" autocomplete="off">
    <select id="quick-add-context">
      <option value="computer">computer</option>
      <option value="phone">phone</option>
      <option value="errands">errands</option>
      <option value="home">home</option>
      <option value="office">office</option>
      <option value="anywhere">anywhere</option>
      <option value="agenda">agenda</option>
    </select>
    <input id="quick-add-project" type="text" placeholder="Project (optional)" autocomplete="off">
    <button type="submit">Add task</button>
  </form>
</div>
<script src="logic.js"></script>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `app.js` and `style.css`**

```js
// scripts/dashboard_static/app.js
(function () {
  var POLL_MS = 4000;
  var state = null;
  var query = "";

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("dashboard-theme", theme);
  }

  function renderAll() {
    if (!state) return;
    var out = DashboardLogic.render(state, query, today());
    document.getElementById("kpis").innerHTML =
      ["inbox", "tasks", "waiting", "due"].map(function (k) {
        return '<div class="kpi"><b>' + out.kpis[k] + "</b><div>" + k + "</div></div>";
      }).join("");
    document.getElementById("tasks").innerHTML = out.tasksHtml;
    document.getElementById("due-soon").innerHTML = out.dueSoonHtml;
    document.getElementById("waiting").innerHTML = out.waitingHtml;
    document.getElementById("projects").innerHTML = out.projectsHtml;
    document.getElementById("someday").innerHTML = out.somedayHtml;
  }

  function refresh() {
    fetch("/api/state").then(function (r) { return r.json(); }).then(function (data) {
      state = data;
      renderAll();
    });
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error("request failed: " + r.status);
      return r.json();
    });
  }

  document.addEventListener("click", function (e) {
    var li = e.target.closest(".task");
    if (!li) return;
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    if (e.target.classList.contains("task-check")) {
      post("/api/complete-task", { file: file, line_text: line }).then(refresh);
    } else if (e.target.classList.contains("task-delete")) {
      post("/api/delete-task", { file: file, line_text: line }).then(refresh);
    }
  });

  document.addEventListener("focusout", function (e) {
    if (!e.target.classList || !e.target.classList.contains("task-text")) return;
    var li = e.target.closest(".task");
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    var newText = e.target.textContent.trim();
    if (!newText) return;
    post("/api/edit-task", { file: file, line_text: line, new_text: newText }).then(refresh);
  });

  document.getElementById("search").addEventListener("input", function (e) {
    query = e.target.value;
    renderAll();
  });

  document.getElementById("theme-toggle").addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "light" ? "dark" : "light");
  });

  var modal = document.getElementById("quick-add");
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    if (e.key === "/") {
      e.preventDefault();
      document.getElementById("search").focus();
    } else if (e.key === "n") {
      e.preventDefault();
      modal.classList.remove("hidden");
      document.getElementById("quick-add-text").focus();
    } else if (e.key === "Escape") {
      modal.classList.add("hidden");
    }
  });

  document.getElementById("quick-add-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var text = document.getElementById("quick-add-text").value.trim();
    if (!text) return;
    var context = document.getElementById("quick-add-context").value;
    var project = document.getElementById("quick-add-project").value.trim() || undefined;
    post("/api/new-task", { text: text, context: context, project: project }).then(function () {
      document.getElementById("quick-add-text").value = "";
      document.getElementById("quick-add-project").value = "";
      modal.classList.add("hidden");
      refresh();
    });
  });

  applyTheme(localStorage.getItem("dashboard-theme") || "light");
  refresh();
  setInterval(refresh, POLL_MS);
})();
```

```css
/* scripts/dashboard_static/style.css */
:root {
  --bg: #fafafa; --card-bg: #fff; --border: #e2e2e2; --text: #1a1a1a; --muted: #6b6b74;
  --accent: #4c8dff; --red: #e5534b; --green: #2ea043;
}
html[data-theme="dark"] {
  --bg: #1b1b1e; --card-bg: #26262a; --border: #3a3a40; --text: #e8e8ea; --muted: #9a9aa2;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; overflow: hidden; }
body {
  font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text);
  display: flex; flex-direction: column; padding: 12px 16px;
}
header { flex: 0 0 auto; }
h1 { font-size: 1.1rem; margin: 0 0 8px; }
.kpis { display: flex; gap: 8px; margin-bottom: 8px; }
.kpis .kpi {
  flex: 1; border: 1px solid var(--border); border-radius: 10px; padding: 6px 10px;
  text-align: center; background: var(--card-bg);
}
.toolbar { display: flex; gap: 8px; margin-bottom: 8px; }
.toolbar input {
  flex: 1; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--card-bg); color: var(--text);
}
.grid {
  flex: 1 1 auto; min-height: 0; display: grid;
  grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(2, 1fr); gap: 10px;
}
.card {
  border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; background: var(--card-bg);
  min-height: 0; overflow: hidden; display: flex; flex-direction: column;
}
.card > div { overflow: auto; }
.card h2 {
  font-size: 0.85rem; margin: 0 0 6px; border-bottom: 1px solid var(--border); padding-bottom: 4px;
}
.card.span2 { grid-column: span 2; }
.task-list { list-style: none; margin: 0; padding: 0; font-size: 0.85rem; }
.task-list li { display: flex; align-items: center; gap: 6px; padding: 3px 0; border-bottom: 1px solid var(--border); }
.task-text { flex: 1; }
.proj { color: var(--accent); font-size: 0.75rem; }
.due { font-size: 0.75rem; color: var(--muted); }
.due.overdue { color: var(--red); font-weight: 600; }
.task-delete { border: none; background: none; color: var(--muted); cursor: pointer; font-size: 1rem; }
.pill {
  font-size: 0.68rem; padding: 1px 7px; border-radius: 999px;
  background: var(--border); color: var(--muted); margin-left: 6px;
}
.pill.overdue { background: rgba(229,83,75,0.18); color: var(--red); }
.empty { color: var(--muted); font-style: italic; font-size: 0.85rem; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; }
.modal.hidden { display: none; }
.modal form { background: var(--card-bg); border-radius: 10px; padding: 16px; display: flex; gap: 8px; }
```

- [ ] **Step 3: Manual browser verification**

Run `python scripts/dashboard_server.py <path to a real or test vault>`, open
`http://localhost:8787`, and confirm:
- The page loads with no scrollbar on a normal laptop screen at the vault's current data size.
- KPI numbers match what `/api/state` returns (compare against `curl http://localhost:8787/api/state`).
- Checking a task's checkbox removes it from the list and the underlying `.md` file shows `[x]`.
- Clicking a task's delete button removes the line from its file.
- Clicking into a task's text, editing it, and clicking away writes the new text back (tags/due
  date preserved).
- Pressing `n` anywhere (outside an input) opens the quick-add modal; submitting it creates a task
  (inbox file if no project given, inserted under "## Next actions" if a project name is given).
- Pressing `/` focuses the search box; typing filters the Tasks card.
- Clicking the theme button toggles light/dark and survives a page reload.
- Editing a task directly in Obsidian, then waiting ~4 seconds, shows the change on the dashboard
  without a manual reload.

- [ ] **Step 4: Commit**

```bash
git add scripts/dashboard_static/index.html scripts/dashboard_static/app.js scripts/dashboard_static/style.css
git commit -m "feat(dashboard): add frontend page, DOM wiring, and styling"
```

---

### Task 7: Documentation

**Files:**
- Create: `docs/gtd/local-dashboard.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing (documentation only).

- [ ] **Step 1: Write the doc**

```markdown
<!-- docs/gtd/local-dashboard.md -->
# Local dashboard server

A second, independent way to view and edit this vault's GTD state — a plain browser page instead
of Obsidian. Complements (doesn't replace) `Dashboard.md` + QuickAdd in Obsidian, which keeps
working on its own.

## Run it

```
python scripts/dashboard_server.py            # serves the repo root as the vault, port 8787
python scripts/dashboard_server.py /path/to/vault --port 9000
```

Leave that process running and open `http://localhost:8787` (or your chosen port) in a browser
tab. It's local-only — the server binds to `127.0.0.1`, so nothing outside your machine can reach
it, and there's no login because there's nothing to log into.

## What it does

- Shows inbox size, tasks (grouped by context), due-soon, waiting-for, active projects, and
  someday/maybe on one no-scroll screen.
- Checking a task's box, editing its text or due date, or deleting it writes straight to the real
  `.md` file — Obsidian and the browser page never disagree, because there's only ever one copy of
  the data.
- "New task" (press `n` or use the form) captures to `00 Inbox/` if you don't pick a project, or
  inserts under that project's `## Next actions` heading if you do — matching `/gtd-capture`'s and
  QuickAdd's conventions.
- Auto-refreshes every ~4 seconds, so edits made directly in Obsidian show up here too.

## Safety model

Every write re-reads its target file immediately before editing and matches the exact line of text
it's changing — never a stored line number, which could point at the wrong line if the file changed
in between. If that exact line isn't there anymore (you edited it elsewhere in the last few
seconds), the write is refused rather than applied to the wrong line; the page just re-fetches
current state on its next poll.
```

- [ ] **Step 2: Update the README feature table**

Find the "Live dashboard" row in `README.md`'s features table and add a line directly below it:

```
| Local browser dashboard | `scripts/dashboard_server.py` — a second, independent live view with full task CRUD, no Obsidian required. See `docs/gtd/local-dashboard.md`. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/gtd/local-dashboard.md README.md
git commit -m "docs: document the local dashboard server"
```

---

## Self-Review Notes

- **Spec coverage:** every "Views"/"Task actions"/"Project actions"/"Live behavior" item from the
  spec maps to Task 5/6 (rendering) + Task 3/4 (API); write-back safety (exact-line-match,
  re-read-before-write) is Task 2, tested explicitly for both the missing-line and duplicate-line
  failure modes; the DRY requirement (reuse `build_dashboard.py`'s regexes) is honored in both
  Task 1 and Task 2 via `import build_dashboard as BD`; the stdlib-only / `127.0.0.1`-only
  constraints are enforced in Task 3 and verified by `test_server_binds_localhost_only`; the
  testing-approach section (pytest backend, `node:test` frontend, no browser E2E) is exactly what
  Tasks 1-2-3-4 (pytest) and Task 5 (`node --test`) implement, with Task 6 explicitly called out as
  manually-verified instead.
- **Deviation from spec, called out explicitly:** the spec's example server code combined GET and
  POST handling in one description; the plan splits them into Task 3 (GET + static) and Task 4
  (POST) for reviewable task size, both modifying the same `Handler` class — consistent with how
  earlier plans in this session (QuickAdd) let sequential tasks build on the same file.
- **Type/name consistency:** `dashboard_parser.collect_state`'s return shape (keys:
  `inbox_count`, `tasks_by_context`, `waiting`, `due_soon`, `active_projects`, `someday_projects`)
  is used identically by `dashboard_server.py`'s `/api/state` handler (Task 3), and
  `logic.js`'s `render(state, ...)` (Task 5) reads exactly those same key names — verified by
  re-reading Task 5's test fixtures against Task 1's actual field names. `dashboard_writer`'s
  function signatures (`complete_task(vault, file, line_text)`, `edit_task(vault, file, line_text, new_text=None, new_due=None)`,
  `create_task(vault, text, context, project=None)`, `create_project(vault, title)`) match exactly
  between Task 2's definitions and Task 4's `do_POST` call sites.
