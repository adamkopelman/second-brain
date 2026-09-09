# GTD Second Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `second-brain` repo into a working GTD second brain — an Obsidian vault operated by Claude Code — covering structure, skills, an automation hook, two dashboards, a CLI, external-plugin guidance, and docs.

**Architecture:** Plain-markdown Obsidian vault at the repo root. GTD *location* is expressed with PARA-style folders; GTD *state* is expressed with tags + Dataview inline fields inside task checkboxes. Claude Code skills (`.claude/skills/gtd-*`) drive the five GTD steps conversationally; a read-only bash `SessionStart` hook briefs each session; the live dashboard is a Dataview note, the shareable dashboard is a published HTML Artifact; a stdlib-only Python CLI (`brain`) provides terminal access to the same data.

**Tech Stack:** Markdown, Obsidian (+ Dataview community plugin), Bash, Python 3 (stdlib + `pytest`), Claude Code skills/hooks, Claude Artifacts (HTML/CSS).

**Spec:** `docs/superpowers/specs/2026-09-09-gtd-second-brain.md`

## Global Constraints

- **Vault root = repo root.** All content folders live at the top level.
- **Folders (verbatim, including numeric prefixes and the space):** `00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`, `40 Archive`, `Journal`, `People`, `Meetings`, `_templates`.
- **Context tags (exact):** `#computer` `#phone` `#errands` `#home` `#office` `#anywhere` `#agenda`.
- **Status tags (exact):** `#next` `#waiting` `#someday`.
- **Inline fields (exact syntax):** `[due:: YYYY-MM-DD]`, `[scheduled:: YYYY-MM-DD]`, `[since:: YYYY-MM-DD]`.
- **Project frontmatter keys (exact):** `type: project`, `status: active|someday|done`, `area`, `created`, `review`.
- **Skills:** directory `.claude/skills/<name>/SKILL.md`; frontmatter has exactly `name` and `description`; `name` is kebab-case and equals the directory name; all GTD skills are prefixed `gtd-`. Do not touch the vendored Superpowers skills already in `.claude/skills/`.
- **Dates:** always `YYYY-MM-DD`. Use the real current date at execution time.
- **Read-only means read-only:** the hook and the `gtd-dashboard` / `gtd-next-actions` skills must never modify vault files.
- **No secrets** committed to the repo (relevant to the optional connectors phase).
- **Prerequisite already done:** the Superpowers skills library is installed at `.claude/skills/` (commit `b9f9264`). This plan builds on top of it; do not re-install or remove it.
- **Commit discipline:** one commit per completed task, message prefixed `feat:`/`docs:`/`chore:`/`test:`. Work on branch `claude/superpowers-skills-beuh67`.

---

## File Structure

Files created by this plan (Superpowers skills under `.claude/skills/` already exist and are untouched):

```
README.md                                 (rewrite — Task 21)
.gitignore                                (Task 3)
Dashboard.md                              (Task 12)
Weekly Review.md                          (Task 13)
00 Inbox/README.md                        (Task 1)
10 Projects/README.md                     (Task 1)
20 Areas/README.md                        (Task 1)
30 Resources/README.md                    (Task 1)
30 Resources/GTD System.md                (Task 2)
40 Archive/README.md                      (Task 1)
Journal/README.md                         (Task 1)
People/README.md                          (Task 1)
Meetings/README.md                        (Task 1)
_templates/Project.md                     (Task 4)
_templates/Daily Note.md                  (Task 4)
_templates/Person.md                      (Task 4)
_templates/Meeting.md                     (Task 4)
_templates/Weekly Review.md               (Task 4)
.obsidian/app.json                        (Task 3)
.obsidian/core-plugins.json               (Task 3)
.obsidian/templates.json                  (Task 3)
.obsidian/daily-notes.json                (Task 3)
.obsidian/community-plugins.json          (Task 3)
.claude/skills/gtd-capture/SKILL.md       (Task 5)
.claude/skills/gtd-process-inbox/SKILL.md (Task 6)
.claude/skills/gtd-next-actions/SKILL.md  (Task 7)
.claude/skills/gtd-weekly-review/SKILL.md (Task 8)
.claude/skills/gtd-dashboard/SKILL.md     (Task 9)
.claude/hooks/gtd-status.sh               (Task 10)
.claude/hooks/test_gtd-status.sh          (Task 10)
.claude/settings.json                     (Task 11)
docs/gtd/html-dashboard.md                (Task 14)
cli/brain                                 (Task 15 — executable entrypoint)
cli/gtdlib.py                             (Task 15)
cli/gtd_capture.py                        (Task 15)
cli/gtd_query.py                          (Tasks 16–18)
cli/tests/test_gtdlib.py                  (Task 15)
cli/tests/test_capture.py                 (Task 15)
cli/tests/test_query.py                   (Tasks 16–18)
cli/tests/conftest.py                     (Task 15)
cli/README.md                             (Task 19)
docs/gtd/obsidian-plugins.md              (Task 20)
docs/gtd/connectors.md                    (Task 22 — optional)
```

---

## Phase 0 — Foundations & conventions

### Task 1: Vault folder structure + guide notes

**Files:**
- Create: `00 Inbox/README.md`, `10 Projects/README.md`, `20 Areas/README.md`, `30 Resources/README.md`, `40 Archive/README.md`, `Journal/README.md`, `People/README.md`, `Meetings/README.md`

Each `README.md` doubles as a `.gitkeep` (so the otherwise-empty folder is tracked) and a human-readable explanation of the folder's GTD role.

- [ ] **Step 1: Create the eight folders and their guide notes**

Write each file with the exact content below.

`00 Inbox/README.md`:
```markdown
# 📥 Inbox
Single capture point. Dump anything here — thoughts, tasks, links, notes — without organizing.
Process to empty with `/gtd-process-inbox`. Should trend toward zero.
```
`10 Projects/README.md`:
```markdown
# 📋 Projects
One note per project: any outcome that needs more than one action. Use `_templates/Project.md`.
Every active project should have at least one `#next` action. See `30 Resources/GTD System.md`.
```
`20 Areas/README.md`:
```markdown
# 🗂️ Areas
Ongoing responsibilities with no end date (Health, Finances, a role). Standards to maintain,
not outcomes to finish. Projects can link to an area via `area:` frontmatter.
```
`30 Resources/README.md`:
```markdown
# 📚 Resources
Reference material worth keeping — notes, docs, checklists. The GTD manual lives here:
`30 Resources/GTD System.md`.
```
`40 Archive/README.md`:
```markdown
# 🗄️ Archive
Completed projects and anything no longer active. Nothing is deleted — it's moved here so the
active folders stay clean.
```
`Journal/README.md`:
```markdown
# 🗓️ Journal
Daily notes: a running log, the day's quick captures, and calendar. Use `_templates/Daily Note.md`.
Weekly review notes are tagged `#weekly-review` and live here.
```
`People/README.md`:
```markdown
# 👥 People
One note per person — for delegation, waiting-for items, and agendas.
Link from tasks: `#agenda [[Person Name]]`. Use `_templates/Person.md`.
```
`Meetings/README.md`:
```markdown
# 🤝 Meetings
Meeting notes. Capture decisions and action items as `#next` tasks so they flow to the dashboard.
Use `_templates/Meeting.md`.
```

- [ ] **Step 2: Verify all eight folders and notes exist**

Run: `for d in "00 Inbox" "10 Projects" "20 Areas" "30 Resources" "40 Archive" Journal People Meetings; do test -f "$d/README.md" && echo "OK $d" || echo "MISSING $d"; done`
Expected: eight `OK` lines, no `MISSING`.

- [ ] **Step 3: Commit**

```bash
git add "00 Inbox" "10 Projects" "20 Areas" "30 Resources" "40 Archive" Journal People Meetings
git commit -m "feat: add GTD vault folder structure with guide notes"
```

---

### Task 2: GTD conventions manual

**Files:**
- Create: `30 Resources/GTD System.md`

This is the single source of truth every skill, the hook, and the CLI reference. It must document exactly the tags, fields, and frontmatter listed in Global Constraints.

- [ ] **Step 1: Write `30 Resources/GTD System.md`**

Content — write it verbatim:
```markdown
---
type: reference
tags: [system, gtd]
---

# GTD System — How This Vault Works

This vault is a Getting Things Done system built in Obsidian. It uses PARA-style folders for
*where things live* and tags + frontmatter for *what state things are in*. The dashboards are
built on the Dataview plugin, so the conventions below are what make the queries work.

## The five GTD steps → where they happen

| Step | Where |
| --- | --- |
| Capture | `00 Inbox/` — one entry point. `/gtd-capture` |
| Clarify | `/gtd-process-inbox` walks each item through the decision tree |
| Organize | Items move to Projects / Areas / Resources, or become tasks |
| Reflect | `/gtd-weekly-review` + `Weekly Review.md` |
| Engage | `Dashboard.md` and `/gtd-next-actions` |

## Folders (PARA)

- `00 Inbox/` — unprocessed capture. Trends toward empty.
- `10 Projects/` — one note per project (an outcome needing >1 action). Active work.
- `20 Areas/` — ongoing responsibilities with no end date.
- `30 Resources/` — reference material (this file lives here).
- `40 Archive/` — completed/inactive; nothing deleted.
- `Journal/` — daily notes.
- `People/` — one note per person (delegation, waiting-for, agendas).
- `Meetings/` — meeting notes.

## Tasks — the conventions that power the dashboards

Actions are markdown checkboxes inside the relevant project or daily note. Metadata rides along
as tags and Dataview inline fields (`[field:: value]`).

    - [ ] Draft the Q3 proposal #next #computer [due:: 2026-09-20] [[Project - Q3 Proposal]]
    - [ ] Waiting on Sam to send figures #waiting [[Sam Rivera]] [since:: 2026-09-08]
    - [ ] Someday: learn to sail #someday

Context tags (pick one per action): `#computer` `#phone` `#errands` `#home` `#office`
`#anywhere` `#agenda` (pair `#agenda` with `[[Person]]`).

Status tags: `#next` (a next action, ready now — this is what the dashboard shows),
`#waiting` (delegated/blocked; pair with `[[Person]]` and `[since:: YYYY-MM-DD]`),
`#someday` (not committed yet).

Inline fields: `[due:: YYYY-MM-DD]` (deadline), `[scheduled:: YYYY-MM-DD]` (do-date/tickler),
`[since:: YYYY-MM-DD]` (when a `#waiting` item started).

Rule of thumb: every active project should have at least one `#next` action.

## Project note frontmatter

    ---
    type: project
    status: active        # active | someday | done
    area: "[[Career]]"    # optional link into 20 Areas
    created: 2026-09-09
    review: 2026-09-16    # next review date
    ---

## People note frontmatter

    ---
    type: person
    tags: [person]
    ---

## Required plugin

Dataview (community plugin) powers `Dashboard.md`. Install via Settings → Community plugins →
Browse → "Dataview", then enable. The `/gtd-dashboard` skill can also publish a standalone HTML
snapshot that needs no plugin.
```

- [ ] **Step 2: Verify the file has valid frontmatter and documents every constraint token**

Run: `head -4 "30 Resources/GTD System.md" | grep -q '^---' && for t in '#computer' '#next' '#waiting' '#someday' 'due::' 'scheduled::' 'since::' 'status:'; do grep -q "$t" "30 Resources/GTD System.md" && echo "OK $t" || echo "MISSING $t"; done`
Expected: all `OK`, no `MISSING`.

- [ ] **Step 3: Commit**

```bash
git add "30 Resources/GTD System.md"
git commit -m "docs: add GTD conventions manual (tags, fields, frontmatter)"
```

---

### Task 3: Obsidian vault config + .gitignore

**Files:**
- Create: `.obsidian/app.json`, `.obsidian/core-plugins.json`, `.obsidian/templates.json`, `.obsidian/daily-notes.json`, `.obsidian/community-plugins.json`, `.gitignore`

**Interfaces:**
- Produces: templates folder is `_templates` (Task 4 depends on this); daily-notes folder is `Journal` with template `_templates/Daily Note.md`; new files default into `00 Inbox`.

- [ ] **Step 1: Write the `.obsidian` config files**

`.obsidian/app.json`:
```json
{
  "alwaysUpdateLinks": true,
  "newFileLocation": "folder",
  "newFileFolderPath": "00 Inbox",
  "attachmentFolderPath": "30 Resources/attachments",
  "useMarkdownLinks": false
}
```
`.obsidian/core-plugins.json`:
```json
{
  "file-explorer": true,
  "global-search": true,
  "switcher": true,
  "graph": true,
  "backlink": true,
  "outgoing-link": true,
  "tag-pane": true,
  "properties": true,
  "daily-notes": true,
  "templates": true,
  "note-composer": true,
  "command-palette": true,
  "editor-status": true,
  "bookmarks": true,
  "outline": true,
  "word-count": true
}
```
`.obsidian/templates.json`:
```json
{
  "folder": "_templates",
  "dateFormat": "YYYY-MM-DD",
  "timeFormat": "HH:mm"
}
```
`.obsidian/daily-notes.json`:
```json
{
  "folder": "Journal",
  "format": "YYYY-MM-DD",
  "template": "_templates/Daily Note.md"
}
```
`.obsidian/community-plugins.json`:
```json
[]
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Obsidian per-machine state (keep shared config, ignore local workspace/cache)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
.obsidian/plugins/
.obsidian/themes/
.trash/

# OS cruft
.DS_Store
Thumbs.db

# Python
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Verify all JSON is valid**

Run: `for f in .obsidian/*.json; do python3 -c "import json;json.load(open('$f'))" && echo "OK $f" || echo "BAD $f"; done`
Expected: five `OK` lines, no `BAD`.

- [ ] **Step 4: Commit**

```bash
git add .obsidian .gitignore
git commit -m "feat: add Obsidian vault config and .gitignore"
```

---

### Task 4: Obsidian note templates

**Files:**
- Create: `_templates/Project.md`, `_templates/Daily Note.md`, `_templates/Person.md`, `_templates/Meeting.md`, `_templates/Weekly Review.md`

**Interfaces:**
- Consumes: templates folder configured as `_templates` in Task 3.
- Produces: `_templates/Project.md` etc. are referenced by name by the GTD skills (Tasks 6, 8) and the daily-notes config (Task 3). Template placeholders use Obsidian's core Templates syntax: `{{title}}`, `{{date:YYYY-MM-DD}}`, `{{date:dddd, MMMM D, YYYY}}`.

- [ ] **Step 1: Write the five templates**

`_templates/Project.md`:
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
`_templates/Daily Note.md`:
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
`_templates/Person.md`:
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
`_templates/Meeting.md`:
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
`_templates/Weekly Review.md`:
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

- [ ] **Step 2: Verify each template has frontmatter and at least one task or placeholder**

Run: `for f in _templates/*.md; do head -1 "$f" | grep -q '^---' && echo "OK $f" || echo "BAD $f"; done`
Expected: five `OK` lines.

- [ ] **Step 3: Commit**

```bash
git add _templates
git commit -m "feat: add Obsidian note templates for projects, dailies, people, meetings, reviews"
```

---

## Phase 1 — GTD skills

> All skills in this phase follow the same shape: a `SKILL.md` with frontmatter (`name`, `description`) plus a body. The `description` must start with "Use when…" and include trigger phrases so Claude auto-selects it. After writing each skill, verify frontmatter with the check in each task's verification step.

### Task 5: `gtd-capture` skill

**Files:**
- Create: `.claude/skills/gtd-capture/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: gtd-capture
description: Use when the user wants to quickly capture a thought, task, idea, link, or note into their GTD second brain without organizing it yet. Triggers on "capture", "add to inbox", "jot down", "remind me to", "note that".
---

# GTD Capture

Friction-free capture into `00 Inbox/`. The goal is speed. Do not organize, clarify, or ask where
it should go — that is `/gtd-process-inbox`'s job.

## Steps
1. Write what the user said to a new markdown file in `00 Inbox/`.
2. Filename: short slug + today's date, e.g. `00 Inbox/2026-09-09 call-dentist.md`.
3. Contents: raw capture; a checkbox if it's clearly an action, plain text otherwise:
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
- Keep the response to a single confirmation line.
```

- [ ] **Step 2: Verify frontmatter**

Run: `python3 -c "import re,sys; t=open('.claude/skills/gtd-capture/SKILL.md').read(); m=re.match(r'^---\n(.*?)\n---', t, re.S); assert m and 'name: gtd-capture' in m.group(1) and 'description:' in m.group(1); print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-capture
git commit -m "feat: add gtd-capture skill"
```

---

### Task 6: `gtd-process-inbox` skill

**Files:**
- Create: `.claude/skills/gtd-process-inbox/SKILL.md`

**Interfaces:**
- Consumes: conventions in `30 Resources/GTD System.md` (Task 2); `_templates/Project.md` (Task 4).

- [ ] **Step 1: Write the skill**

```markdown
---
name: gtd-process-inbox
description: Use when the user wants to process, clarify, or empty their GTD inbox — walking each captured item through the GTD decision tree and filing it. Triggers on "process inbox", "clarify", "empty my inbox", "clear the inbox".
---

# GTD Process Inbox (Clarify & Organize)

Walk every item in `00 Inbox/` through the GTD clarify workflow until the inbox is empty.
Read `30 Resources/GTD System.md` first.

## Process
Take files in `00 Inbox/` (ignore `README.md`) one at a time, oldest first. For each, apply the
decision tree, confirming with the user before moving files:

1. Actionable?
   - No, trash → delete the file.
   - No, reference → move into `30 Resources/` (or `20 Areas/`) with `type: reference`.
   - No, someday → `status: someday` project in `10 Projects/`, or a `#someday` task.
2. Actionable — one action or several?
   - Several (project) → new note in `10 Projects/` from `_templates/Project.md`; define outcome
     and at least one `#next` action.
   - One action: <2 min → do it now, then delete the item; delegate → `#waiting` + `[[Person]]` +
     `[since:: today]`; defer → `#next` + context tag, in the right project (or `[scheduled:: DATE]`).
3. Remove the processed file from `00 Inbox/` once filed.

## Rules
- End state is an empty inbox (only `README.md`). Say so when done.
- Confirm before deleting anything the user might want.
- Every touched project ends with at least one `#next` action.
```

- [ ] **Step 2: Verify frontmatter** — same command as Task 5 Step 2 with path `.claude/skills/gtd-process-inbox/SKILL.md`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-process-inbox
git commit -m "feat: add gtd-process-inbox skill"
```

---

### Task 7: `gtd-next-actions` skill

**Files:**
- Create: `.claude/skills/gtd-next-actions/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: gtd-next-actions
description: Use when the user asks what to work on now, wants their next actions, or filters tasks by context/time/energy. Triggers on "what should I do", "next actions", "what's on my list", "what can I do at my computer", "what's due".
---

# GTD Next Actions (Engage)

Help the user decide what to do now. Read `30 Resources/GTD System.md` for conventions.

## Steps
1. Gather open `#next` tasks (unchecked, not `#waiting`) across `00 Inbox/`, `10 Projects/`,
   `20 Areas/`, `Journal/`, `People/`, `Meetings/` (skip `40 Archive/`, `_templates/`, and the
   reference docs). Use Grep.
2. Hide items whose `[scheduled:: DATE]` is in the future.
3. If given a context (`@computer`, "phone", "errands"), filter to that context tag. If given
   time/energy, prefer short/low-effort items and say why.
4. Show due/overdue (`[due:: DATE]`) first, then group by context. Each line: action, its project
   (from `[[link]]`), due date.
5. Keep to a scannable 5–10 item shortlist. Offer to check one off or start one.

## Rules
- Read-first; only modify the vault if the user asks to check something off.
- Never invent tasks. If nothing is queued, suggest `/gtd-process-inbox` or `/gtd-weekly-review`.
```

- [ ] **Step 2: Verify frontmatter** — same command, path `.claude/skills/gtd-next-actions/SKILL.md`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-next-actions
git commit -m "feat: add gtd-next-actions skill"
```

---

### Task 8: `gtd-weekly-review` skill

**Files:**
- Create: `.claude/skills/gtd-weekly-review/SKILL.md`

**Interfaces:**
- Consumes: `_templates/Weekly Review.md` (Task 4); writes a `Journal/` note tagged `#weekly-review` that the hook (Task 10) reads for recency.

- [ ] **Step 1: Write the skill**

```markdown
---
name: gtd-weekly-review
description: Use when the user wants to do their GTD weekly review — the recurring ritual to get clear, current, and creative. Triggers on "weekly review", "review my week", "gtd review", "do my review".
---

# GTD Weekly Review (Reflect)

Guide the user through the review interactively, updating the vault as you go. Full checklist in
`Weekly Review.md`. Read `30 Resources/GTD System.md` for conventions.

## Process
### 1. Get Clear
- Process `00 Inbox/` to empty (`/gtd-process-inbox`).
- Prompt a brain-dump; capture and process it.
### 2. Get Current
- Projects: open each `status: active` note in `10 Projects/`; ensure a concrete `#next` action;
  bump its `review:` date +7 days.
- Waiting For: list `#waiting` tasks; flag stale `[since::]` dates; offer follow-ups.
- Calendar/Journal: review the past week and the next two weeks.
- People: skim `People/` for pending agendas.
### 3. Get Creative
- Review `status: someday` projects and `#someday` tasks; promote any that are ready.
- Review `20 Areas/`. Archive finished projects (`status: done` → `40 Archive/`).

## Finish
- Create a review note in `Journal/` from `_templates/Weekly Review.md`, tagged `#weekly-review`,
  summarizing changes and carry-overs. (The SessionStart hook reads this for review recency.)
- Offer to refresh the dashboard (`/gtd-dashboard`).

## Rules
- Confirm before deleting/archiving. Definition of done: inbox empty, every active project has a
  next action, review note written.
```

- [ ] **Step 2: Verify frontmatter** — same command, path `.claude/skills/gtd-weekly-review/SKILL.md`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/gtd-weekly-review
git commit -m "feat: add gtd-weekly-review skill"
```

---

### Task 9: `gtd-dashboard` skill (HTML snapshot)

**Files:**
- Create: `.claude/skills/gtd-dashboard/SKILL.md`

**Interfaces:**
- Consumes: conventions (Task 2). Produces the published HTML Artifact described in Task 14's doc.

- [ ] **Step 1: Write the skill**

```markdown
---
name: gtd-dashboard
description: Use when the user wants a visual dashboard of their GTD second brain published as a shareable HTML page/artifact (not the live in-Obsidian Dataview view). Triggers on "dashboard", "show me my system", "gtd overview", "publish my dashboard".
---

# GTD Dashboard (HTML snapshot)

Publishes a read-only visual snapshot of the GTD system as an Artifact. Complements the live
`Dashboard.md` (which needs Dataview). Read `30 Resources/GTD System.md` first.

## Steps
1. Gather data with Grep/Read (skip `40 Archive/`, `_templates/`, reference docs):
   inbox count; active projects (title, area, review date, whether each has a `#next`); next
   actions grouped by context; waiting-for (`#waiting` + `[[person]]` + `[since::]`); due-soon
   (`[due::]` within 7 days, mark overdue); someday counts.
2. Build the page: load the `artifact-design` skill, then write one self-contained theme-aware,
   responsive HTML file — a KPI row (inbox / active projects / next actions / waiting) plus columns
   for Next Actions by context, Waiting For, Projects (flag those with no next action / overdue
   review), Due Soon. If you show a chart, load `dataviz` first.
3. Publish with the Artifact tool. Title "GTD Dashboard". Give the user the link; on refresh,
   redeploy to the same file path for a stable URL.

## Rules
- Point-in-time snapshot — say so, include the generation date; live view is `Dashboard.md`.
- Read-only. Every number comes from the files; never estimate.
```

- [ ] **Step 2: Verify frontmatter** — same command, path `.claude/skills/gtd-dashboard/SKILL.md`. Expected: `OK`.

- [ ] **Step 3: Verify all five GTD skills are discoverable (name == dir)**

Run: `for s in gtd-capture gtd-process-inbox gtd-next-actions gtd-weekly-review gtd-dashboard; do grep -q "name: $s" ".claude/skills/$s/SKILL.md" && echo "OK $s" || echo "BAD $s"; done`
Expected: five `OK` lines.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/gtd-dashboard
git commit -m "feat: add gtd-dashboard skill (HTML snapshot)"
```

---

## Phase 2 — SessionStart hook

### Task 10: Hook script + shell test

**Files:**
- Create: `.claude/hooks/gtd-status.sh`, `.claude/hooks/test_gtd-status.sh`

**Interfaces:**
- Produces: an executable that prints a GTD brief to stdout; consumes `CLAUDE_PROJECT_DIR` env var (falls back to deriving the vault root from its own path). Reads only. Wired into `settings.json` in Task 11.

> This is real code — use TDD. Write the test first with a temp fixture vault, watch it fail, then implement.

- [ ] **Step 1: Write the failing test `.claude/hooks/test_gtd-status.sh`**

```bash
#!/usr/bin/env bash
# Self-contained test: builds a fixture vault in a temp dir, runs the hook, asserts on output.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gtd-status.sh"
fail=0
assert_contains() { grep -qF "$2" <<<"$1" && echo "OK  $3" || { echo "FAIL $3"; fail=1; }; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/00 Inbox" "$TMP/10 Projects" "$TMP/Journal"
echo "- [ ] loose thing" > "$TMP/00 Inbox/thing.md"
cat > "$TMP/10 Projects/P.md" <<'EOF'
---
type: project
status: active
---
- [ ] Pick a static site generator #next #computer [due:: 2026-09-15] [[P]]
- [ ] Wait on domain #waiting [[Reg]] [since:: 2026-09-02]
EOF

out="$(CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK")"
assert_contains "$out" "Inbox: 1" "inbox count"
assert_contains "$out" "1 active project" "active project count"
assert_contains "$out" "Pick a static site generator" "next action surfaced"
grep -q "Wait on domain" <<<"$out" && { echo "FAIL waiting excluded"; fail=1; } || echo "OK  waiting excluded from next actions"
assert_contains "$out" "No weekly review" "review recency (none yet)"

# Empty-vault safety
EMPTY="$(mktemp -d)"; out2="$(CLAUDE_PROJECT_DIR="$EMPTY" bash "$HOOK")"; rm -rf "$EMPTY"
assert_contains "$out2" "Inbox: 0" "empty vault inbox 0"

exit $fail
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `chmod +x .claude/hooks/test_gtd-status.sh && bash .claude/hooks/test_gtd-status.sh`
Expected: FAIL (hook script does not exist yet — `bash: gtd-status.sh: No such file`).

- [ ] **Step 3: Implement `.claude/hooks/gtd-status.sh`**

```bash
#!/usr/bin/env bash
# SessionStart hook: prints a short GTD brief. Read-only; safe on an empty vault.
set -uo pipefail

if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then VAULT="$CLAUDE_PROJECT_DIR"
else VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; fi
cd "$VAULT" 2>/dev/null || exit 0

inbox_count=0
if [[ -d "00 Inbox" ]]; then
  inbox_count=$(find "00 Inbox" -maxdepth 1 -type f -name '*.md' ! -name 'README.md' 2>/dev/null | wc -l | tr -d ' ')
fi

review_line="⚠️  No weekly review found yet — run /gtd-weekly-review"
if [[ -d "Journal" ]]; then
  last_review=$(grep -rl "weekly-review" "Journal" --include='*.md' 2>/dev/null | grep -v '/README.md$' | xargs -r ls -t 2>/dev/null | head -1)
  if [[ -n "$last_review" ]]; then
    now=$(date +%s); mtime=$(date -r "$last_review" +%s 2>/dev/null || echo "$now")
    days=$(( (now - mtime) / 86400 ))
    if (( days >= 7 )); then review_line="⚠️  Weekly review is ${days} days old — time for /gtd-weekly-review"
    else review_line="✅ Weekly review done ${days}d ago"; fi
  fi
fi

content_dirs=()
for d in "00 Inbox" "10 Projects" "20 Areas" "Journal" "People" "Meetings"; do [[ -d "$d" ]] && content_dirs+=("$d"); done
next_actions=""
if (( ${#content_dirs[@]} > 0 )); then
  next_actions=$(grep -rh '^[[:space:]]*- \[ \].*#next' "${content_dirs[@]}" --include='*.md' 2>/dev/null \
    | grep -v '#waiting' \
    | sed -E 's/^[[:space:]]*- \[ \][[:space:]]*//' \
    | sed -E 's/\[\[([^]]*)\]\]/\1/g' \
    | sed -E 's/\[[a-z]+:: ?[^]]*\]//g' \
    | sed -E 's/#[A-Za-z_-]+//g' \
    | sed -E 's/[[:space:]]+/ /g; s/^[[:space:]]//; s/[[:space:]]$//' \
    | grep -v '^$' | head -5)
fi

proj_count=0
if [[ -d "10 Projects" ]]; then
  proj_count=$(grep -rls 'status: active' "10 Projects" --include='*.md' 2>/dev/null | wc -l | tr -d ' ')
fi

echo "🧠 Second Brain — GTD status"
echo "📥 Inbox: ${inbox_count} item(s) to process   ·   📋 ${proj_count} active project(s)"
echo "$review_line"
if [[ -n "$next_actions" ]]; then
  echo "⚡ Next actions ready:"
  while IFS= read -r a; do echo "   • $a"; done <<< "$next_actions"
else
  echo "⚡ No #next actions queued — add some during processing or review."
fi
```

- [ ] **Step 4: Make executable and run the test to verify it passes**

Run: `chmod +x .claude/hooks/gtd-status.sh && bash .claude/hooks/test_gtd-status.sh; echo "exit=$?"`
Expected: all `OK` lines and `exit=0`.

- [ ] **Step 5: Lint the script**

Run: `bash -n .claude/hooks/gtd-status.sh && echo "syntax OK"` (and `shellcheck .claude/hooks/gtd-status.sh` if available; warnings acceptable, no errors).
Expected: `syntax OK`.

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/gtd-status.sh .claude/hooks/test_gtd-status.sh
git commit -m "feat: add read-only SessionStart GTD status hook with shell test"
```

---

### Task 11: Wire the hook into settings.json

**Files:**
- Create: `.claude/settings.json`

**Interfaces:**
- Consumes: `.claude/hooks/gtd-status.sh` (Task 10).

- [ ] **Step 1: Write `.claude/settings.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/gtd-status.sh\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify JSON and that it points at the hook**

Run: `python3 -c "import json;d=json.load(open('.claude/settings.json'));assert d['hooks']['SessionStart'][0]['hooks'][0]['command'].endswith('gtd-status.sh\"');print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: run GTD status hook on SessionStart"
```

---

## Phase 3 — Dashboards

### Task 12: Live Dataview dashboard

**Files:**
- Create: `Dashboard.md`

**Interfaces:**
- Consumes: the tag/field/frontmatter conventions from Task 2. Requires the Dataview plugin (documented in Task 20).

- [ ] **Step 1: Write `Dashboard.md`**

```markdown
---
type: dashboard
cssclasses: [dashboard]
---

# 🧠 Second Brain — Dashboard

> Live view. Requires the Dataview plugin. For a shareable snapshot, run `/gtd-dashboard`.

## 📥 Inbox
```dataview
LIST
FROM "00 Inbox"
SORT file.ctime ASC
```

## ⚡ Next Actions — by context
```dataview
TASK
WHERE !completed AND contains(tags, "#next")
WHERE !contains(tags, "#waiting")
WHERE !scheduled OR scheduled <= date(today)
GROUP BY filter(tags, (t) => t = "#computer" OR t = "#phone" OR t = "#errands" OR t = "#home" OR t = "#office" OR t = "#anywhere" OR t = "#agenda")[0] AS "Context"
SORT due ASC
```

## 🔥 Due soon (next 7 days)
```dataview
TASK
WHERE !completed AND due AND due <= date(today) + dur(7 days)
SORT due ASC
```

## ⏳ Waiting For
```dataview
TASK
WHERE !completed AND contains(tags, "#waiting")
SORT since ASC
```

## 📋 Active Projects
```dataview
TABLE status, area, review AS "Next review"
FROM "10 Projects"
WHERE type = "project" AND status = "active"
SORT review ASC
```

## 🗓️ Projects needing review
```dataview
TABLE review AS "Review due"
FROM "10 Projects"
WHERE type = "project" AND status = "active" AND review <= date(today)
SORT review ASC
```

## 💤 Someday / Maybe
```dataview
LIST
FROM "10 Projects"
WHERE type = "project" AND status = "someday"
```
```

> Note: the fenced ` ```dataview ` blocks are literal content of `Dashboard.md`. When copying from this plan, ensure the outer plan code-fence is stripped and the inner `dataview` fences remain intact.

- [ ] **Step 2: Verify the file contains the expected query blocks**

Run: `grep -c '```dataview' Dashboard.md`
Expected: `7`.

- [ ] **Step 3: Manual check (documented, not automated)**

Open the vault in Obsidian with Dataview enabled and confirm each section renders without a Dataview syntax error. Record the outcome in the task's review notes. (No sample data yet is fine — sections render empty.)

- [ ] **Step 4: Commit**

```bash
git add Dashboard.md
git commit -m "feat: add live Dataview dashboard"
```

---

### Task 13: Weekly Review runbook

**Files:**
- Create: `Weekly Review.md`

- [ ] **Step 1: Write `Weekly Review.md`**

```markdown
---
type: reference
tags: [system, gtd, review]
---

# 🔄 Weekly Review

Run once a week (`/gtd-weekly-review` walks you through it interactively).

## Get Clear
- [ ] Empty the inbox to zero (`/gtd-process-inbox`)
- [ ] Collect loose notes and mental clutter, then process
- [ ] Empty your head

## Get Current
- [ ] Review `Dashboard.md`; delete/complete stale next actions
- [ ] Review Active Projects — each has a `#next` action?
- [ ] Review Waiting For — chase stale `[since::]` items
- [ ] Review the calendar (past week + next two weeks)
- [ ] Review `People/` for agendas
- [ ] Bump `review:` dates on projects you touched

## Get Creative
- [ ] Review Someday/Maybe — promote anything ready
- [ ] Review `20 Areas/`
- [ ] Archive completed projects to `40 Archive/`

---

## Review log
```dataview
TABLE file.ctime AS "Reviewed"
FROM "Journal"
WHERE contains(tags, "weekly-review")
SORT file.ctime DESC
LIMIT 8
```
```

- [ ] **Step 2: Verify** — Run: `grep -q 'weekly-review' "Weekly Review.md" && grep -q '```dataview' "Weekly Review.md" && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add "Weekly Review.md"
git commit -m "docs: add weekly review runbook"
```

---

### Task 14: HTML dashboard doc (the "website" surface)

The HTML dashboard is produced at runtime by the `gtd-dashboard` skill (Task 9) publishing an Artifact — there is no static site to build. This task documents that surface so it's discoverable and repeatable.

**Files:**
- Create: `docs/gtd/html-dashboard.md`

- [ ] **Step 1: Write `docs/gtd/html-dashboard.md`**

```markdown
# HTML Dashboard (shareable snapshot)

The second brain has two dashboards:

| | Live dashboard | HTML snapshot |
| --- | --- | --- |
| File | `Dashboard.md` | published Artifact (URL) |
| Engine | Dataview plugin, inside Obsidian | `/gtd-dashboard` skill, rendered by Claude |
| Updates | live as you edit notes | point-in-time when you run the skill |
| Needs | Obsidian + Dataview | nothing (opens in a browser) |
| Use it for | daily driving | sharing, reviewing away from Obsidian |

## Generating the snapshot
Run `/gtd-dashboard` in Claude Code. It reads the vault, builds a theme-aware responsive HTML page
(KPI row + Next Actions by context + Waiting For + Projects + Due Soon), and publishes it as an
Artifact. Re-running redeploys to the same URL.

## What it shows
- KPIs: inbox count, active projects, open next actions, waiting-for count.
- Next actions grouped by context.
- Projects, flagging any with no `#next` action or an overdue `review:` date.
- Items due within 7 days (overdue highlighted).

The snapshot is read-only and never modifies the vault.
```

- [ ] **Step 2: Verify** — Run: `test -f docs/gtd/html-dashboard.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/gtd/html-dashboard.md
git commit -m "docs: document the HTML dashboard snapshot surface"
```

---

## Phase 4 — CLI (`brain`)

> Real code — strict TDD (pytest). The CLI is stdlib-only (no pip installs), operates on the vault markdown, and shares the same conventions as everything else. Run tests from the repo root with `python3 -m pytest cli/tests -q`.

### Task 15: CLI core library + `capture` command

**Files:**
- Create: `cli/gtdlib.py`, `cli/gtd_capture.py`, `cli/brain`, `cli/tests/conftest.py`, `cli/tests/test_gtdlib.py`, `cli/tests/test_capture.py`

**Interfaces:**
- Produces (consumed by Tasks 16–18):
  - `gtdlib.find_vault(start: Path) -> Path` — walks up from `start` to the dir containing `30 Resources/GTD System.md`; raises `FileNotFoundError` if none.
  - `gtdlib.Task` dataclass: `text: str`, `tags: list[str]`, `fields: dict[str,str]`, `links: list[str]`, `source: Path`, `done: bool`.
  - `gtdlib.parse_tasks(md: str, source: Path) -> list[Task]` — parses `- [ ]` / `- [x]` lines, extracting `#tags`, `[k:: v]` fields, and `[[links]]`.
  - `gtdlib.iter_tasks(vault: Path, dirs: list[str]) -> Iterator[Task]` — parses all `.md` under the given content dirs (excluding `README.md`).
  - `gtd_capture.capture(vault: Path, text: str, today: str) -> Path` — writes a new inbox file and returns its path.

- [ ] **Step 1: Write `cli/tests/conftest.py` (fixture vault)**

```python
import textwrap
from pathlib import Path
import pytest

@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / "30 Resources").mkdir()
    (tmp_path / "30 Resources" / "GTD System.md").write_text("# GTD System\n")
    for d in ["00 Inbox", "10 Projects", "20 Areas", "Journal", "People", "Meetings", "40 Archive"]:
        (tmp_path / d).mkdir()
    (tmp_path / "10 Projects" / "P.md").write_text(textwrap.dedent("""\
        ---
        type: project
        status: active
        ---
        - [ ] Pick a static site generator #next #computer [due:: 2026-09-15] [[P]]
        - [ ] Wait on domain #waiting [[Reg]] [since:: 2026-09-02]
        - [x] Done thing #next
    """))
    return tmp_path
```

- [ ] **Step 2: Write failing tests `cli/tests/test_gtdlib.py`**

```python
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gtdlib

def test_find_vault_from_subdir(vault):
    assert gtdlib.find_vault(vault / "10 Projects") == vault

def test_find_vault_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        gtdlib.find_vault(tmp_path)

def test_parse_tasks_extracts_metadata(vault):
    md = (vault / "10 Projects" / "P.md").read_text()
    tasks = gtdlib.parse_tasks(md, vault / "10 Projects" / "P.md")
    open_next = [t for t in tasks if "#next" in t.tags and not t.done]
    assert any(t.text.startswith("Pick a static site generator") for t in open_next)
    t = next(t for t in open_next if "static site" in t.text)
    assert "#computer" in t.tags
    assert t.fields["due"] == "2026-09-15"
    assert "P" in t.links

def test_iter_tasks_skips_archive_and_readme(vault):
    (vault / "40 Archive" / "old.md").write_text("- [ ] archived #next\n")
    (vault / "10 Projects" / "README.md").write_text("- [ ] guide #next\n")
    texts = [t.text for t in gtdlib.iter_tasks(vault, ["10 Projects", "40 Archive"])]
    assert not any("archived" in x for x in texts)
    assert not any("guide" in x for x in texts)
```

- [ ] **Step 3: Run to verify failure**

Run: `python3 -m pytest cli/tests/test_gtdlib.py -q`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'gtdlib'`.

- [ ] **Step 4: Implement `cli/gtdlib.py`**

```python
"""Vault helpers for the `brain` CLI. Standard library only."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

TASK_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<body>.*)$")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)")
FIELD_RE = re.compile(r"\[([a-z][a-z0-9_-]*)::\s*([^\]]*)\]")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

@dataclass
class Task:
    text: str
    tags: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    source: Path | None = None
    done: bool = False

def find_vault(start: Path) -> Path:
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / "30 Resources" / "GTD System.md").exists():
            return d
    raise FileNotFoundError("Not inside a GTD vault (no '30 Resources/GTD System.md' found)")

def parse_tasks(md: str, source: Path) -> list[Task]:
    tasks: list[Task] = []
    for line in md.splitlines():
        m = TASK_RE.match(line)
        if not m:
            continue
        body = m.group("body")
        tags = [f"#{t}" for t in TAG_RE.findall(body)]
        fields = {k: v.strip() for k, v in FIELD_RE.findall(body)}
        links = LINK_RE.findall(body)
        text = body
        text = FIELD_RE.sub("", text)
        text = LINK_RE.sub("", text)
        text = TAG_RE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        tasks.append(Task(text=text, tags=tags, fields=fields, links=links,
                          source=source, done=m.group("mark").lower() == "x"))
    return tasks

def iter_tasks(vault: Path, dirs: list[str]) -> Iterator[Task]:
    for d in dirs:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            yield from parse_tasks(p.read_text(encoding="utf-8"), p)
```

- [ ] **Step 5: Run to verify `test_gtdlib.py` passes**

Run: `python3 -m pytest cli/tests/test_gtdlib.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Write failing test `cli/tests/test_capture.py`**

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gtd_capture

def test_capture_writes_inbox_file(vault):
    p = gtd_capture.capture(vault, "Call the dentist", today="2026-09-09")
    assert p.parent == vault / "00 Inbox"
    assert p.suffix == ".md"
    text = p.read_text()
    assert "Call the dentist" in text
    assert "captured: 2026-09-09" in text
    assert "2026-09-09" in p.name

def test_capture_slug_and_uniqueness(vault):
    a = gtd_capture.capture(vault, "Same idea", today="2026-09-09")
    b = gtd_capture.capture(vault, "Same idea", today="2026-09-09")
    assert a != b  # no collision
```

- [ ] **Step 7: Run to verify failure**

Run: `python3 -m pytest cli/tests/test_capture.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gtd_capture'`.

- [ ] **Step 8: Implement `cli/gtd_capture.py`**

```python
"""Capture command: write a raw item into 00 Inbox/."""
from __future__ import annotations
import re
from pathlib import Path

def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return (s[:40] or "note")

def capture(vault: Path, text: str, today: str) -> Path:
    inbox = vault / "00 Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    base = f"{today} {_slug(text)}"
    path = inbox / f"{base}.md"
    n = 2
    while path.exists():
        path = inbox / f"{base}-{n}.md"
        n += 1
    is_action = text.rstrip().endswith(("!", ".")) is False and len(text.split()) <= 20
    body = f"- [ ] {text}" if is_action else text
    path.write_text(f"---\ntype: inbox\ncaptured: {today}\n---\n\n{body}\n", encoding="utf-8")
    return path
```

- [ ] **Step 9: Run to verify `test_capture.py` passes**

Run: `python3 -m pytest cli/tests/test_capture.py -q`
Expected: PASS (2 passed).

- [ ] **Step 10: Write the `cli/brain` entrypoint (capture subcommand only for now)**

```python
#!/usr/bin/env python3
"""`brain` — a small CLI for the GTD second brain. Standard library only."""
from __future__ import annotations
import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gtdlib
import gtd_capture

def _today() -> str:
    return _dt.date.today().isoformat()

def cmd_capture(args, vault: Path) -> int:
    text = " ".join(args.text).strip()
    if not text:
        print("nothing to capture", file=sys.stderr)
        return 1
    p = gtd_capture.capture(vault, text, today=_today())
    print(f"📥 Captured to {p.relative_to(vault)}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="GTD second brain CLI")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture", help="capture an item into the inbox")
    c.add_argument("text", nargs="+")
    c.set_defaults(func=cmd_capture)
    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        vault = gtdlib.find_vault(Path.cwd())
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    return args.func(args, vault)

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 11: Make executable; smoke-test capture end to end**

Run:
```bash
chmod +x cli/brain
cd "$(git rev-parse --show-toplevel)" && python3 cli/brain capture "test from cli"
ls "00 Inbox" | grep -q "$(date +%F).*test-from-cli" && echo "SMOKE OK"
git checkout -- "00 Inbox" 2>/dev/null; find "00 Inbox" -name "*test-from-cli*" -delete
```
Expected: prints `📥 Captured to 00 Inbox/…`, then `SMOKE OK`; cleanup removes the test file.

- [ ] **Step 12: Commit**

```bash
git add cli
git commit -m "feat: add brain CLI core (gtdlib, capture) with pytest tests"
```

---

### Task 16: CLI `next` command

**Files:**
- Create: `cli/gtd_query.py`
- Modify: `cli/brain` (register `next` subcommand), `cli/tests/test_query.py`

**Interfaces:**
- Consumes: `gtdlib.iter_tasks`, `gtdlib.Task` (Task 15).
- Produces (consumed by Tasks 17–18): `gtd_query.next_actions(vault, context=None, today=None) -> list[Task]` — open `#next` tasks, excluding `#waiting`, excluding future `[scheduled::]`, optionally filtered to a context tag, sorted by `due` (missing due sorts last).

- [ ] **Step 1: Write failing test in `cli/tests/test_query.py`**

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gtd_query

CONTENT = ["00 Inbox", "10 Projects", "20 Areas", "Journal", "People", "Meetings"]

def test_next_actions_excludes_waiting_and_done(vault):
    res = gtd_query.next_actions(vault, today="2026-09-10")
    texts = [t.text for t in res]
    assert any("static site" in x for x in texts)
    assert not any("Wait on domain" in x for x in texts)
    assert not any("Done thing" in x for x in texts)

def test_next_actions_context_filter(vault):
    assert gtd_query.next_actions(vault, context="#computer", today="2026-09-10")
    assert gtd_query.next_actions(vault, context="#phone", today="2026-09-10") == []

def test_next_actions_hides_future_scheduled(vault):
    (vault / "10 Projects" / "S.md").write_text(
        "- [ ] later thing #next [scheduled:: 2999-01-01]\n")
    texts = [t.text for t in gtd_query.next_actions(vault, today="2026-09-10")]
    assert not any("later thing" in x for x in texts)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest cli/tests/test_query.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gtd_query'`.

- [ ] **Step 3: Implement `cli/gtd_query.py`**

```python
"""Query commands for the brain CLI."""
from __future__ import annotations
import datetime as _dt
from pathlib import Path
import gtdlib

CONTENT_DIRS = ["00 Inbox", "10 Projects", "20 Areas", "Journal", "People", "Meetings"]

def _today(today: str | None) -> _dt.date:
    return _dt.date.fromisoformat(today) if today else _dt.date.today()

def next_actions(vault: Path, context: str | None = None, today: str | None = None) -> list[gtdlib.Task]:
    day = _today(today)
    out: list[gtdlib.Task] = []
    for t in gtdlib.iter_tasks(vault, CONTENT_DIRS):
        if t.done or "#next" not in t.tags or "#waiting" in t.tags:
            continue
        sched = t.fields.get("scheduled")
        if sched:
            try:
                if _dt.date.fromisoformat(sched) > day:
                    continue
            except ValueError:
                pass
        if context and context not in t.tags:
            continue
        out.append(t)
    def sort_key(t: gtdlib.Task):
        due = t.fields.get("due")
        try:
            return (0, _dt.date.fromisoformat(due)) if due else (1, _dt.date.max)
        except ValueError:
            return (1, _dt.date.max)
    return sorted(out, key=sort_key)

def waiting(vault: Path) -> list[gtdlib.Task]:
    return [t for t in gtdlib.iter_tasks(vault, CONTENT_DIRS)
            if not t.done and "#waiting" in t.tags]
```

- [ ] **Step 4: Run to verify test passes**

Run: `python3 -m pytest cli/tests/test_query.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Register `next` in `cli/brain`**

Add to `cli/brain`: `import gtd_query` near the other imports, and inside `build_parser()` before `return p`:
```python
    n = sub.add_parser("next", help="show next actions")
    n.add_argument("--context", help="filter to a context tag, e.g. #computer or computer")
    n.set_defaults(func=cmd_next)
```
And add the handler above `build_parser`:
```python
def cmd_next(args, vault: Path) -> int:
    ctx = args.context
    if ctx and not ctx.startswith("#"):
        ctx = "#" + ctx
    tasks = gtd_query.next_actions(vault, context=ctx)
    if not tasks:
        print("No #next actions queued. Try `/gtd-process-inbox` or `/gtd-weekly-review`.")
        return 0
    for t in tasks:
        due = f"  📅 {t.fields['due']}" if "due" in t.fields else ""
        proj = f"  [{t.links[0]}]" if t.links else ""
        ctxs = " ".join(x for x in t.tags if x not in ("#next",))
        print(f"• {t.text}{proj}{due}  {ctxs}".rstrip())
    return 0
```

- [ ] **Step 6: Smoke-test**

Run: `cd "$(git rev-parse --show-toplevel)" && python3 cli/brain next`
Expected: either a bullet list of next actions, or the "No #next actions queued" message (both are valid depending on vault contents). No traceback.

- [ ] **Step 7: Commit**

```bash
git add cli
git commit -m "feat: add `brain next` command with context filter and tests"
```

---

### Task 17: CLI `inbox` command

**Files:**
- Modify: `cli/gtd_query.py` (add `inbox_items`), `cli/brain` (register `inbox`), `cli/tests/test_query.py` (add test)

**Interfaces:**
- Produces: `gtd_query.inbox_items(vault) -> list[Path]` — `.md` files in `00 Inbox/` excluding `README.md`, sorted by creation time.

- [ ] **Step 1: Add failing test to `cli/tests/test_query.py`**

```python
def test_inbox_items_excludes_readme(vault):
    (vault / "00 Inbox" / "README.md").write_text("# Inbox\n")
    (vault / "00 Inbox" / "a.md").write_text("- [ ] a\n")
    (vault / "00 Inbox" / "b.md").write_text("- [ ] b\n")
    names = [p.name for p in gtd_query.inbox_items(vault)]
    assert "README.md" not in names
    assert set(names) == {"a.md", "b.md"}
```

- [ ] **Step 2: Run to verify failure** — Run: `python3 -m pytest cli/tests/test_query.py::test_inbox_items_excludes_readme -q`. Expected: FAIL — `AttributeError: module 'gtd_query' has no attribute 'inbox_items'`.

- [ ] **Step 3: Implement `inbox_items` in `cli/gtd_query.py`**

```python
def inbox_items(vault: Path) -> list[Path]:
    inbox = vault / "00 Inbox"
    if not inbox.is_dir():
        return []
    items = [p for p in inbox.glob("*.md") if p.name != "README.md"]
    return sorted(items, key=lambda p: p.stat().st_ctime)
```

- [ ] **Step 4: Run to verify pass** — Run: `python3 -m pytest cli/tests/test_query.py -q`. Expected: PASS (all query tests).

- [ ] **Step 5: Register `inbox` in `cli/brain`**

In `build_parser()`:
```python
    i = sub.add_parser("inbox", help="list unprocessed inbox items")
    i.set_defaults(func=cmd_inbox)
```
Handler:
```python
def cmd_inbox(args, vault: Path) -> int:
    items = gtd_query.inbox_items(vault)
    if not items:
        print("📥 Inbox is empty.")
        return 0
    print(f"📥 {len(items)} item(s) to process:")
    for p in items:
        first = next((ln.strip() for ln in p.read_text().splitlines()
                      if ln.strip() and not ln.startswith(("-", "#")) or ln.startswith("- [ ]")), p.stem)
        print(f"• {first}  ({p.name})")
    return 0
```

- [ ] **Step 6: Smoke-test** — Run: `cd "$(git rev-parse --show-toplevel)" && python3 cli/brain inbox`. Expected: "📥 Inbox is empty." (no traceback).

- [ ] **Step 7: Commit**

```bash
git add cli
git commit -m "feat: add `brain inbox` command with test"
```

---

### Task 18: CLI `review` command (status summary)

**Files:**
- Modify: `cli/gtd_query.py` (add `review_status`), `cli/brain` (register `review`), `cli/tests/test_query.py` (add test)

**Interfaces:**
- Produces: `gtd_query.review_status(vault, today=None) -> dict` with keys `inbox` (int), `active_projects` (int), `waiting` (int), `next_count` (int), `last_review_days` (int | None).

- [ ] **Step 1: Add failing test to `cli/tests/test_query.py`**

```python
def test_review_status_counts(vault):
    s = gtd_query.review_status(vault, today="2026-09-10")
    assert s["active_projects"] == 1
    assert s["waiting"] == 1
    assert s["next_count"] == 1     # one open #next (the completed one excluded)
    assert s["last_review_days"] is None
```

- [ ] **Step 2: Run to verify failure** — Run: `python3 -m pytest cli/tests/test_query.py::test_review_status_counts -q`. Expected: FAIL — no attribute `review_status`.

- [ ] **Step 3: Implement `review_status` in `cli/gtd_query.py`**

```python
def _count_active_projects(vault: Path) -> int:
    d = vault / "10 Projects"
    if not d.is_dir():
        return 0
    n = 0
    for p in d.rglob("*.md"):
        if p.name == "README.md":
            continue
        if "status: active" in p.read_text(encoding="utf-8"):
            n += 1
    return n

def _last_review_days(vault: Path, today: _dt.date) -> int | None:
    j = vault / "Journal"
    if not j.is_dir():
        return None
    candidates = [p for p in j.rglob("*.md")
                  if p.name != "README.md" and "weekly-review" in p.read_text(encoding="utf-8")]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    mdate = _dt.date.fromtimestamp(newest.stat().st_mtime)
    return (today - mdate).days

def review_status(vault: Path, today: str | None = None) -> dict:
    day = _today(today)
    return {
        "inbox": len(inbox_items(vault)),
        "active_projects": _count_active_projects(vault),
        "waiting": len(waiting(vault)),
        "next_count": len(next_actions(vault, today=today)),
        "last_review_days": _last_review_days(vault, day),
    }
```

- [ ] **Step 4: Run to verify pass** — Run: `python3 -m pytest cli/tests -q`. Expected: PASS (whole suite green).

- [ ] **Step 5: Register `review` in `cli/brain`**

In `build_parser()`:
```python
    r = sub.add_parser("review", help="print a GTD status summary")
    r.set_defaults(func=cmd_review)
```
Handler:
```python
def cmd_review(args, vault: Path) -> int:
    s = gtd_query.review_status(vault)
    lr = s["last_review_days"]
    review = "never" if lr is None else f"{lr}d ago"
    print("🧠 GTD status")
    print(f"📥 inbox {s['inbox']} · 📋 active projects {s['active_projects']} · "
          f"⏳ waiting {s['waiting']} · ⚡ next {s['next_count']}")
    print(f"🔄 last weekly review: {review}")
    if lr is None or lr >= 7:
        print("→ time for /gtd-weekly-review")
    return 0
```

- [ ] **Step 6: Smoke-test** — Run: `cd "$(git rev-parse --show-toplevel)" && python3 cli/brain review`. Expected: a status block, no traceback.

- [ ] **Step 7: Commit**

```bash
git add cli
git commit -m "feat: add `brain review` status command with test"
```

---

### Task 19: CLI packaging & install docs

**Files:**
- Create: `cli/README.md`

- [ ] **Step 1: Run the full CLI suite to confirm green**

Run: `python3 -m pytest cli/tests -q`
Expected: all tests pass.

- [ ] **Step 2: Write `cli/README.md`**

```markdown
# `brain` — GTD second brain CLI

Terminal access to the vault. Python 3.9+; standard library only (no installs). Run any command
from inside the vault (it finds the root by locating `30 Resources/GTD System.md`).

## Commands
| Command | Does |
| --- | --- |
| `brain capture <text>` | Write an item to `00 Inbox/` |
| `brain next [--context computer]` | List next actions, optionally by context |
| `brain inbox` | List unprocessed inbox items |
| `brain review` | Print a GTD status summary |

## Install (optional convenience)
Put `cli/` on your PATH or add an alias:

    alias brain='python3 /path/to/second-brain/cli/brain'

## Tests
    python3 -m pytest cli/tests -q
```

- [ ] **Step 3: Verify** — Run: `test -f cli/README.md && echo OK`. Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add cli/README.md
git commit -m "docs: add brain CLI README"
```

---

## Phase 5 — External plugins & top-level docs

### Task 20: External Obsidian plugins guide

**Files:**
- Create: `docs/gtd/obsidian-plugins.md`

- [ ] **Step 1: Write `docs/gtd/obsidian-plugins.md`**

```markdown
# Obsidian plugins for this vault

## Required
### Dataview — powers `Dashboard.md`
1. Settings → Community plugins → turn off Restricted mode (first time only).
2. Browse → search "Dataview" → Install → Enable.
3. Reopen `Dashboard.md`; the query blocks now render.
Without Dataview, `Dashboard.md` shows the raw ```dataview code blocks. Use `/gtd-dashboard`
(the HTML snapshot) if you don't want to install a plugin.

## Recommended (optional)
- **Tasks** — richer task querying, recurring tasks, due-date pickers. Compatible with our
  checkbox conventions; the emoji-date syntax is an alternative to `[due:: ]`.
- **Calendar** — a month view that ties into `Journal/` daily notes.
- **Templater** — more powerful templates than core Templates (dynamic dates, prompts). Our
  `_templates/` use core-Templates syntax and work without it.

## Core plugins already enabled
Templates (folder `_templates`), Daily notes (folder `Journal`, template `_templates/Daily Note.md`),
Properties, Tag pane, Backlinks, Outgoing links, Graph — see `.obsidian/core-plugins.json`.
```

- [ ] **Step 2: Verify** — Run: `grep -q 'Dataview' docs/gtd/obsidian-plugins.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/gtd/obsidian-plugins.md
git commit -m "docs: add Obsidian plugins guide (Dataview required)"
```

---

### Task 21: Rewrite top-level README

**Files:**
- Modify: `README.md` (currently the two-line stub)

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# 🧠 Second Brain

A template for a GTD (Getting Things Done) second brain, built as an Obsidian vault and operated
with Claude Code. Plain markdown all the way down — your data outlives any single tool.

## What's inside
| Surface | What it does |
| --- | --- |
| Vault structure | PARA-style folders (`00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`, `40 Archive`) plus `Journal`, `People`, `Meetings`. GTD state lives in tags + frontmatter. |
| GTD skills | `/gtd-capture`, `/gtd-process-inbox`, `/gtd-next-actions`, `/gtd-weekly-review`, `/gtd-dashboard`. |
| SessionStart hook | Each Claude session opens with a brief: inbox count, active projects, review recency, next actions. |
| Live dashboard | `Dashboard.md` — auto-updating Dataview queries, viewed in Obsidian. |
| HTML dashboard | `/gtd-dashboard` publishes a shareable visual snapshot as an Artifact. |
| CLI | `brain capture|next|inbox|review` — terminal access (see `cli/README.md`). |
| Superpowers skills | The Superpowers dev-workflow library in `.claude/skills/`. |

## Getting started
1. Open in Obsidian: Open folder as vault → this repo.
2. Install Dataview (see `docs/gtd/obsidian-plugins.md`).
3. Read `30 Resources/GTD System.md` for the conventions.
4. Capture: say "capture: …" in Claude Code, or `brain capture "…"`, or drop notes in `00 Inbox/`.
5. Weekly: run `/gtd-weekly-review`.

## The GTD loop
Capture → Clarify → Organize → Reflect → Engage, closed weekly by the review.

## Conventions (quick reference)
- Contexts: `#computer` `#phone` `#errands` `#home` `#office` `#anywhere` `#agenda`
- Status: `#next` (do now) · `#waiting` (delegated) · `#someday` (not yet committed)
- Fields: `[due:: YYYY-MM-DD]` · `[scheduled:: YYYY-MM-DD]` · `[since:: YYYY-MM-DD]`

Full details in `30 Resources/GTD System.md`. Design docs in `docs/`.
```

- [ ] **Step 2: Verify** — Run: `grep -q 'Getting started' README.md && grep -q 'gtd-capture' README.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README to document the full second-brain system"
```

---

## Phase 6 — Optional: external connectors (deferred / stretch)

> Only build this phase if the user opts in. It brings capture-in and calendar-into-review from
> Gmail/Google Calendar via the connectors already available to Claude Code. No repo secrets.

### Task 22: Connectors capture bridge (documentation + skill wiring)

**Files:**
- Create: `docs/gtd/connectors.md`

- [ ] **Step 1: Write `docs/gtd/connectors.md`** documenting the flows (no code, no credentials):

```markdown
# Connectors (optional)

Claude Code can reach Gmail and Google Calendar directly. These flows never store credentials in
the repo — Claude uses its own connector auth at runtime.

## Email → inbox
Ask Claude: "process my flagged emails into the second brain." Claude reads flagged/starred
threads and runs the `gtd-capture` flow for each, writing items to `00 Inbox/` with a link back to
the thread. You then `/gtd-process-inbox` as usual.

## Calendar → weekly review
During `/gtd-weekly-review`, ask Claude to pull the next two weeks from Google Calendar so
commitments are reviewed alongside projects.

## Guardrails
- Capture only; Claude does not send email or modify calendar events unless you explicitly ask.
- Nothing from a connector is committed automatically — you review the inbox before it's filed.
```

- [ ] **Step 2: Verify** — Run: `test -f docs/gtd/connectors.md && echo OK`. Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/gtd/connectors.md
git commit -m "docs: document optional Gmail/Calendar connector flows"
```

---

## Final verification (run after all phases)

- [ ] **Skills discoverable:** `for s in gtd-capture gtd-process-inbox gtd-next-actions gtd-weekly-review gtd-dashboard; do grep -q "name: $s" ".claude/skills/$s/SKILL.md" && echo "OK $s"; done` → five `OK`.
- [ ] **Hook test green:** `bash .claude/hooks/test_gtd-status.sh; echo exit=$?` → `exit=0`.
- [ ] **CLI suite green:** `python3 -m pytest cli/tests -q` → all pass.
- [ ] **All JSON valid:** `for f in .claude/settings.json .obsidian/*.json; do python3 -c "import json;json.load(open('$f'))"; done` → no errors.
- [ ] **No stray build artifacts:** `git status --porcelain` → clean after commits.
- [ ] **Manual Obsidian pass:** open the vault, enable Dataview, confirm `Dashboard.md` and `Weekly Review.md` render without query errors.
- [ ] **Push:** `git push -u origin claude/superpowers-skills-beuh67`.

---

## Self-Review (author's checklist — completed)

**1. Spec coverage** — every spec section maps to tasks:
- Vault structure → Tasks 1, 3. Conventions → Task 2. Templates → Task 4.
- GTD skills (5 steps) → Tasks 5–9. Capture/next fast paths → Tasks 5, 7, 15, 16.
- Two dashboards → Task 12 (live) + Tasks 9/14 (HTML). Weekly review → Tasks 8, 13.
- CLI → Tasks 15–19. External plugins → Task 20. Docs/README → Tasks 21, 14, 19, 20.
- Optional connectors (non-goal for v1, documented as stretch) → Task 22.
- Superpowers prerequisite → Global Constraints (already installed).

**2. Placeholder scan** — no "TBD"/"add error handling"/"similar to Task N"; every code and content
step carries full copy-pasteable content. Manual-only checks (Obsidian rendering) are explicitly
labeled as manual, not left as vague steps.

**3. Type consistency** — CLI signatures are consistent across tasks: `find_vault`, `Task`,
`parse_tasks`, `iter_tasks` (Task 15) are used verbatim by `next_actions`/`waiting`/`inbox_items`/
`review_status` (Tasks 16–18); `review_status` keys (`inbox`, `active_projects`, `waiting`,
`next_count`, `last_review_days`) match their test and the `cmd_review` reader. Content tokens
(tags, fields, folder names) match Global Constraints everywhere.
```
