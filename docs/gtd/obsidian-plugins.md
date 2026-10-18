# Obsidian plugins for this vault

The plugins are **optional git submodules** under `.obsidian/plugins/` (already enabled in
`.obsidian/community-plugins.json`), each in its own repository — the third-party ones are unmodified
upstream release builds that credit and link the original project. See
`.obsidian/plugins/README.md` for the list, versions, upstreams and licenses.
- Fresh clone: `git clone --recurse-submodules …`; existing clone: `git submodule update --init`
  (or name only the plugins you want: `git submodule update --init .obsidian/plugins/dataview`).
- Then run `python .claude/skills/gtd-setup/apply.py .` (or `/gtd-setup`): it applies the vault's
  presets below to the installed plugins. The presets live in
  `.claude/skills/gtd-setup/scaffold/plugin-data/<id>/data.json`; your own settings (`data.json` in
  the plugin folder) are git-ignored and never overwritten.
- Skipped a submodule? Install that plugin from Settings → Community plugins instead (same folder),
  then re-run `apply.py`.

## Required
### Dataview — powers `Dashboard.md`
Dataview (`.obsidian/plugins/dataview`) needs **JavaScript queries turned on** for the visual
`Dashboard.md` — the gtd-setup preset does that (`enableDataviewJs`, `enableInlineDataviewJs`).
1. Check out the submodule and run `apply.py` (above).
2. Open the folder as a vault; accept "Trust author and enable plugins" on first open.
3. `Dashboard.md` renders as a KPI + card grid; `Home.canvas` is a spatial launchpad.
Installed Dataview from the Community store instead? Enable "Enable JavaScript Queries" in its
settings, or re-run `apply.py`.
Don't want Dataview at all? Run `/gtd-dashboard` for the portable `dashboard.html`, which needs
no plugin and opens in any browser.

### QuickAdd — powers the dashboard's Actions row
QuickAdd (`.obsidian/plugins/quickadd`) gets three choices from the gtd-setup preset
(`.claude/skills/gtd-setup/scaffold/plugin-data/quickadd/data.json`, copied to
`.obsidian/plugins/quickadd/data.json` by `apply.py`):
- **Quick Capture** — appends a raw, untagged line to `00 Inbox/README.md`.
- **New Next Action** — prompts for a project (from `10 Projects/`), a task, and a context; inserts
  a formatted `#next` task line directly under that project's `## Next actions` heading.
- **New Project** — prompts for a title and creates a new file in `10 Projects/` from
  `_templates/Project.md`.

`Dashboard.md`'s "➕ Actions" row links to these via `obsidian://quickadd?choice=<name>&vault=<name>`
— click one to run it without opening the command palette. They're also always reachable via
`Ctrl+P` → "QuickAdd: <choice name>" regardless of which note is open.
Installed QuickAdd from the Community store instead? Re-run `apply.py` to add the three choices (it
won't touch an existing `data.json`; copy the preset over it yourself if you want to replace yours).

### The dashboard's styling
`Dashboard.md` carries `cssclasses: [dashboard]` and is styled by the snippet
`.obsidian/snippets/dashboard.css` (enabled in `.obsidian/appearance.json`). `Dashboard (lists).md`
is a plain-Dataview fallback if you prefer tables to cards.

## Optional
- **Smart Second Brain** (`.obsidian/plugins/smart-second-brain`, submodule; upstream
  [s2b-dev/smart-second-brain](https://github.com/s2b-dev/smart-second-brain)) — semantic / RAG search
  + an AI assistant that knows your notes. Complements Dataview: Dataview does *structured* queries
  (tags, fields), Smart Second Brain does *fuzzy/semantic* retrieval ("what did I note about
  pricing?"). Or install via Community plugins → "Smart Second Brain".
- **Claudian** (`.obsidian/plugins/realclaudian`, submodule; upstream
  [YishenTu/claudian](https://github.com/YishenTu/claudian)) — runs the vault's agent and skills in a
  side panel; see `docs/gtd/portability.md`.
- **Tasks** — richer task querying/recurrence; compatible with our checkbox conventions.
- **Calendar** — month view tied to `Journal/` daily notes.
- **Templater** — dynamic templates; our `_templates/` use core Templates and work without it.

### Record Meeting — meeting recording + transcription
Submodule `.obsidian/plugins/record-meeting`
([adamkopelman/obsidian-record-meeting](https://github.com/adamkopelman/obsidian-record-meeting)),
pre-enabled in `.obsidian/community-plugins.json`. Adds a mic ribbon button (record → WAV) and a
captions ribbon button (transcribe pending recordings with the fully offline `whisper.cpp` from the
`vendor/whisper-cpp` submodule — download its model once, see `docs/gtd/meeting-recording.md`).
Desktop only (uses Node `child_process` + the local microphone).

## Core plugins already enabled
Templates (`_templates`), Daily notes (`Journal`, template `_templates/Daily Note.md`), Properties,
Tag pane, Backlinks, Graph — see `.obsidian/core-plugins.json`.
