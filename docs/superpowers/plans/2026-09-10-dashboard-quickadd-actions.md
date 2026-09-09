# Dashboard QuickAdd Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Dashboard.md` actionable — three clickable links that capture a task, add a next
action to an existing project, or create a new project, without leaving Obsidian.

**Architecture:** Vendor the QuickAdd community plugin (same pattern as the Dataview/Claudian
plugins already committed in `.obsidian/plugins/`), configure three QuickAdd "choices" in its
`data.json`, and trigger them from plain markdown links in `Dashboard.md` using QuickAdd's
`obsidian://quickadd?choice=...` URI scheme — no second plugin needed for clickability. Mirror the
changes into the `gtd-setup` scaffold so `/gtd-setup` reproduces them for new vaults.

**Tech Stack:** Obsidian (community plugin: QuickAdd 2.25.0), Dataview `dataviewjs` (already in
use in `Dashboard.md`), Obsidian Canvas (`Home.canvas`), Python (existing `gtd-setup` test suite).

**Spec:** `docs/superpowers/specs/2026-09-10-dashboard-mission-quickadd-design.md`

## Global Constraints

- QuickAdd is pinned to release **2.25.0** — download only from the exact URLs in Task 1, don't
  substitute "latest".
- Do not modify `_templates/Project.md`. (Verified during planning: QuickAdd's Template engine
  already runs its own token formatter over the whole file, and its `TITLE_REGEX`/`DATE_REGEX` are
  case-insensitive, so the existing lowercase `{{title}}` / `{{date:YYYY-MM-DD}}` tokens already
  resolve correctly through QuickAdd. Adding a QuickAdd-only token like `{{VALUE:area}}` to that
  file would silently break the *existing* manual "Insert Template" flow, which only understands
  Obsidian's core template tokens — so the "New Project" choice leaves `area:` blank, exactly like
  manual creation does today.)
- `created` and `review` on a QuickAdd-created project both resolve to the creation date (both use
  the same `{{date:YYYY-MM-DD}}` token, with no `+7` offset) — this is a deliberate simplification;
  offsetting only the QuickAdd path would require a second, diverging template.
- No automated test runner can execute Obsidian-plugin config — every task that touches
  `.obsidian/plugins/quickadd/` or `Dashboard.md` ends with a **manual verification step**: open
  the vault in Obsidian and confirm the real behavior. Do not mark a task done without doing this.
- Keep `Dashboard.md`'s existing `dataviewjs` KPI/card-grid block untouched — this work is
  additive only.
- Mirror every vault-facing change into `.claude/skills/gtd-setup/scaffold/vault/` at the matching
  relative path (scaffold == root convention; see commit `97a33d9`).

---

### Task 1: Vendor the QuickAdd plugin and enable it

**Files:**
- Create: `.obsidian/plugins/quickadd/manifest.json`
- Create: `.obsidian/plugins/quickadd/main.js`
- Create: `.obsidian/plugins/quickadd/styles.css`
- Modify: `.obsidian/community-plugins.json`
- Modify: `.obsidian/plugins/README.md`

**Interfaces:**
- Produces: an enabled, unconfigured QuickAdd plugin (plugin id `"quickadd"`) that Task 2 will
  configure via `.obsidian/plugins/quickadd/data.json`.

- [ ] **Step 1: Download the pinned release assets**

Run from the repo root:

```bash
mkdir -p ".obsidian/plugins/quickadd"
curl -sL -o ".obsidian/plugins/quickadd/manifest.json" "https://github.com/chhoumann/quickadd/releases/download/2.25.0/manifest.json"
curl -sL -o ".obsidian/plugins/quickadd/main.js" "https://github.com/chhoumann/quickadd/releases/download/2.25.0/main.js"
curl -sL -o ".obsidian/plugins/quickadd/styles.css" "https://github.com/chhoumann/quickadd/releases/download/2.25.0/styles.css"
```

- [ ] **Step 2: Verify the downloaded manifest**

Run: `cat ".obsidian/plugins/quickadd/manifest.json"`
Expected: contains `"id": "quickadd"` and `"version": "2.25.0"`. If either is wrong, the download
failed silently (e.g. an HTML error page was saved) — re-run Step 1 and check `curl`'s exit code.

- [ ] **Step 3: Enable the plugin**

Edit `.obsidian/community-plugins.json` from:
```json
["dataview", "realclaudian", "smart-second-brain"]
```
to:
```json
["dataview", "realclaudian", "smart-second-brain", "quickadd"]
```

- [ ] **Step 4: Document the new vendored plugin**

Edit `.obsidian/plugins/README.md`, adding a row to the table:
```
| QuickAdd | `quickadd` | 2.25.0 | https://github.com/chhoumann/quickadd | MIT |
```
And update the closing sentence to read:
```
**Updating:** re-download `manifest.json`, `main.js`, `styles.css` from the plugin's
`releases/latest/download/` and commit. Only Dataview and QuickAdd are required by this vault;
Claudian and Smart Second Brain are recommended/optional (see `docs/gtd/obsidian-plugins.md`).
```

- [ ] **Step 5: Manual verification**

Open the vault in Obsidian (or reload it if already open: `Ctrl+R` / Command palette → "Reload app
without saving"). Go to Settings → Community plugins and confirm "QuickAdd" is listed and enabled,
with no error banner. (It will do nothing useful yet — Task 2 configures it.)

- [ ] **Step 6: Commit**

```bash
git add ".obsidian/plugins/quickadd/manifest.json" ".obsidian/plugins/quickadd/main.js" ".obsidian/plugins/quickadd/styles.css" ".obsidian/community-plugins.json" ".obsidian/plugins/README.md"
git commit -m "feat(vault): vendor and enable the QuickAdd plugin"
```

---

### Task 2: Configure the three QuickAdd choices

**Files:**
- Create: `.obsidian/plugins/quickadd/data.json`

**Interfaces:**
- Consumes: the enabled QuickAdd plugin from Task 1 (plugin id `quickadd`).
- Produces: three named QuickAdd choices — `"Quick Capture"`, `"New Next Action"`, `"New
  Project"` — triggerable both from QuickAdd's command palette entry ("QuickAdd: Run QuickAdd")
  and, from Task 3 onward, from `obsidian://quickadd?choice=<name>` links in `Dashboard.md`. QuickAdd
  merges this file with its own defaults on load (`Object.assign({}, DEFAULT_SETTINGS,
  loadedData)`, verified in QuickAdd's `main.ts`), so only the `choices` array needs to be written
  here — every other setting keeps QuickAdd's built-in default.

- [ ] **Step 1: Write `data.json`**

```json
{
  "choices": [
    {
      "id": "faf7c466-8550-499b-9759-7dfa9508af39",
      "name": "Quick Capture",
      "type": "Capture",
      "command": false,
      "captureTo": "00 Inbox/README.md",
      "captureToActiveFile": false,
      "captureToCanvasNodeId": "",
      "activeFileWritePosition": "cursor",
      "createFileIfItDoesntExist": { "enabled": false, "createWithTemplate": false, "template": "" },
      "format": { "enabled": true, "format": "{{VALUE}}" },
      "prepend": false,
      "appendLink": false,
      "task": true,
      "insertAfter": {
        "enabled": false,
        "after": "",
        "insertAtEnd": false,
        "considerSubsections": false,
        "createIfNotFound": false,
        "createIfNotFoundLocation": "top",
        "inline": false,
        "replaceExisting": false,
        "blankLineAfterMatchMode": "auto",
        "promptHeading": false
      },
      "insertBefore": { "enabled": false, "before": "", "createIfNotFound": false, "createIfNotFoundLocation": "top" },
      "newLineCapture": { "enabled": false, "direction": "below" },
      "openFile": false,
      "fileOpening": { "location": "tab", "direction": "vertical", "mode": "default", "focus": true }
    },
    {
      "id": "bcad0b28-0440-4f08-8563-677e8dc28e78",
      "name": "New Next Action",
      "type": "Capture",
      "command": false,
      "captureTo": "10 Projects/{{FILE:10 Projects|name|label:Project}}.md",
      "captureToActiveFile": false,
      "captureToCanvasNodeId": "",
      "activeFileWritePosition": "cursor",
      "createFileIfItDoesntExist": { "enabled": false, "createWithTemplate": false, "template": "" },
      "format": { "enabled": true, "format": "{{VALUE}} #next #{{VALUE:computer,phone,errands,home,office,anywhere,agenda|name:context}}" },
      "prepend": false,
      "appendLink": false,
      "task": true,
      "insertAfter": {
        "enabled": true,
        "after": "## Next actions",
        "insertAtEnd": false,
        "considerSubsections": false,
        "createIfNotFound": false,
        "createIfNotFoundLocation": "top",
        "inline": false,
        "replaceExisting": false,
        "blankLineAfterMatchMode": "auto",
        "promptHeading": false
      },
      "insertBefore": { "enabled": false, "before": "", "createIfNotFound": false, "createIfNotFoundLocation": "top" },
      "newLineCapture": { "enabled": false, "direction": "below" },
      "openFile": false,
      "fileOpening": { "location": "tab", "direction": "vertical", "mode": "default", "focus": true }
    },
    {
      "id": "425d93c8-e8f3-44b3-887a-e9a1d16ae2d0",
      "name": "New Project",
      "type": "Template",
      "command": false,
      "templatePath": "_templates/Project.md",
      "folder": {
        "enabled": true,
        "folders": ["10 Projects"],
        "chooseWhenCreatingNote": false,
        "createInSameFolderAsActiveFile": false,
        "chooseFromSubfolders": false
      },
      "fileNameFormat": { "enabled": true, "format": "{{VALUE:title|label:Project title}}" },
      "discoverExistingNotesBeforeCreate": false,
      "appendLink": false,
      "copyLinkToClipboard": false,
      "openFile": true,
      "fileOpening": { "location": "tab", "direction": "vertical", "mode": "default", "focus": true },
      "fileExistsBehavior": { "kind": "prompt" }
    }
  ]
}
```

- [ ] **Step 2: Verify the JSON is well-formed**

Run: `python3 -m json.tool ".obsidian/plugins/quickadd/data.json" > /dev/null && echo OK`
Expected: `OK`. If it fails, fix the syntax error it reports before continuing — a malformed
`data.json` makes QuickAdd fall back to defaults silently (no choices, no crash), which is much
harder to debug than a `json.tool` syntax error caught here.

- [ ] **Step 3: Manual verification — Quick Capture**

In Obsidian, reload the app (Task 1 already enabled the plugin; reloading picks up `data.json`).
Open the command palette (`Ctrl+P`), run **QuickAdd: Quick Capture**, type `Buy stamps`, confirm.
Open `00 Inbox/README.md` and confirm a new line `- [ ] Buy stamps` was appended, with no tags.

- [ ] **Step 4: Manual verification — New Next Action**

Command palette → **QuickAdd: New Next Action**. When prompted for a project, pick any existing
file in `10 Projects/` (create a throwaway one first if the folder is empty, e.g. copy
`_templates/Project.md` to `10 Projects/Test Project.md`). Type a task name, e.g. `Call the
vendor`, then pick a context, e.g. `phone`. Open that project file and confirm a new line
`- [ ] Call the vendor #next #phone` was inserted directly under its `## Next actions` heading.
Delete the throwaway project file afterward if you created one.

- [ ] **Step 5: Manual verification — New Project**

Command palette → **QuickAdd: New Project**. Type a title, e.g. `Test Project Two`. Confirm a new
file `10 Projects/Test Project Two.md` was created from the template: `# Test Project Two`
heading, `type: project`, `status: active`, `area:` blank, `created:`/`review:` both today's date.
Delete this test file afterward.

- [ ] **Step 6: Commit**

```bash
git add ".obsidian/plugins/quickadd/data.json"
git commit -m "feat(vault): configure QuickAdd capture and new-project choices"
```

---

### Task 3: Add the clickable Actions row to `Dashboard.md`

**Files:**
- Modify: `Dashboard.md`

**Interfaces:**
- Consumes: the three QuickAdd choice names from Task 2 (`"Quick Capture"`, `"New Next Action"`,
  `"New Project"`) — must match exactly (case-sensitive), since QuickAdd's URI handler looks
  choices up by name.
- Produces: an `.gtd-actions` HTML block rendered inside the existing `dataviewjs` block, for
  Task 6's scaffold mirror and any future dashboard styling to reference.

- [ ] **Step 1: Insert the Actions row**

In `Dashboard.md`, find this line (existing KPI tile construction):

```js
  let html = `<div class="gtd-kpis">` + tiles.map(([e,n,l,c]) =>
    `<div class="gtd-kpi gtd-${c}"><div class="gtd-kpi-n">${n}</div><div class="gtd-kpi-l">${e} ${esc(l)}</div></div>`).join("") + `</div>`;

  html += `<div class="gtd-grid">`;
```

Change it to (adding the actions row between the KPI tiles and the grid):

```js
  let html = `<div class="gtd-kpis">` + tiles.map(([e,n,l,c]) =>
    `<div class="gtd-kpi gtd-${c}"><div class="gtd-kpi-n">${n}</div><div class="gtd-kpi-l">${e} ${esc(l)}</div></div>`).join("") + `</div>`;

  // ---- Quick actions (QuickAdd) ----
  const vaultName = encodeURIComponent(dv.app.vault.getName());
  const qa = (choice) => `obsidian://quickadd?choice=${encodeURIComponent(choice)}&vault=${vaultName}`;
  html += `<div class="gtd-actions">` +
    `<a class="gtd-action-btn" href="${qa("Quick Capture")}">📥 Quick Capture</a>` +
    `<a class="gtd-action-btn" href="${qa("New Next Action")}">⚡ New Next Action</a>` +
    `<a class="gtd-action-btn" href="${qa("New Project")}">📋 New Project</a>` +
    `</div>`;

  html += `<div class="gtd-grid">`;
```

- [ ] **Step 2: Style the new buttons**

Read `.obsidian/snippets/dashboard.css` first (it defines `.gtd-kpis`, `.gtd-card`, etc. using
theme variables). Add a block following the same conventions (reuse the existing color/spacing
custom properties you find there rather than hardcoding new colors), e.g.:

```css
.gtd-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 20px; }
.gtd-action-btn {
  display: inline-block;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--interactive-accent);
  color: var(--text-on-accent);
  text-decoration: none;
  font-size: 0.85em;
  font-weight: 600;
}
.gtd-action-btn:hover { background: var(--interactive-accent-hover); }
```

(If `dashboard.css` uses different variable names than `--interactive-accent` /
`--text-on-accent`, match whatever it actually uses instead — read the file before writing this.)

- [ ] **Step 3: Verify the dataviewjs block still parses**

Extract the JS between the ` ```dataviewjs ` fence markers in `Dashboard.md` and check it for
syntax errors without a full Obsidian instance:

```bash
python3 - <<'PY'
import re
text = open("Dashboard.md", encoding="utf-8").read()
m = re.search(r"```dataviewjs\n(.*?)\n```", text, re.S)
open("/tmp/dashboard_check.js", "w", encoding="utf-8").write(
    "const dv = {pages: () => ({where: () => []}), date: () => ({plus: () => 0}), el: () => ({})};\n" + m.group(1)
)
PY
node --check /tmp/dashboard_check.js && echo OK
```

Expected: `OK`. This only checks JS syntax, not runtime behavior (that's Step 4).

- [ ] **Step 4: Manual verification**

Open `Dashboard.md` in Obsidian (Reading view). Confirm three pill-shaped buttons render below the
KPI tiles. Click each one in turn and confirm QuickAdd's prompt opens for the matching choice
(you don't need to complete the full capture again here — Task 2 already verified the capture
behavior; this step verifies the *link* reaches the *right* choice from inside the dashboard).

- [ ] **Step 5: Commit**

```bash
git add "Dashboard.md" ".obsidian/snippets/dashboard.css"
git commit -m "feat(dashboard): add clickable QuickAdd actions row"
```

---

### Task 4: Update `Home.canvas` to mention the new actions

**Files:**
- Modify: `Home.canvas`

**Interfaces:**
- Consumes: nothing new (this is a documentation-only text update to an existing canvas node).

- [ ] **Step 1: Edit the "engage" node's text**

In `Home.canvas`, find the node with `"id": "engage"` and change its `"text"` field from:

```
"## ⚡ Capture & Engage\n- [[00 Inbox]] — capture here\n- [[Dashboard]] — what's now\n- `/gtd-capture` · `/gtd-next-actions` · `/gtd-status`"
```

to:

```
"## ⚡ Capture & Engage\n- [[00 Inbox]] — capture here\n- [[Dashboard]] — what's now, and click to add\n- `/gtd-capture` · `/gtd-next-actions` · `/gtd-status`\n- Dashboard buttons: Quick Capture · New Next Action · New Project (needs QuickAdd)"
```

(Edit the JSON's `text` string value directly — don't hand-edit the escaped `⚡` etc.;
whatever editor/tool you use should preserve the surrounding JSON structure. If editing by hand,
increasing the node's `"height"` from `230` to `260` keeps the extra line from being clipped.)

- [ ] **Step 2: Verify the canvas file is still valid JSON**

Run: `python3 -m json.tool "Home.canvas" > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Manual verification**

Open `Home.canvas` in Obsidian and confirm the "Capture & Engage" card shows the new line without
visual clipping (resize the node in the canvas editor if it looks cramped, and save).

- [ ] **Step 4: Commit**

```bash
git add "Home.canvas"
git commit -m "docs(vault): mention QuickAdd dashboard actions on the Home canvas"
```

---

### Task 5: Document QuickAdd as a required plugin

**Files:**
- Modify: `docs/gtd/obsidian-plugins.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing new; documents Tasks 1-3's behavior.

- [ ] **Step 1: Update `docs/gtd/obsidian-plugins.md`**

Change the `## Required` section from just Dataview to include QuickAdd. Replace:

```markdown
## Required
### Dataview — powers `Dashboard.md`
```

with:

```markdown
## Required
### Dataview — powers `Dashboard.md`
```

(heading stays), and after the existing Dataview subsection (before `## Optional`), insert a new
subsection:

```markdown
### QuickAdd — powers the dashboard's Actions row
QuickAdd is **vendored and pre-enabled** (`.obsidian/plugins/quickadd`,
`.obsidian/community-plugins.json`), with three choices pre-configured in
`.obsidian/plugins/quickadd/data.json`:
- **Quick Capture** — appends a raw, untagged line to `00 Inbox/README.md`.
- **New Next Action** — prompts for a project (from `10 Projects/`), a task, and a context; inserts
  a formatted `#next` task line directly under that project's `## Next actions` heading.
- **New Project** — prompts for a title and creates a new file in `10 Projects/` from
  `_templates/Project.md`.

`Dashboard.md`'s "➕ Actions" row links to these via `obsidian://quickadd?choice=<name>&vault=<name>`
— click one to run it without opening the command palette. They're also always reachable via
`Ctrl+P` → "QuickAdd: <choice name>" regardless of which note is open.
If you ever start from a fresh vault without the vendored plugin, install QuickAdd via
Settings → Community plugins → Browse → "QuickAdd", then recreate the three choices above (or copy
`.obsidian/plugins/quickadd/data.json` from this repo).
```

- [ ] **Step 2: Update `README.md`**

Change the dashboard row in the features table from:

```
| Live dashboard | `Dashboard.md` — a visual KPI + card grid (Dataview JS); `Dashboard (lists).md` is a no-JS fallback. |
```

to:

```
| Live dashboard | `Dashboard.md` — a visual KPI + card grid (Dataview JS) with a clickable Actions row (QuickAdd) to capture a task, add a next action to a project, or start a new project; `Dashboard (lists).md` is a no-JS fallback. |
```

- [ ] **Step 3: Commit**

```bash
git add "docs/gtd/obsidian-plugins.md" "README.md"
git commit -m "docs: document QuickAdd as a required plugin for dashboard actions"
```

---

### Task 6: Mirror everything into the `gtd-setup` scaffold

**Files:**
- Modify: `.claude/skills/gtd-setup/scaffold/vault/Dashboard.md`
- Modify: `.claude/skills/gtd-setup/scaffold/vault/Home.canvas`
- Modify: `.claude/skills/gtd-setup/scaffold/vault/.obsidian/community-plugins.json`
- Modify: `.claude/skills/gtd-setup/scaffold/vault/.obsidian/snippets/dashboard.css`

**Interfaces:**
- Consumes: the finished, verified `Dashboard.md`, `Home.canvas`, `dashboard.css`, and
  `community-plugins.json` from Tasks 1-4.
- Produces: a scaffold that reproduces the same dashboard for any future `/gtd-setup` run. Note:
  per the existing pattern (confirmed during planning — the scaffold's
  `.obsidian/community-plugins.json` already lists `dataview`/`realclaudian`/`smart-second-brain`
  IDs with **no vendored plugin binaries** alongside them), the scaffold gets the `"quickadd"` id
  added to its `community-plugins.json` but does **not** get a copy of
  `.obsidian/plugins/quickadd/` — a fresh vault installs QuickAdd manually per
  `docs/gtd/obsidian-plugins.md`.

- [ ] **Step 1: Copy the updated files into the scaffold**

```bash
cp "Dashboard.md" ".claude/skills/gtd-setup/scaffold/vault/Dashboard.md"
cp "Home.canvas" ".claude/skills/gtd-setup/scaffold/vault/Home.canvas"
cp ".obsidian/snippets/dashboard.css" ".claude/skills/gtd-setup/scaffold/vault/.obsidian/snippets/dashboard.css"
```

- [ ] **Step 2: Add `quickadd` to the scaffold's community-plugins.json**

Edit `.claude/skills/gtd-setup/scaffold/vault/.obsidian/community-plugins.json` from:
```json
["dataview", "realclaudian", "smart-second-brain"]
```
to:
```json
["dataview", "realclaudian", "smart-second-brain", "quickadd"]
```

- [ ] **Step 3: Run the existing `gtd-setup` test suite**

Run: `python3 -m pytest .claude/skills/gtd-setup/tests/test_apply.py -v`
Expected: all 4 tests pass (`test_apply_creates_all_assets`, `test_apply_is_idempotent`,
`test_apply_never_overwrites_user_edits`, `test_force_overwrites`). These tests only check file
copying/idempotency, not dashboard content, so they should pass unchanged — if any fails, the
scaffold copy in Step 1/2 broke something structural (e.g. wrong path), not the dashboard content
itself.

- [ ] **Step 4: Manual verification**

Run `/gtd-setup` (or `python3 .claude/skills/gtd-setup/apply.py <scaffold> <tmp-dir>` directly) into
a scratch directory, open it as a new Obsidian vault, and confirm `Dashboard.md` shows the new
Actions row (buttons will not work until QuickAdd is installed there too, per the docs — that's
expected for a fresh vault).

- [ ] **Step 5: Commit**

```bash
git add ".claude/skills/gtd-setup/scaffold/vault/Dashboard.md" ".claude/skills/gtd-setup/scaffold/vault/Home.canvas" ".claude/skills/gtd-setup/scaffold/vault/.obsidian/community-plugins.json" ".claude/skills/gtd-setup/scaffold/vault/.obsidian/snippets/dashboard.css"
git commit -m "feat(gtd-setup): mirror dashboard QuickAdd actions into the scaffold"
```

---

## Self-Review Notes

- **Spec coverage:** every row of the spec's "QuickAdd capture flows" table maps to Task 2; the
  "Dashboard.md layout changes" section maps to Task 3; "Home.canvas" line maps to Task 4;
  "Mirroring & docs" maps to Tasks 5-6. The spec's "Testing approach" (manual verification per
  capture flow) is embedded as a step in Tasks 1-4 rather than a separate task, since each is only
  meaningful once its owning task's files exist.
- **Deviation from spec, called out explicitly:** the spec's "New Project" row listed an area
  suggester; Task 2 drops it (kept as a documented Global Constraint) because implementing it would
  have required adding a QuickAdd-only token to `_templates/Project.md`, breaking that template's
  existing use via Obsidian's core "Insert Template" command. `review` defaulting to the creation
  date (not +7 days) is the same kind of trade-off, also called out as a Global Constraint.
- **Type/name consistency:** the three choice names (`"Quick Capture"`, `"New Next Action"`,
  `"New Project"`) are identical, byte-for-byte, across Task 2's `data.json`, Task 3's
  `Dashboard.md` links, and Task 5's docs — QuickAdd's URI handler does an exact, case-sensitive
  name match.
