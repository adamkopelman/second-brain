# GTD Second Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `second-brain` repo into a working, harness-portable GTD second brain — an Obsidian vault operated by any skills+MCP agent (Claude Code, opencode, …) — covering a setup skill, the GTD workflow skills, two dashboards, cross-harness wiring, and an Outlook MCP integration.

**Architecture:** Plain-markdown Obsidian vault at the repo root. GTD *location* = PARA-style folders; GTD *state* = tags + Dataview inline fields inside task checkboxes. **Skills are the interface** and live in `.claude/skills/` (discovered by Claude Code *and* opencode). A `gtd-setup` skill is the single source of truth for the scaffold (idempotent copier over a bundled asset tree); the committed vault is its output. Portable static `dashboard.html` (stdlib script) is the shareable dashboard; `Dashboard.md` (Dataview) is the in-Obsidian live view. The user's `outlook-mcp-rs` server is wired for both harnesses. Anything a harness would "do by default" (the session brief) is a skill first; the Claude Code `SessionStart` hook is only an optional auto-trigger.

**Tech Stack:** Markdown, Obsidian (+ Dataview), Python 3 (stdlib + `pytest`) for the setup copier and dashboard generator, Bash for the optional hook, MCP (`.mcp.json` + `opencode.json`), `outlook-mcp-rs`.

**Spec:** `docs/superpowers/specs/2026-09-09-gtd-second-brain.md`

## Global Constraints

- **Vault root = repo root.** All content folders at top level.
- **Folders (verbatim):** `00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`, `40 Archive`, `Journal`, `People`, `Meetings`, `_templates`.
- **Context tags (exact):** `#computer` `#phone` `#errands` `#home` `#office` `#anywhere` `#agenda`.
- **Status tags (exact):** `#next` `#waiting` `#someday`.
- **Inline fields (exact):** `[due:: YYYY-MM-DD]`, `[scheduled:: YYYY-MM-DD]`, `[since:: YYYY-MM-DD]`.
- **Project frontmatter (exact):** `type: project`, `status: active|someday|done`, `area`, `created`, `review`.
- **Skills:** `.claude/skills/<name>/SKILL.md`; frontmatter is exactly `name` + `description`; `name` == directory, kebab-case, `gtd-` prefixed. **No skill may require a Claude-Code-only capability to function** (portability). Do not modify the vendored Superpowers skills.
- **Portability rule:** any behavior a harness performs automatically must exist as an invokable skill; harness-specific config (hooks, `.mcp.json`) may only *trigger* skills/logic, never be the sole path.
- **Dates:** `YYYY-MM-DD`, real current date at execution.
- **Read-only means read-only:** `gtd-status`, `gtd-next-actions`, `gtd-dashboard`, the hook, and `build_dashboard.py` must not modify vault notes.
- **Python:** standard library only (no pip installs); target 3.9+.
- **Secrets:** none committed. The Outlook MCP binary path comes from an environment variable.
- **Prerequisite (done):** Superpowers installed at `.claude/skills/` (commit `b9f9264`). Build on it.
- **Commits:** one per task, prefixed `feat:`/`docs:`/`test:`/`chore:`. Branch `claude/superpowers-skills-beuh67`.

---

## File Structure

```
# Setup skill = source of truth for the scaffold
.claude/skills/gtd-setup/SKILL.md                     (Task 2)
.claude/skills/gtd-setup/apply.py                      (Task 1)
.claude/skills/gtd-setup/tests/test_apply.py           (Task 1)
.claude/skills/gtd-setup/scaffold/vault/**             (Task 1 — asset tree, bodies in Appendix A)

# Materialized vault (output of running apply.py at repo root — Task 3)
00 Inbox/README.md  10 Projects/README.md  20 Areas/README.md  30 Resources/README.md
40 Archive/README.md  Journal/README.md  People/README.md  Meetings/README.md
30 Resources/GTD System.md   _templates/{Project,Daily Note,Person,Meeting,Weekly Review}.md
Dashboard.md   Weekly Review.md   .obsidian/{app,core-plugins,templates,daily-notes,community-plugins}.json
.gitignore

# GTD workflow skills
.claude/skills/gtd-capture/SKILL.md                    (Task 4)
.claude/skills/gtd-process-inbox/SKILL.md              (Task 5)
.claude/skills/gtd-next-actions/SKILL.md               (Task 6)
.claude/skills/gtd-weekly-review/SKILL.md              (Task 7)
.claude/skills/gtd-status/SKILL.md                     (Task 8)

# Dashboards
scripts/build_dashboard.py                             (Task 9)
scripts/tests/test_build_dashboard.py                  (Task 9)
.claude/skills/gtd-dashboard/SKILL.md                  (Task 10)

# Cross-harness wiring
.mcp.json                                              (Task 11)
opencode.json                                          (Task 11)
.claude/hooks/gtd-status.sh                            (Task 12)
.claude/hooks/test_gtd-status.sh                       (Task 12)
.claude/settings.json                                  (Task 12)
AGENTS.md                                              (Task 13)

# Outlook integration
.claude/skills/gtd-outlook/SKILL.md                    (Task 14)
docs/gtd/outlook.md                                    (Task 15)

# Docs
docs/gtd/obsidian-plugins.md                           (Task 16)
docs/gtd/portability.md                                (Task 17)
docs/gtd/html-dashboard.md                             (Task 17)
README.md                                              (Task 18 — rewrite)

# Optional (Phase 6)
.claude/skills/gtd-maintain/SKILL.md                   (Task 19 — optional)
```

---

## Phase 0 — Setup skill & scaffold (single source of truth)

### Task 1: `gtd-setup` scaffolder (`apply.py`) + asset tree + tests

**Files:**
- Create: `.claude/skills/gtd-setup/apply.py`, `.claude/skills/gtd-setup/tests/test_apply.py`, and the asset tree `.claude/skills/gtd-setup/scaffold/vault/**` (all files listed under "Materialized vault" above, with bodies from **Appendix A**).

**Interfaces:**
- Produces: `apply.py` — CLI `python3 apply.py <target_dir> [--force]`. Walks `scaffold/vault/`, and for each asset copies it to `<target_dir>/<relpath>`, **creating parent dirs and only writing when the destination does not exist** (unless `--force`). Prints one line per file: `created <relpath>` or `skipped <relpath>`. Exit 0. Also exposes `apply(scaffold_root: Path, target: Path, force: bool=False) -> dict` returning `{"created": [...], "skipped": [...]}`.

- [ ] **Step 1: Create the asset tree** `.claude/skills/gtd-setup/scaffold/vault/` with every file body in **Appendix A** at its stated path (e.g. `scaffold/vault/00 Inbox/README.md`, `scaffold/vault/30 Resources/GTD System.md`, `scaffold/vault/.obsidian/app.json`, etc.).

- [ ] **Step 2: Write the failing test** `.claude/skills/gtd-setup/tests/test_apply.py`

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply as A

SCAFFOLD = Path(__file__).resolve().parents[1] / "scaffold" / "vault"

def test_apply_creates_all_assets(tmp_path):
    res = A.apply(SCAFFOLD, tmp_path)
    assert (tmp_path / "30 Resources" / "GTD System.md").exists()
    assert (tmp_path / "Dashboard.md").exists()
    assert (tmp_path / ".obsidian" / "app.json").exists()
    assert res["created"] and not res["skipped"]

def test_apply_is_idempotent(tmp_path):
    A.apply(SCAFFOLD, tmp_path)
    res2 = A.apply(SCAFFOLD, tmp_path)
    assert res2["created"] == []          # nothing new the second time
    assert res2["skipped"]                # everything skipped

def test_apply_never_overwrites_user_edits(tmp_path):
    target = tmp_path / "Dashboard.md"
    A.apply(SCAFFOLD, tmp_path)
    target.write_text("MY EDITS")
    A.apply(SCAFFOLD, tmp_path)           # no --force
    assert target.read_text() == "MY EDITS"

def test_force_overwrites(tmp_path):
    A.apply(SCAFFOLD, tmp_path)
    (tmp_path / "Dashboard.md").write_text("X")
    A.apply(SCAFFOLD, tmp_path, force=True)
    assert (tmp_path / "Dashboard.md").read_text() != "X"
```

- [ ] **Step 3: Run to verify failure** — Run: `python3 -m pytest ".claude/skills/gtd-setup/tests/test_apply.py" -q`. Expected: ERROR `No module named 'apply'`.

- [ ] **Step 4: Implement `.claude/skills/gtd-setup/apply.py`**

```python
#!/usr/bin/env python3
"""Idempotent scaffolder for the GTD second brain. Copies the bundled asset tree
into a target vault, creating only files that don't already exist. Standard library only."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

def apply(scaffold_root: Path, target: Path, force: bool = False) -> dict:
    scaffold_root = Path(scaffold_root)
    target = Path(target)
    created, skipped = [], []
    for src in sorted(scaffold_root.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(scaffold_root)
        dst = target / rel
        if dst.exists() and not force:
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        created.append(str(rel))
    return {"created": created, "skipped": skipped}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Scaffold or repair a GTD second-brain vault.")
    p.add_argument("target", nargs="?", default=".", help="vault root (default: current dir)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    args = p.parse_args(argv)
    scaffold = Path(__file__).resolve().parent / "scaffold" / "vault"
    res = apply(scaffold, Path(args.target), force=args.force)
    for c in res["created"]:
        print(f"created {c}")
    for s in res["skipped"]:
        print(f"skipped {s}")
    print(f"\n{len(res['created'])} created, {len(res['skipped'])} skipped")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run to verify pass** — Run: `python3 -m pytest ".claude/skills/gtd-setup/tests/test_apply.py" -q`. Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add ".claude/skills/gtd-setup/apply.py" ".claude/skills/gtd-setup/tests" ".claude/skills/gtd-setup/scaffold"
git commit -m "feat: add gtd-setup scaffolder (idempotent copier) with asset tree and tests"
```

---

### Task 2: `gtd-setup` skill

**Files:**
- Create: `.claude/skills/gtd-setup/SKILL.md`

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-setup
description: Use when the user wants to set up, scaffold, initialize, or repair the GTD second-brain vault — creating the folder structure, templates, dashboards, and config. Triggers on "set up the vault", "scaffold", "initialize second brain", "repair the structure", "gtd setup".
---

# GTD Setup

Scaffolds or repairs the vault. Idempotent — it only creates what's missing and never overwrites
existing notes. This skill is the canonical source of the vault structure.

## Steps
1. Determine the vault root (the repo root, or a directory the user names).
2. Run the bundled copier:
   ```
   python3 .claude/skills/gtd-setup/apply.py <vault-root>
   ```
   It prints `created …` / `skipped …` per file and a summary.
3. Report what was created vs already present. If everything was skipped, the vault is intact.
4. Point the user at `30 Resources/GTD System.md` (conventions) and `docs/gtd/obsidian-plugins.md`
   (install Dataview for the live dashboard).

## Notes
- To rebuild a NEW vault elsewhere, copy `.claude/skills/gtd-setup/` (skill + `scaffold/` + `apply.py`)
  into that repo and run the copier there.
- `--force` overwrites existing files — only use it when the user explicitly wants to reset to
  defaults, and confirm first.
- Python 3.9+ with no third-party packages is the only requirement.
~~~

- [ ] **Step 2: Verify frontmatter** — Run: `python3 -c "import re;t=open('.claude/skills/gtd-setup/SKILL.md').read();m=re.match(r'^---\n(.*?)\n---',t,re.S);assert m and 'name: gtd-setup' in m.group(1);print('OK')"`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-setup/SKILL.md
git commit -m "feat: add gtd-setup skill"
```

---

### Task 3: Materialize the committed vault

**Files:**
- Create (generated): all files under "Materialized vault" in the File Structure map.

- [ ] **Step 1: Run the scaffolder at the repo root**

Run: `python3 ".claude/skills/gtd-setup/apply.py" .`
Expected: a list of `created …` lines covering the folders, guide notes, `30 Resources/GTD System.md`, templates, `Dashboard.md`, `Weekly Review.md`, `.obsidian/*.json`, `.gitignore`; summary shows all created.

- [ ] **Step 2: Verify structure and JSON validity**

Run:
```bash
for d in "00 Inbox" "10 Projects" "20 Areas" "30 Resources" "40 Archive" Journal People Meetings; do test -f "$d/README.md" && echo "OK $d"; done
test -f "30 Resources/GTD System.md" && test -f Dashboard.md && test -f "Weekly Review.md" && echo "OK core files"
for f in .obsidian/*.json; do python3 -c "import json;json.load(open('$f'))" && echo "OK $f"; done
```
Expected: all `OK`, no errors.

- [ ] **Step 3: Confirm idempotency** — Run: `python3 ".claude/skills/gtd-setup/apply.py" . | tail -1`. Expected: `0 created, N skipped` (N > 0).

- [ ] **Step 4: Commit**

```bash
git add "00 Inbox" "10 Projects" "20 Areas" "30 Resources" "40 Archive" Journal People Meetings _templates Dashboard.md "Weekly Review.md" .obsidian .gitignore
git commit -m "feat: materialize GTD vault via gtd-setup (structure, templates, dashboards, config)"
```

---

## Phase 1 — GTD workflow skills

> Each skill is portable (no Claude-only dependency). After writing, verify frontmatter with:
> `python3 -c "import re;t=open('<path>').read();m=re.match(r'^---\n(.*?)\n---',t,re.S);assert m and 'name:' in m.group(1) and 'description:' in m.group(1);print('OK')"`

### Task 4: `gtd-capture` skill

**Files:** Create `.claude/skills/gtd-capture/SKILL.md`

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-capture
description: Use when the user wants to quickly capture a thought, task, idea, link, or note into their GTD second brain without organizing it yet. Triggers on "capture", "add to inbox", "jot down", "remind me to", "note that".
---

# GTD Capture

Friction-free capture into `00 Inbox/`. Speed over organization — do not clarify or file it
(that's `/gtd-process-inbox`).

## Steps
1. Write what the user said to a new file in `00 Inbox/`.
2. Filename: `<today> <short-slug>.md`, e.g. `00 Inbox/2026-09-09 call-dentist.md`.
3. Contents — checkbox if it's clearly an action, plain text otherwise:
   ```
   ---
   type: inbox
   captured: 2026-09-09
   ---
   - [ ] Call the dentist to reschedule
   ```
4. Confirm in one line: "📥 Captured to inbox."

## Rules
- Never route to a project/area during capture. Everything lands in `00 Inbox/`.
- Multiple items → one file each (or one file with several checkboxes if clearly related).
- Single confirmation line only.
~~~

- [ ] **Step 2: Verify frontmatter** (command above, this path). Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-capture && git commit -m "feat: add gtd-capture skill"`

---

### Task 5: `gtd-process-inbox` skill

**Files:** Create `.claude/skills/gtd-process-inbox/SKILL.md`
**Interfaces:** Consumes conventions (`30 Resources/GTD System.md`) and `_templates/Project.md`.

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-process-inbox
description: Use when the user wants to process, clarify, or empty their GTD inbox — walking each captured item through the GTD decision tree and filing it. Triggers on "process inbox", "clarify", "empty my inbox", "clear the inbox".
---

# GTD Process Inbox (Clarify & Organize)

Walk every item in `00 Inbox/` through the GTD clarify workflow until the inbox is empty. Read
`30 Resources/GTD System.md` first.

## Process
Take files in `00 Inbox/` (ignore `README.md`) oldest first. For each, confirm before moving files:
1. Actionable? No → trash (delete), or reference (move to `30 Resources/` / `20 Areas/`,
   `type: reference`), or someday (`status: someday` project, or `#someday` task).
2. Actionable → one action or several?
   - Several (project) → new note in `10 Projects/` from `_templates/Project.md`; outcome +
     at least one `#next` action.
   - One action: <2 min → do now then delete; delegate → `#waiting` + `[[Person]]` +
     `[since:: today]`; defer → `#next` + context tag (or `[scheduled:: DATE]`).
3. Remove the processed file from `00 Inbox/` once filed.

## Rules
- End state: empty inbox (only `README.md`). Say so when done.
- Confirm before deleting anything the user might keep.
- Every touched project ends with at least one `#next` action.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-process-inbox && git commit -m "feat: add gtd-process-inbox skill"`

---

### Task 6: `gtd-next-actions` skill

**Files:** Create `.claude/skills/gtd-next-actions/SKILL.md`

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-next-actions
description: Use when the user asks what to work on now, wants their next actions, or filters tasks by context/time/energy. Triggers on "what should I do", "next actions", "what's on my list", "what can I do at my computer", "what's due".
---

# GTD Next Actions (Engage)

Help the user decide what to do now. Read `30 Resources/GTD System.md`. Read-only unless asked to
check something off.

## Steps
1. Grep open `#next` tasks (unchecked, not `#waiting`) across `00 Inbox/`, `10 Projects/`,
   `20 Areas/`, `Journal/`, `People/`, `Meetings/` (skip `40 Archive/`, `_templates/`, reference docs).
2. Hide items whose `[scheduled:: DATE]` is in the future.
3. If given a context (`@computer`, "phone", "errands"), filter to that context tag. If given
   time/energy, prefer short/low-effort items and say why.
4. Show due/overdue (`[due:: DATE]`) first, then group by context; each line: action, project
   (from `[[link]]`), due date. Keep to 5–10 items.
5. Offer to check one off or start one.

## Rules
- Never invent tasks. If nothing is queued, suggest `/gtd-process-inbox` or `/gtd-weekly-review`.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-next-actions && git commit -m "feat: add gtd-next-actions skill"`

---

### Task 7: `gtd-weekly-review` skill

**Files:** Create `.claude/skills/gtd-weekly-review/SKILL.md`
**Interfaces:** Consumes `_templates/Weekly Review.md`; writes a `Journal/` note tagged `#weekly-review` (read by `gtd-status`/the hook for recency).

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-weekly-review
description: Use when the user wants to do their GTD weekly review — the recurring ritual to get clear, current, and creative. Triggers on "weekly review", "review my week", "gtd review", "do my review".
---

# GTD Weekly Review (Reflect)

Guide the user through the review interactively, updating the vault as you go. Full checklist in
`Weekly Review.md`. Read `30 Resources/GTD System.md`.

## Process
### Get Clear
- Process `00 Inbox/` to empty (`/gtd-process-inbox`); prompt a brain-dump and process it.
### Get Current
- Projects: each `status: active` note in `10 Projects/` has a concrete `#next`; bump `review:` +7d.
- Waiting For: list `#waiting`; flag stale `[since::]`; offer follow-ups.
- Calendar/Journal: past week + next two weeks. If Outlook is configured, `/gtd-outlook` can pull
  the calendar. People: skim `People/` agendas.
### Get Creative
- Promote ready `#someday`/`status: someday` items. Review `20 Areas/`. Archive done projects
  (`status: done` → `40 Archive/`).

## Finish
- Create a `Journal/` note from `_templates/Weekly Review.md`, tagged `#weekly-review`, summarizing
  changes and carry-overs. Offer to refresh the dashboard (`/gtd-dashboard`).

## Rules
- Confirm before deleting/archiving. Done = inbox empty, every active project has a next action,
  review note written.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-weekly-review && git commit -m "feat: add gtd-weekly-review skill"`

---

### Task 8: `gtd-status` skill (portable session brief)

**Files:** Create `.claude/skills/gtd-status/SKILL.md`

This is the portable equivalent of the SessionStart brief — invokable in any harness. The Claude
Code hook (Task 12) calls the same shell logic, but this skill is the canonical behavior.

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-status
description: Use when the user opens the vault or asks for a status brief / overview of their GTD system — inbox size, active projects, weekly-review recency, and next actions ready now. Triggers on "status", "brief me", "where am I", "gtd status", "what's my day".
---

# GTD Status (brief)

Print a short, read-only brief. Works in any harness (no dependency on hooks). If the shell hook
`.claude/hooks/gtd-status.sh` exists you may run it for speed; otherwise compute directly.

## Compute
1. **Inbox:** count files in `00 Inbox/` excluding `README.md`.
2. **Active projects:** notes in `10 Projects/` whose frontmatter has `status: active`.
3. **Weekly review recency:** most recent `Journal/` note containing `weekly-review`
   (exclude `README.md`); report age in days; flag if ≥7 or none.
4. **Next actions ready:** up to 5 open `#next` tasks (not `#waiting`, `[scheduled::]` not in the
   future), across content folders (skip `40 Archive/`, `_templates/`, reference docs).

## Output (example shape)
```
🧠 Second Brain — GTD status
📥 Inbox: 3 to process · 📋 5 active projects
⚠️  Weekly review is 9 days old — run /gtd-weekly-review
⚡ Next actions ready:
   • Draft Q3 proposal  (Q3 Proposal)  📅 2026-09-20
```

## Rules
- Read-only. Keep it to a few lines. Never invent tasks.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-status && git commit -m "feat: add portable gtd-status skill"`

---

## Phase 2 — Dashboards

### Task 9: Portable dashboard generator (`build_dashboard.py`) + tests

**Files:** Create `scripts/build_dashboard.py`, `scripts/tests/test_build_dashboard.py`

**Interfaces:**
- Produces: CLI `python3 scripts/build_dashboard.py [vault_root] [--out dashboard.html]`. Reads the vault, writes a self-contained HTML file. Exposes `collect(vault: Path) -> dict` (keys: `inbox` int, `active_projects` list[str], `next_by_context` dict[str,list[str]], `waiting` list[str], `due_soon` list[str]) and `render(data: dict, generated: str) -> str` (returns full HTML). Read-only.

- [ ] **Step 1: Write the failing test** `scripts/tests/test_build_dashboard.py`

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_dashboard as B

def _mk(vault: Path):
    (vault / "30 Resources").mkdir(parents=True)
    (vault / "30 Resources" / "GTD System.md").write_text("# GTD\n")
    (vault / "00 Inbox").mkdir()
    (vault / "00 Inbox" / "a.md").write_text("- [ ] loose\n")
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "10 Projects").mkdir()
    (vault / "10 Projects" / "P.md").write_text(
        "---\ntype: project\nstatus: active\n---\n"
        "- [ ] Pick SSG #next #computer [due:: 2026-09-15] [[P]]\n"
        "- [ ] Wait domain #waiting [[Reg]] [since:: 2026-09-02]\n")

def test_collect_counts(tmp_path):
    _mk(tmp_path)
    d = B.collect(tmp_path)
    assert d["inbox"] == 1
    assert d["active_projects"] == ["P"]
    assert any("Pick SSG" in x for x in d["next_by_context"].get("#computer", []))
    assert any("Wait domain" in x for x in d["waiting"])

def test_render_is_self_contained_html(tmp_path):
    _mk(tmp_path)
    html = B.render(B.collect(tmp_path), generated="2026-09-09")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html   # no external assets
    assert "Pick SSG" in html
```

- [ ] **Step 2: Run to verify failure** — Run: `python3 -m pytest scripts/tests/test_build_dashboard.py -q`. Expected: ERROR `No module named 'build_dashboard'`.

- [ ] **Step 3: Implement `scripts/build_dashboard.py`**

```python
#!/usr/bin/env python3
"""Generate a self-contained dashboard.html from the vault. Read-only, stdlib only."""
from __future__ import annotations
import argparse, datetime as _dt, html, re
from pathlib import Path

CONTENT = ["00 Inbox", "10 Projects", "20 Areas", "Journal", "People", "Meetings"]
CONTEXTS = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"]
TASK_RE = re.compile(r"^\s*-\s*\[(?P<m>[ xX])\]\s*(?P<b>.*)$")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)")
FIELD_RE = re.compile(r"\[([a-z][a-z0-9_-]*)::\s*([^\]]*)\]")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

def _clean(body: str) -> str:
    t = FIELD_RE.sub("", body); t = LINK_RE.sub(r"\1", t); t = TAG_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip()

def _iter_task_lines(vault: Path):
    for d in CONTENT:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                m = TASK_RE.match(line)
                if m:
                    yield m.group("m").lower() == "x", m.group("b")

def collect(vault: Path) -> dict:
    vault = Path(vault)
    inbox = 0
    ib = vault / "00 Inbox"
    if ib.is_dir():
        inbox = len([p for p in ib.glob("*.md") if p.name != "README.md"])
    active = []
    pj = vault / "10 Projects"
    if pj.is_dir():
        for p in sorted(pj.rglob("*.md")):
            if p.name != "README.md" and "status: active" in p.read_text(encoding="utf-8"):
                active.append(p.stem)
    next_by_ctx: dict[str, list[str]] = {}
    waiting, due_soon = [], []
    today = _dt.date.today()
    for done, body in _iter_task_lines(vault):
        if done:
            continue
        tags = ["#" + t for t in TAG_RE.findall(body)]
        fields = {k: v.strip() for k, v in FIELD_RE.findall(body)}
        text = _clean(body)
        if "#waiting" in tags:
            waiting.append(text); continue
        if "#next" in tags:
            sched = fields.get("scheduled")
            if sched:
                try:
                    if _dt.date.fromisoformat(sched) > today:
                        continue
                except ValueError:
                    pass
            ctx = next((c for c in CONTEXTS if c in tags), "#anywhere")
            label = text + (f"  📅 {fields['due']}" if "due" in fields else "")
            next_by_ctx.setdefault(ctx, []).append(label)
            due = fields.get("due")
            if due:
                try:
                    if _dt.date.fromisoformat(due) <= today + _dt.timedelta(days=7):
                        due_soon.append(f"{text} — {due}")
                except ValueError:
                    pass
    return {"inbox": inbox, "active_projects": active, "next_by_context": next_by_ctx,
            "waiting": waiting, "due_soon": due_soon}

def _ul(items): 
    return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>" if items else "<p class=empty>None</p>"

def render(data: dict, generated: str) -> str:
    n_next = sum(len(v) for v in data["next_by_context"].values())
    cols = ""
    for ctx, items in sorted(data["next_by_context"].items()):
        cols += f"<h3>{html.escape(ctx)}</h3>{_ul(items)}"
    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>GTD Dashboard</title>
<style>
:root{{color-scheme:light dark}}
body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:1.5rem;background:#fafafa;color:#1a1a1a}}
@media(prefers-color-scheme:dark){{body{{background:#161616;color:#e8e8e8}}}}
h1{{margin:.2rem 0}} .kpis{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}}
.kpi{{flex:1;min-width:120px;border:1px solid #8883;border-radius:12px;padding:1rem;text-align:center}}
.kpi b{{display:block;font-size:1.8rem}} .grid{{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.card{{border:1px solid #8883;border-radius:12px;padding:1rem}} .empty{{color:#8888}}
small{{color:#8888}}
</style></head><body>
<h1>🧠 GTD Dashboard</h1><small>Snapshot generated {html.escape(generated)} · live view: Dashboard.md in Obsidian</small>
<div class=kpis>
<div class=kpi><b>{data['inbox']}</b>inbox</div>
<div class=kpi><b>{len(data['active_projects'])}</b>active projects</div>
<div class=kpi><b>{n_next}</b>next actions</div>
<div class=kpi><b>{len(data['waiting'])}</b>waiting</div>
</div>
<div class=grid>
<div class=card><h2>⚡ Next actions</h2>{cols or '<p class=empty>None</p>'}</div>
<div class=card><h2>⏳ Waiting for</h2>{_ul(data['waiting'])}</div>
<div class=card><h2>📋 Active projects</h2>{_ul(data['active_projects'])}</div>
<div class=card><h2>🔥 Due soon</h2>{_ul(data['due_soon'])}</div>
</div></body></html>"""

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=".")
    ap.add_argument("--out", default="dashboard.html")
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    html_str = render(collect(vault), generated=_dt.date.today().isoformat())
    (vault / a.out).write_text(html_str, encoding="utf-8")
    print(f"wrote {a.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass** — Run: `python3 -m pytest scripts/tests/test_build_dashboard.py -q`. Expected: 2 passed.

- [ ] **Step 5: Smoke-test on the real vault** — Run: `python3 scripts/build_dashboard.py . --out dashboard.html && python3 -c "print(open('dashboard.html').read()[:15])"`. Expected: prints `wrote dashboard.html` then `<!doctype html>`. Then add `dashboard.html` to `.gitignore` (generated artifact) OR commit it as a sample — default: gitignore it. Run: `grep -q '^dashboard.html' .gitignore || echo 'dashboard.html' >> .gitignore`.

- [ ] **Step 6: Commit**

```bash
git add scripts .gitignore
git commit -m "feat: add portable static dashboard.html generator with tests"
```

---

### Task 10: `gtd-dashboard` skill

**Files:** Create `.claude/skills/gtd-dashboard/SKILL.md`
**Interfaces:** Consumes `scripts/build_dashboard.py` (Task 9).

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-dashboard
description: Use when the user wants a visual dashboard of their GTD second brain as a shareable HTML page they can open in a browser. Triggers on "dashboard", "show me my system", "gtd overview", "build my dashboard".
---

# GTD Dashboard (portable HTML snapshot)

Generates a self-contained `dashboard.html` from the vault — opens in any browser, no plugin, works
in any harness. Complements the live `Dashboard.md` (Obsidian + Dataview).

## Steps
1. Run: `python3 scripts/build_dashboard.py . --out dashboard.html`
2. Tell the user the file is at `dashboard.html` and how to open it (double-click / `open`).
3. (Claude Code only, optional) If the user wants a shareable link, additionally load the
   `artifact-design` skill and publish the same HTML as an Artifact. Skip this in other harnesses.

## Rules
- Read-only; the generator never modifies notes.
- It's a point-in-time snapshot — the live view is `Dashboard.md`. Numbers come only from the files.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-dashboard && git commit -m "feat: add gtd-dashboard skill (portable HTML)"`

---

## Phase 3 — Cross-harness wiring

### Task 11: MCP config for both harnesses

**Files:** Create `.mcp.json` (Claude Code), `opencode.json` (opencode)

**Interfaces:** Both register the `outlook` server, launched from the env var `OUTLOOK_MCP_BIN` (path to `outlook-mcp-rs` binary). If unset/absent, the server simply doesn't start; the rest of the system is unaffected.

- [ ] **Step 1: Write `.mcp.json`**

```json
{
  "mcpServers": {
    "outlook": {
      "command": "${OUTLOOK_MCP_BIN}",
      "args": [],
      "env": {}
    }
  }
}
```

- [ ] **Step 2: Write `opencode.json`**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "outlook": {
      "type": "local",
      "command": ["{env:OUTLOOK_MCP_BIN}"],
      "enabled": true
    }
  }
}
```

- [ ] **Step 3: Verify both are valid JSON** — Run: `for f in .mcp.json opencode.json; do python3 -c "import json;json.load(open('$f'))" && echo "OK $f"; done`. Expected: two `OK`.

- [ ] **Step 4: Commit** — `git add .mcp.json opencode.json && git commit -m "feat: register outlook MCP server for Claude Code and opencode"`

---

### Task 11b: Vendor external artifacts (self-contained repo)

Goal: the repo contains everything except Obsidian and the LLM harness — the community plugins and
the Outlook MCP binary ship in-repo, version-pinned. All are fetched from GitHub release assets
(the `github.com/<repo>/releases/latest/download/<file>` path works through the proxy).

**Files:**
- Create: `.obsidian/plugins/{dataview,realclaudian,smart-second-brain}/{manifest.json,main.js,styles.css}`, `vendor/outlook-mcp-rs/outlook-mcp-rs.exe`, `vendor/README.md`, `.obsidian/plugins/README.md`

- [ ] **Step 1: Download the three plugins**

```bash
for spec in "dataview:blacksmithgu/obsidian-dataview" "realclaudian:YishenTu/claudian" "smart-second-brain:your-papa/obsidian-smart2brain"; do
  id="${spec%%:*}"; repo="${spec#*:}"; mkdir -p ".obsidian/plugins/$id"
  for f in manifest.json main.js styles.css; do
    curl -sSL -f -o ".obsidian/plugins/$id/$f" "https://github.com/$repo/releases/latest/download/$f" || rm -f ".obsidian/plugins/$id/$f"
  done
done
```

- [ ] **Step 2: Download the Outlook binary**

```bash
mkdir -p vendor/outlook-mcp-rs
curl -sSL -f -o vendor/outlook-mcp-rs/outlook-mcp-rs.exe \
  "https://github.com/adamkopelman/outlook-mcp-rs/releases/latest/download/outlook-mcp-rs.exe"
```

- [ ] **Step 3: Write provenance notes** (record source + pinned version from each `manifest.json`)

`.obsidian/plugins/README.md` — a table of vendored plugins, their `id`, version (from manifest),
source repo URL, and license; note "vendored release builds; update by re-downloading the release
assets." `vendor/README.md` — the Outlook binary's source repo, version/tag, platform
(Windows x86-64), sha256 (`sha256sum`), and that it's used via `$OUTLOOK_MCP_BIN`.

- [ ] **Step 4: Verify** — Run: `for p in dataview realclaudian smart-second-brain; do test -f ".obsidian/plugins/$p/main.js" && test -f ".obsidian/plugins/$p/manifest.json" && echo "OK $p"; done; file vendor/outlook-mcp-rs/outlook-mcp-rs.exe | grep -q 'MS Windows' && echo "OK exe"`. Expected: three `OK <plugin>` + `OK exe`.

- [ ] **Step 5: Commit**

```bash
git add .obsidian/plugins vendor
git commit -m "chore: vendor Obsidian plugins and Outlook MCP binary (self-contained repo)"
```

---

### Task 12: SessionStart hook (optional Claude Code auto-trigger)

**Files:** Create `.claude/hooks/gtd-status.sh`, `.claude/hooks/test_gtd-status.sh`, `.claude/settings.json`

**Interfaces:** The hook prints the same brief as the `gtd-status` skill. Read-only. Claude-Code-only convenience; opencode/other harnesses use `/gtd-status` instead.

> Real code — TDD. (This is the same well-tested script from the earlier design; keep its test.)

- [ ] **Step 1: Write the failing test** `.claude/hooks/test_gtd-status.sh`

```bash
#!/usr/bin/env bash
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gtd-status.sh"
fail=0; ac(){ grep -qF "$2" <<<"$1" && echo "OK  $3" || { echo "FAIL $3"; fail=1; }; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/00 Inbox" "$TMP/10 Projects" "$TMP/Journal"
echo "- [ ] loose" > "$TMP/00 Inbox/x.md"
printf '%s\n' '---' 'status: active' '---' \
  '- [ ] Pick SSG #next #computer [due:: 2026-09-15] [[P]]' \
  '- [ ] Wait domain #waiting [[Reg]] [since:: 2026-09-02]' > "$TMP/10 Projects/P.md"
out="$(CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK")"
ac "$out" "Inbox: 1" "inbox count"; ac "$out" "1 active project" "active projects"
ac "$out" "Pick SSG" "next surfaced"
grep -q "Wait domain" <<<"$out" && { echo "FAIL waiting excluded"; fail=1; } || echo "OK  waiting excluded"
ac "$out" "No weekly review" "review none"
E="$(mktemp -d)"; o2="$(CLAUDE_PROJECT_DIR="$E" bash "$HOOK")"; rm -rf "$E"; ac "$o2" "Inbox: 0" "empty vault"
exit $fail
```

- [ ] **Step 2: Run to verify failure** — Run: `chmod +x .claude/hooks/test_gtd-status.sh && bash .claude/hooks/test_gtd-status.sh`. Expected: FAIL (no `gtd-status.sh`).

- [ ] **Step 3: Implement `.claude/hooks/gtd-status.sh`**

```bash
#!/usr/bin/env bash
# SessionStart hook: prints a GTD brief (same as the gtd-status skill). Read-only.
set -uo pipefail
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then VAULT="$CLAUDE_PROJECT_DIR"
else VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; fi
cd "$VAULT" 2>/dev/null || exit 0

inbox_count=0
[[ -d "00 Inbox" ]] && inbox_count=$(find "00 Inbox" -maxdepth 1 -type f -name '*.md' ! -name 'README.md' 2>/dev/null | wc -l | tr -d ' ')

review_line="⚠️  No weekly review found yet — run /gtd-weekly-review"
if [[ -d "Journal" ]]; then
  last=$(grep -rl "weekly-review" "Journal" --include='*.md' 2>/dev/null | grep -v '/README.md$' | xargs -r ls -t 2>/dev/null | head -1)
  if [[ -n "$last" ]]; then
    now=$(date +%s); mt=$(date -r "$last" +%s 2>/dev/null || echo "$now"); days=$(( (now-mt)/86400 ))
    if (( days>=7 )); then review_line="⚠️  Weekly review is ${days} days old — run /gtd-weekly-review"
    else review_line="✅ Weekly review done ${days}d ago"; fi
  fi
fi

dirs=(); for d in "00 Inbox" "10 Projects" "20 Areas" "Journal" "People" "Meetings"; do [[ -d "$d" ]] && dirs+=("$d"); done
next=""
if (( ${#dirs[@]} > 0 )); then
  next=$(grep -rh '^[[:space:]]*- \[ \].*#next' "${dirs[@]}" --include='*.md' 2>/dev/null \
    | grep -v '#waiting' \
    | sed -E 's/^[[:space:]]*- \[ \][[:space:]]*//; s/\[\[([^]]*)\]\]/\1/g; s/\[[a-z]+:: ?[^]]*\]//g; s/#[A-Za-z_-]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' \
    | grep -v '^$' | head -5)
fi

proj=0; [[ -d "10 Projects" ]] && proj=$(grep -rls 'status: active' "10 Projects" --include='*.md' 2>/dev/null | wc -l | tr -d ' ')

echo "🧠 Second Brain — GTD status"
echo "📥 Inbox: ${inbox_count} item(s) · 📋 ${proj} active project(s)"
echo "$review_line"
if [[ -n "$next" ]]; then echo "⚡ Next actions ready:"; while IFS= read -r a; do echo "   • $a"; done <<< "$next"
else echo "⚡ No #next actions queued — try /gtd-process-inbox or /gtd-weekly-review."; fi
```

- [ ] **Step 4: Make executable, run test** — Run: `chmod +x .claude/hooks/gtd-status.sh && bash .claude/hooks/test_gtd-status.sh; echo exit=$?`. Expected: all `OK`, `exit=0`.

- [ ] **Step 5: Write `.claude/settings.json`**

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/gtd-status.sh\"" } ] }
    ]
  }
}
```

- [ ] **Step 6: Verify JSON** — Run: `python3 -c "import json;json.load(open('.claude/settings.json'));print('OK')"`. Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks .claude/settings.json
git commit -m "feat: add optional Claude Code SessionStart hook mirroring gtd-status"
```

---

### Task 13: `AGENTS.md` (harness-neutral operating guide)

**Files:** Create `AGENTS.md`

- [ ] **Step 1: Write `AGENTS.md`**

```markdown
# AGENTS.md — operating this vault

This repo is a GTD second brain (an Obsidian vault) driven by skills + MCP. It works in Claude Code,
opencode, and any harness that discovers skills in `.claude/skills/`.

## Skills (the interface)
- `gtd-setup` — scaffold/repair the vault (idempotent).
- `gtd-capture` — capture into `00 Inbox/`.
- `gtd-process-inbox` — clarify the inbox to empty.
- `gtd-next-actions` — what to do now.
- `gtd-weekly-review` — the weekly ritual.
- `gtd-status` — a read-only brief (inbox, projects, review recency, next actions).
- `gtd-dashboard` — build a portable `dashboard.html`.
- `gtd-outlook` — pull email/calendar from the Outlook MCP.

## Conventions
Tasks are markdown checkboxes. Contexts: `#computer #phone #errands #home #office #anywhere #agenda`.
Status: `#next` `#waiting` `#someday`. Fields: `[due:: ]` `[scheduled:: ]` `[since:: ]`. Full spec:
`30 Resources/GTD System.md`.

## Harness notes
- Skills are discovered from `.claude/skills/` by Claude Code, opencode, and Claudian (the Obsidian
  plugin that runs one of those agents in a side panel — the recommended way to use the vault).
- MCP: Claude Code reads `.mcp.json`; opencode reads `opencode.json`. Both launch the Outlook server
  from `$OUTLOOK_MCP_BIN`.
- The session brief is the `gtd-status` skill. Claude Code additionally auto-runs it via a
  `SessionStart` hook (`.claude/settings.json`); other harnesses: run `/gtd-status`.
- Optional: `gtd-maintain` runs a lightweight vault health pass; schedule it per harness if wanted.
```

- [ ] **Step 2: Verify** — Run: `grep -q 'gtd-setup' AGENTS.md && grep -q 'OUTLOOK_MCP_BIN' AGENTS.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit** — `git add AGENTS.md && git commit -m "docs: add AGENTS.md harness-neutral operating guide"`

---

## Phase 4 — Outlook MCP integration

### Task 14: `gtd-outlook` skill

**Files:** Create `.claude/skills/gtd-outlook/SKILL.md`

**Interfaces:** Uses the `outlook` MCP server's tools (e.g. `list_emails`, `get_email`, `list_events`) when present. Degrades to a clear message if the server isn't configured.

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-outlook
description: Use when the user wants to bring Microsoft Outlook email or calendar into their GTD second brain — turning flagged/starred emails into inbox items or pulling the calendar into the weekly review. Triggers on "outlook", "my email", "flagged emails to inbox", "pull my calendar".
---

# GTD Outlook bridge

Bridges the `outlook` MCP server (from outlook-mcp-rs) into GTD flows. Capture-only by default —
never sends mail or changes calendar events unless the user explicitly asks.

## Preconditions
The `outlook` MCP server must be configured (`.mcp.json` / `opencode.json`) and reachable — that
means classic Outlook running and signed in on a Windows machine, with `$OUTLOOK_MCP_BIN` set. If
its tools aren't available, tell the user how to enable it (`docs/gtd/outlook.md`) and stop.

## Flows
### Email → inbox
1. Use the Outlook tools to list flagged/important unread emails (`list_emails`, then `get_email`).
2. For each, run the capture pattern: write a file to `00 Inbox/` with the subject as the item, the
   sender and a one-line summary, and the Outlook item id / a note to find it. Mark `type: inbox`.
3. Do not mark the email read or reply. Report how many were captured; the user runs
   `/gtd-process-inbox` next.

### Calendar → weekly review
1. During `/gtd-weekly-review`, use `list_events` for the next two weeks.
2. Summarize commitments so they're reviewed alongside projects. Do not create events.

## Rules
- Read/capture only unless explicitly asked to send or schedule (then confirm first).
- Nothing is auto-filed — captured items land in `00 Inbox/` for normal processing.
~~~

- [ ] **Step 2: Verify frontmatter.** Expected: `OK`.
- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-outlook && git commit -m "feat: add gtd-outlook skill (email/calendar bridge)"`

---

### Task 15: Outlook setup docs

**Files:** Create `docs/gtd/outlook.md`

- [ ] **Step 1: Write `docs/gtd/outlook.md`**

```markdown
# Outlook MCP integration

The `gtd-outlook` skill uses [`outlook-mcp-rs`](https://github.com/adamkopelman/outlook-mcp-rs), an
MCP server that drives the classic Outlook desktop app on Windows (26 tools: email, calendar, tasks,
notes). No auth/tokens — it uses your signed-in Outlook session.

## Requirements
- Windows with the classic Outlook desktop app installed and signed in.
- Rust (2024 edition) to build, or a prebuilt binary.

## Build
    git clone https://github.com/adamkopelman/outlook-mcp-rs
    cd outlook-mcp-rs
    cargo build --release
    # → target/release/outlook-mcp-rs.exe

## Point the vault at it
The prebuilt binary is **already vendored** in this repo at `vendor/outlook-mcp-rs/outlook-mcp-rs.exe`
(you only need to build it yourself to update the version). Set an environment variable to its full
path (both harness configs read it):

    setx OUTLOOK_MCP_BIN "%CD%\vendor\outlook-mcp-rs\outlook-mcp-rs.exe"   # from the repo root, Windows

- Claude Code reads `.mcp.json` → server `outlook` → `command: ${OUTLOOK_MCP_BIN}`.
- opencode reads `opencode.json` → `mcp.outlook.command: ["{env:OUTLOOK_MCP_BIN}"]`.

Restart the harness. Outlook must be running. Then `/gtd-outlook` can pull flagged email into
`00 Inbox/` and surface your calendar during the weekly review.

## Not on Windows?
Everything else in the vault works without Outlook. The `outlook` server just won't start, and
`gtd-outlook` will say it's unavailable. (Network mode: `outlook-mcp-rs.exe --http --port 8080
--token SECRET` exposes it over HTTP if you run Outlook on a separate Windows box.)
```

- [ ] **Step 2: Verify** — Run: `grep -q 'OUTLOOK_MCP_BIN' docs/gtd/outlook.md && grep -q 'cargo build' docs/gtd/outlook.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit** — `git add docs/gtd/outlook.md && git commit -m "docs: add Outlook MCP setup guide"`

---

## Phase 5 — Docs

### Task 16: Obsidian plugins guide

**Files:** Create `docs/gtd/obsidian-plugins.md`

- [ ] **Step 1: Write `docs/gtd/obsidian-plugins.md`**

```markdown
# Obsidian plugins for this vault

## Required
### Dataview — powers `Dashboard.md`
1. Settings → Community plugins → turn off Restricted mode (first time).
2. Browse → "Dataview" → Install → Enable.
3. Reopen `Dashboard.md`; the query blocks render.
Without Dataview, use `/gtd-dashboard` (the portable `dashboard.html`) instead — no plugin needed.

## Optional
- **Smart Second Brain** (`obsidian-smart2brain`) — semantic / RAG search + an AI assistant that
  knows your notes. Complements Dataview: Dataview does *structured* queries (tags, fields),
  Smart Second Brain does *fuzzy/semantic* retrieval ("what did I note about pricing?"). Install via
  Community plugins → "Smart Second Brain".
- **Tasks** — richer task querying/recurrence; compatible with our checkbox conventions.
- **Calendar** — month view tied to `Journal/` daily notes.
- **Templater** — dynamic templates; our `_templates/` use core Templates and work without it.

## Core plugins already enabled
Templates (`_templates`), Daily notes (`Journal`, template `_templates/Daily Note.md`), Properties,
Tag pane, Backlinks, Graph — see `.obsidian/core-plugins.json`.
```

- [ ] **Step 2: Verify** — Run: `grep -q Dataview docs/gtd/obsidian-plugins.md && echo OK`. Expected: `OK`.
- [ ] **Step 3: Commit** — `git add docs/gtd/obsidian-plugins.md && git commit -m "docs: add Obsidian plugins guide"`

---

### Task 17: Portability + HTML-dashboard docs

**Files:** Create `docs/gtd/portability.md`, `docs/gtd/html-dashboard.md`

- [ ] **Step 1: Write `docs/gtd/portability.md`**

```markdown
# Running this vault in different harnesses

The system is skills + MCP + plain markdown, so it runs anywhere skills are discovered.

## Claude Code
- Skills: auto-discovered from `.claude/skills/`.
- MCP: `.mcp.json` (server `outlook`, launched from `$OUTLOOK_MCP_BIN`).
- Session brief: auto via the `SessionStart` hook (`.claude/settings.json`).

## opencode
- Skills: opencode discovers `.claude/skills/` natively (also `.opencode/skills`).
- MCP: `opencode.json` (`mcp.outlook`, `command: ["{env:OUTLOOK_MCP_BIN}"]`).
- Session brief: run `/gtd-status` (no hook system needed).

## Claudian (inside Obsidian) — recommended
[Claudian](https://community.obsidian.md/plugins/realclaudian) is an Obsidian community plugin that
embeds a CLI agent (Claude Code / opencode / Codex) in a side panel with this vault as the working
directory — so you drive the whole GTD system without leaving Obsidian.
- Install: Community plugins → "Claudian"; it requires a CLI agent already installed on your machine.
- Skills: it runs the underlying agent, which discovers `.claude/skills/` — all `gtd-*` skills work.
- MCP/brief: inherited from whichever agent Claudian runs (Claude Code → `.mcp.json` + hook;
  opencode → `opencode.json` + `/gtd-status`).
- This is the recommended day-to-day setup: live `Dashboard.md` and skills in one window.

## Any other skills+MCP harness
- Place/point skills at `.claude/skills/`. Configure the Outlook server per that harness's MCP
  format using `$OUTLOOK_MCP_BIN`. Use `/gtd-status` for the brief.

## Principle
Every automatic behavior is also a skill, so no capability is locked to one harness. Claude-only
extras (e.g. publishing the dashboard as an Artifact) are optional bonuses, never the only path.
```

- [ ] **Step 2: Write `docs/gtd/html-dashboard.md`**

```markdown
# Dashboards

| | Live (`Dashboard.md`) | Portable (`dashboard.html`) |
| --- | --- | --- |
| Engine | Dataview plugin, in Obsidian | `scripts/build_dashboard.py` via `/gtd-dashboard` |
| Updates | live as you edit | point-in-time snapshot |
| Needs | Obsidian + Dataview | nothing (opens in a browser) |
| Use for | daily driving | sharing / any harness / no Obsidian |

Generate the snapshot: `/gtd-dashboard`, or `python3 scripts/build_dashboard.py . --out dashboard.html`.
It shows KPIs (inbox / active projects / next actions / waiting), next actions by context,
waiting-for, active projects, and items due within 7 days. Read-only.
```

- [ ] **Step 3: Verify** — Run: `grep -q opencode docs/gtd/portability.md && test -f docs/gtd/html-dashboard.md && echo OK`. Expected: `OK`.
- [ ] **Step 4: Commit** — `git add docs/gtd/portability.md docs/gtd/html-dashboard.md && git commit -m "docs: add portability and dashboard docs"`

---

### Task 18: Rewrite the README

**Files:** Modify `README.md`

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# 🧠 Second Brain

A template for a GTD (Getting Things Done) second brain — an Obsidian vault operated by skills + MCP.
Runs in Claude Code, opencode, and any harness that discovers skills. Plain markdown all the way down.

## What's inside
| Surface | What it does |
| --- | --- |
| Vault structure | PARA folders (`00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`, `40 Archive`) + `Journal`, `People`, `Meetings`. State lives in tags + frontmatter. |
| Setup skill | `/gtd-setup` scaffolds or repairs the whole vault, idempotently. |
| GTD skills | `/gtd-capture`, `/gtd-process-inbox`, `/gtd-next-actions`, `/gtd-weekly-review`, `/gtd-status`, `/gtd-dashboard`. |
| Outlook | `/gtd-outlook` pulls email/calendar via the `outlook-mcp-rs` MCP server. |
| Live dashboard | `Dashboard.md` — Dataview queries inside Obsidian. |
| Portable dashboard | `dashboard.html` — self-contained, any browser (`/gtd-dashboard`). |
| Portability | Skills in `.claude/skills/` (Claude Code, opencode, Claudian); MCP in `.mcp.json` + `opencode.json`; see `AGENTS.md`. |

## Getting started
1. Scaffold (if starting empty): `/gtd-setup`, or `python3 .claude/skills/gtd-setup/apply.py .`
2. Open the folder as an Obsidian vault.
3. Install Dataview — see `docs/gtd/obsidian-plugins.md`.
4. (Recommended) Install **Claudian** to run these skills inside Obsidian; (optional) **Smart Second
   Brain** for semantic search. See `docs/gtd/portability.md` and `docs/gtd/obsidian-plugins.md`.
5. (Optional) Wire Outlook — see `docs/gtd/outlook.md`.
6. Read `30 Resources/GTD System.md` for conventions. Capture with `/gtd-capture`; review weekly
   with `/gtd-weekly-review`.

## Conventions (quick reference)
- Contexts: `#computer` `#phone` `#errands` `#home` `#office` `#anywhere` `#agenda`
- Status: `#next` (do now) · `#waiting` (delegated) · `#someday`
- Fields: `[due:: YYYY-MM-DD]` · `[scheduled:: YYYY-MM-DD]` · `[since:: YYYY-MM-DD]`

Full details: `30 Resources/GTD System.md`. Design/plan: `docs/superpowers/`. Harness guide: `AGENTS.md`.
```

- [ ] **Step 2: Verify** — Run: `grep -q 'gtd-setup' README.md && grep -q opencode README.md && echo OK`. Expected: `OK`.
- [ ] **Step 3: Commit** — `git add README.md && git commit -m "docs: rewrite README for the portable skills+MCP second brain"`

---

## Phase 6 — Optional: borrowed enhancements

> Build only if wanted. Semantic search is already covered by the optional **Smart Second Brain**
> plugin (Task 16). This phase adds the one code idea worth borrowing: a scheduled vault-health pass.

### Task 19: `gtd-maintain` skill (vault health pass)

**Files:** Create `.claude/skills/gtd-maintain/SKILL.md`

- [ ] **Step 1: Write the skill**

~~~markdown
---
name: gtd-maintain
description: Use when the user wants a health check of their GTD vault, or to run a maintenance pass — finding stuck projects, stale waiting-for items, overdue reviews, and archive candidates. Triggers on "maintain", "health check", "tidy the vault", "what's stuck", "gtd maintenance".
---

# GTD Maintain (health pass)

A read-only audit that surfaces problems and *proposes* fixes (never auto-edits without confirming).
Read `30 Resources/GTD System.md`. Runs in any harness; can be scheduled (see below).

## Checks
1. **Stuck projects** — `status: active` notes in `10 Projects/` with no open `#next` task.
2. **Stale waiting-for** — `#waiting` tasks whose `[since:: DATE]` is > 14 days ago.
3. **Overdue reviews** — active projects whose `review:` date is in the past.
4. **Aging inbox** — count of `00 Inbox/` items (excluding `README.md`); flag if not empty.
5. **Archive candidates** — `status: done` projects still outside `40 Archive/`.

## Output
A short report grouped by check, each item naming the file. Then offer concrete fixes:
add a `#next`, ping a person (`#agenda`), bump `review:`, archive a done project — applying only
what the user approves.

## Scheduling (optional, per harness)
- Claude Code: a Routine / cron that sends "run /gtd-maintain and summarize" on a schedule.
- opencode / other: the harness's own scheduler, or a system cron invoking the agent.
Keep scheduled runs read-only (report only); apply fixes interactively.

## Rules
- Read-only by default; confirm before any edit or archive move. Never delete notes.
~~~

- [ ] **Step 2: Verify frontmatter** (standard command, this path). Expected: `OK`.

- [ ] **Step 3: Commit** — `git add .claude/skills/gtd-maintain && git commit -m "feat: add optional gtd-maintain vault health skill"`

---

## Final verification (after all phases)

- [ ] **Setup idempotent:** `python3 .claude/skills/gtd-setup/apply.py /tmp/vt >/dev/null && python3 .claude/skills/gtd-setup/apply.py /tmp/vt | tail -1` → `0 created, N skipped`; `rm -rf /tmp/vt`.
- [ ] **All skills discoverable:** `for s in gtd-setup gtd-capture gtd-process-inbox gtd-next-actions gtd-weekly-review gtd-status gtd-dashboard gtd-outlook; do grep -q "name: $s" ".claude/skills/$s/SKILL.md" && echo "OK $s"; done` → eight `OK`.
- [ ] **Python suites green:** `python3 -m pytest .claude/skills/gtd-setup/tests scripts/tests -q` → all pass.
- [ ] **Hook test green:** `bash .claude/hooks/test_gtd-status.sh; echo exit=$?` → `exit=0`.
- [ ] **All JSON valid:** `for f in .mcp.json opencode.json .claude/settings.json .obsidian/*.json; do python3 -c "import json;json.load(open('$f'))"; done` → no errors.
- [ ] **Dashboard builds:** `python3 scripts/build_dashboard.py . --out /tmp/d.html && head -c15 /tmp/d.html` → `<!doctype html>`.
- [ ] **Clean tree:** `git status --porcelain` → clean.
- [ ] **Manual Obsidian pass:** open vault, enable Dataview, confirm `Dashboard.md` renders.
- [ ] **Push:** `git push -u origin claude/superpowers-skills-beuh67`.

---

## Appendix A — canonical vault asset bodies

These are the files created under `.claude/skills/gtd-setup/scaffold/vault/` in Task 1 (and copied to
the repo root by Task 3). Paths are relative to `scaffold/vault/`.

### A.1 Folder guide notes

`00 Inbox/README.md`
```markdown
# 📥 Inbox
Single capture point. Dump anything here without organizing. Process to empty with
`/gtd-process-inbox`. Should trend toward zero.
```
`10 Projects/README.md`
```markdown
# 📋 Projects
One note per project (an outcome needing >1 action). Use `_templates/Project.md`. Every active
project should have at least one `#next` action. See `30 Resources/GTD System.md`.
```
`20 Areas/README.md`
```markdown
# 🗂️ Areas
Ongoing responsibilities with no end date (Health, Finances, a role). Standards to maintain.
Projects can link to an area via `area:` frontmatter.
```
`30 Resources/README.md`
```markdown
# 📚 Resources
Reference material worth keeping. The GTD manual lives here: `30 Resources/GTD System.md`.
```
`40 Archive/README.md`
```markdown
# 🗄️ Archive
Completed projects and anything no longer active. Nothing is deleted — it's moved here.
```
`Journal/README.md`
```markdown
# 🗓️ Journal
Daily notes: log, quick captures, calendar. Use `_templates/Daily Note.md`. Weekly review notes are
tagged `#weekly-review` and live here.
```
`People/README.md`
```markdown
# 👥 People
One note per person — delegation, waiting-for, agendas. Link from tasks: `#agenda [[Person Name]]`.
Use `_templates/Person.md`.
```
`Meetings/README.md`
```markdown
# 🤝 Meetings
Meeting notes. Capture action items as `#next` tasks so they flow to the dashboard. Use
`_templates/Meeting.md`.
```

### A.2 `30 Resources/GTD System.md`
```markdown
---
type: reference
tags: [system, gtd]
---

# GTD System — How This Vault Works

PARA-style folders say *where things live*; tags + frontmatter say *what state things are in*. The
dashboards read these conventions, so keeping to them keeps everything in sync.

## Steps → where
Capture → `00 Inbox/` (`/gtd-capture`). Clarify → `/gtd-process-inbox`. Organize → Projects/Areas/
Resources or tasks. Reflect → `/gtd-weekly-review` + `Weekly Review.md`. Engage → `Dashboard.md`,
`/gtd-next-actions`, `/gtd-status`.

## Folders (PARA)
`00 Inbox/` unprocessed · `10 Projects/` outcomes needing >1 action · `20 Areas/` ongoing
responsibilities · `30 Resources/` reference · `40 Archive/` inactive · `Journal/` dailies ·
`People/` per-person · `Meetings/` notes.

## Tasks
Checkboxes inside project/daily notes, with tags + inline fields:

    - [ ] Draft the Q3 proposal #next #computer [due:: 2026-09-20] [[Q3 Proposal]]
    - [ ] Waiting on Sam for figures #waiting [[Sam Rivera]] [since:: 2026-09-08]
    - [ ] Someday: learn to sail #someday

Contexts (one per action): #computer #phone #errands #home #office #anywhere #agenda (pair #agenda
with [[Person]]). Status: #next (ready now — shown on dashboard), #waiting (delegated; + [[Person]] +
[since:: DATE]), #someday. Fields: [due:: DATE], [scheduled:: DATE] (tickler), [since:: DATE].

Rule of thumb: every active project has at least one #next action.

## Project frontmatter

    ---
    type: project
    status: active        # active | someday | done
    area: "[[Career]]"
    created: 2026-09-09
    review: 2026-09-16
    ---

## People frontmatter

    ---
    type: person
    tags: [person]
    ---

## Required plugin
Dataview powers `Dashboard.md` (Settings → Community plugins → Dataview). Or use `/gtd-dashboard`
for a portable `dashboard.html` that needs no plugin.
```

### A.3 Templates (`_templates/*.md`)
`_templates/Project.md`
```markdown
---
type: project
status: active
area: 
created: {{date:YYYY-MM-DD}}
review: {{date:YYYY-MM-DD}}
---

# {{title}}

**Outcome:** _What does "done" look like?_

## Next actions
- [ ]  #next #computer

## Notes

## Waiting for
- [ ]  #waiting [since:: {{date:YYYY-MM-DD}}]
```
`_templates/Daily Note.md`
```markdown
---
type: daily
created: {{date:YYYY-MM-DD}}
---

# {{date:dddd, MMMM D, YYYY}}

## Capture
- 

## Today's next actions
- [ ]  #next

## Log
```
`_templates/Person.md`
```markdown
---
type: person
tags: [person]
---

# {{title}}

**Role / context:** 

## Agenda
- [ ]  #agenda [[{{title}}]]

## Waiting for
- [ ]  #waiting [[{{title}}]] [since:: {{date:YYYY-MM-DD}}]

## Notes
```
`_templates/Meeting.md`
```markdown
---
type: meeting
date: {{date:YYYY-MM-DD}}
attendees: 
---

# {{title}}

**Date:** {{date:YYYY-MM-DD}}
**Attendees:** 

## Notes

## Decisions

## Action items
- [ ]  #next
```
`_templates/Weekly Review.md`
```markdown
---
type: daily
tags: [weekly-review]
created: {{date:YYYY-MM-DD}}
---

# Weekly Review — {{date:YYYY-MM-DD}}

See `Weekly Review.md` for the full checklist.

## Highlights this week

## Carried into next week
```

### A.4 `Dashboard.md`
~~~markdown
---
type: dashboard
cssclasses: [dashboard]
---

# 🧠 Second Brain — Dashboard

> Live view. Requires the Dataview plugin. Portable snapshot: `/gtd-dashboard`.

## 📥 Inbox
```dataview
LIST FROM "00 Inbox" SORT file.ctime ASC
```

## ⚡ Next Actions — by context
```dataview
TASK
WHERE !completed AND contains(tags, "#next") AND !contains(tags, "#waiting")
WHERE !scheduled OR scheduled <= date(today)
GROUP BY filter(tags, (t) => t = "#computer" OR t = "#phone" OR t = "#errands" OR t = "#home" OR t = "#office" OR t = "#anywhere" OR t = "#agenda")[0] AS "Context"
SORT due ASC
```

## 🔥 Due soon (7 days)
```dataview
TASK WHERE !completed AND due AND due <= date(today) + dur(7 days) SORT due ASC
```

## ⏳ Waiting For
```dataview
TASK WHERE !completed AND contains(tags, "#waiting") SORT since ASC
```

## 📋 Active Projects
```dataview
TABLE status, area, review AS "Next review"
FROM "10 Projects" WHERE type = "project" AND status = "active" SORT review ASC
```

## 🗓️ Projects needing review
```dataview
TABLE review AS "Review due"
FROM "10 Projects" WHERE type = "project" AND status = "active" AND review <= date(today) SORT review ASC
```

## 💤 Someday / Maybe
```dataview
LIST FROM "10 Projects" WHERE type = "project" AND status = "someday"
```
~~~

### A.5 `Weekly Review.md`
~~~markdown
---
type: reference
tags: [system, gtd, review]
---

# 🔄 Weekly Review

Run weekly (`/gtd-weekly-review` walks you through it).

## Get Clear
- [ ] Empty the inbox (`/gtd-process-inbox`)
- [ ] Collect loose notes; empty your head

## Get Current
- [ ] Review `Dashboard.md`; clear stale next actions
- [ ] Each active project has a `#next`?
- [ ] Chase stale `#waiting` (`[since::]`)
- [ ] Calendar: past week + next two weeks (Outlook via `/gtd-outlook`)
- [ ] `People/` agendas; bump `review:` dates

## Get Creative
- [ ] Promote ready Someday/Maybe
- [ ] Review `20 Areas/`; archive done projects to `40 Archive/`

---

## Review log
```dataview
TABLE file.ctime AS "Reviewed" FROM "Journal" WHERE contains(tags, "weekly-review") SORT file.ctime DESC LIMIT 8
```
~~~

### A.6 `.obsidian/*.json`
`.obsidian/app.json`
```json
{
  "alwaysUpdateLinks": true,
  "newFileLocation": "folder",
  "newFileFolderPath": "00 Inbox",
  "attachmentFolderPath": "30 Resources/attachments",
  "useMarkdownLinks": false
}
```
`.obsidian/core-plugins.json`
```json
{
  "file-explorer": true, "global-search": true, "switcher": true, "graph": true,
  "backlink": true, "outgoing-link": true, "tag-pane": true, "properties": true,
  "daily-notes": true, "templates": true, "note-composer": true, "command-palette": true,
  "editor-status": true, "bookmarks": true, "outline": true, "word-count": true
}
```
`.obsidian/templates.json`
```json
{ "folder": "_templates", "dateFormat": "YYYY-MM-DD", "timeFormat": "HH:mm" }
```
`.obsidian/daily-notes.json`
```json
{ "folder": "Journal", "format": "YYYY-MM-DD", "template": "_templates/Daily Note.md" }
```
`.obsidian/community-plugins.json` (enables the vendored plugins — see Task 11b)
```json
["dataview", "realclaudian", "smart-second-brain"]
```

### A.7 `.gitignore`
> Note: `.obsidian/plugins/` is intentionally **tracked** (vendored plugins ship in the repo — see
> Task 11b), so it is NOT ignored. Only per-machine state is ignored.
```gitignore
# Obsidian per-machine state (vendored plugins ARE tracked)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
.trash/

# Generated
dashboard.html

# OS / Python
.DS_Store
Thumbs.db
__pycache__/
*.pyc
.pytest_cache/
```

---

## Self-Review (author's checklist — completed)

**1. Spec coverage** — Setup skill → Tasks 1–3. GTD skills (5 steps + status) → Tasks 4–8. Portable
dashboard + live dashboard → Tasks 9–10 (+ `Dashboard.md` in Appendix A.4 via setup). Cross-harness
(skills location, dual MCP config, hook-as-optional, AGENTS.md) → Tasks 11–13, spec's portability
section. Outlook MCP → Tasks 11, 14, 15. Docs/README → Tasks 15–18. External tools: Claudian (harness) →
`docs/gtd/portability.md`, `AGENTS.md`, README (Tasks 17, 13, 18); Smart Second Brain (semantic
search) → `docs/gtd/obsidian-plugins.md` (Task 16). Borrowed enhancement `gtd-maintain` → Task 19
(optional). CLI → intentionally dropped (spec non-goal). Superpowers prerequisite → Global Constraints.

**2. Placeholder scan** — no "TBD"/"add error handling"/"similar to Task N". Code steps carry full
implementations; content steps carry full bodies (large vault bodies consolidated once in Appendix A
and referenced by the setup task to stay DRY, not omitted). Manual-only checks are labeled.

**3. Type/consistency** — `apply(scaffold_root, target, force=False) -> {"created","skipped"}` is used
identically by its tests and `main`. `build_dashboard.collect() -> {inbox, active_projects,
next_by_context, waiting, due_soon}` matches its test and `render()`. Tag/field/folder tokens match
Global Constraints across the hook, the dashboard generator, the skills, and Appendix A. Skill
`name` == directory for all eight skills. `$OUTLOOK_MCP_BIN` is the single source of the binary path
in `.mcp.json`, `opencode.json`, `AGENTS.md`, and `docs/gtd/outlook.md`.
```
