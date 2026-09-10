# Obsidian plugins for this vault

## Required
### Dataview — powers `Dashboard.md`
Dataview is **vendored and pre-enabled** in this repo (`.obsidian/plugins/dataview`,
`.obsidian/community-plugins.json`), and **JavaScript queries are already turned on**
(`.obsidian/plugins/dataview/data.json`) — the visual `Dashboard.md` needs them.
1. Open the folder as a vault; accept "Trust author and enable plugins" on first open.
2. `Dashboard.md` renders as a KPI + card grid; `Home.canvas` is a spatial launchpad.
If you ever start from a fresh vault without the vendored plugin, install Dataview via
Settings → Community plugins → Browse → "Dataview", then enable "Enable JavaScript Queries".
Don't want Dataview at all? Run `/gtd-dashboard` for the portable `dashboard.html`, which needs
no plugin and opens in any browser.

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

### The dashboard's styling
`Dashboard.md` carries `cssclasses: [dashboard]` and is styled by the snippet
`.obsidian/snippets/dashboard.css` (enabled in `.obsidian/appearance.json`). `Dashboard (lists).md`
is a plain-Dataview fallback if you prefer tables to cards.

## Optional
- **Smart Second Brain** (`obsidian-smart2brain`) — semantic / RAG search + an AI assistant that
  knows your notes. Complements Dataview: Dataview does *structured* queries (tags, fields),
  Smart Second Brain does *fuzzy/semantic* retrieval ("what did I note about pricing?"). Install via
  Community plugins → "Smart Second Brain".
- **Tasks** — richer task querying/recurrence; compatible with our checkbox conventions.
- **Calendar** — month view tied to `Journal/` daily notes.
- **Templater** — dynamic templates; our `_templates/` use core Templates and work without it.

### Record Meeting — meeting recording + transcription
Vendored and pre-enabled (`.obsidian/plugins/record-meeting`, `.obsidian/community-plugins.json`).
Adds a mic ribbon button (record → WAV) and a captions ribbon button (transcribe pending recordings
via the vendored, fully offline `whisper.cpp` in `vendor/whisper-cpp/`). See
`docs/gtd/meeting-recording.md`. Desktop only (uses Node `child_process` + the local microphone).

## Core plugins already enabled
Templates (`_templates`), Daily notes (`Journal`, template `_templates/Daily Note.md`), Properties,
Tag pane, Backlinks, Graph — see `.obsidian/core-plugins.json`.
