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
| Live dashboard | `Dashboard.md` — a visual KPI + card grid (Dataview JS) with a clickable Actions row (QuickAdd) to capture a task, add a next action to a project, or start a new project; `Dashboard (lists).md` is a no-JS fallback. |
| Quick Capture (Windows) | TickTick-style global shortcuts: `Ctrl+Alt+A` adds a task to the inbox from any app, `Ctrl+Alt+T` to Today, `Ctrl+Alt+V` captures the clipboard. A tray script with nothing to install. See `docs/gtd/quick-capture.md`. |
| Local browser dashboard | `scripts/dashboard_server.py` — a Things 3–style app over the same files (Inbox, Today/This Evening, Upcoming, Anytime, Someday, Waiting, Logbook; Areas → Projects), with full to-do editing, no Obsidian required. See `docs/gtd/local-dashboard.md`. |
| Meeting recording | 🎙️/💬 ribbon buttons (`record-meeting` plugin) to record a meeting to WAV and transcribe it — fully offline, multilingual `whisper.cpp` (model downloaded once). Summarizing into notes/decisions/action items runs separately in Claude Code (`gtd-summarize-meetings`). See `docs/gtd/meeting-recording.md`. |
| Home board | `Home.canvas` — a spatial launchpad (Obsidian Canvas) embedding the dashboard + link-cards. |
| Portable dashboard | `dashboard.html` — self-contained, any browser (`/gtd-dashboard`). |
| Portability | Skills in `.claude/skills/` (Claude Code, opencode, Claudian); MCP in `.mcp.json` + `opencode.json`; see `AGENTS.md`. |

## Getting started
1. Clone with the optional components (Obsidian plugins, whisper.cpp, Quick Capture), which are git
   submodules:
   ```
   git clone --recurse-submodules https://github.com/adamkopelman/second-brain.git
   ```
   Already cloned without them? `git submodule update --init`. Every submodule is optional — check
   out only the ones you want (`git submodule update --init <path> ...`) or none; see
   [Optional components](#optional-components-git-submodules).
2. Set up: `/gtd-setup`, or `python3 .claude/skills/gtd-setup/apply.py .` — idempotent; besides
   scaffolding anything missing, it applies the vault's Dataview/QuickAdd settings to the plugins and,
   on Windows, downloads the Outlook MCP server (`outlook-mcp-rs.exe`) from its GitHub release
   (`--no-outlook-mcp` skips that).
3. Open the folder as an Obsidian vault and trust the plugins — see `docs/gtd/obsidian-plugins.md`.
4. (Recommended) Use **Claudian** to run these skills inside Obsidian; (optional) **Smart Second
   Brain** for semantic search. See `docs/gtd/portability.md` and `docs/gtd/obsidian-plugins.md`.
5. (Optional) Wire Outlook — see `docs/gtd/outlook.md`.
6. (Optional, Windows) Offline meeting transcription: download the Whisper model once (~74 MB, not in
   git) with `powershell -ExecutionPolicy Bypass -File vendor\whisper-cpp\download-model.ps1` — see
   `docs/gtd/meeting-recording.md`.
7. (Optional, Windows) Global capture shortcuts: double-click `scripts\quick_capture\install.cmd`, then
   press `Ctrl+Alt+A` anywhere — see `docs/gtd/quick-capture.md`.
8. Read `30 Resources/GTD System.md` for conventions. Capture with `/gtd-capture`; review weekly
   with `/gtd-weekly-review`.

## Optional components (git submodules)
Each lives in its own repository so the vault stays small and you take only what you want.
Third-party plugins are unmodified upstream release builds; each repo's README credits and links
the original project.

| Path | Repository | What | Upstream |
| --- | --- | --- | --- |
| `.obsidian/plugins/dataview` | [obsidian-dataview-dist](https://github.com/adamkopelman/obsidian-dataview-dist) | Dataview 0.5.70 — powers `Dashboard.md` | [blacksmithgu/obsidian-dataview](https://github.com/blacksmithgu/obsidian-dataview) (MIT) |
| `.obsidian/plugins/quickadd` | [obsidian-quickadd-dist](https://github.com/adamkopelman/obsidian-quickadd-dist) | QuickAdd 2.25.0 — the dashboard's Actions row | [chhoumann/quickadd](https://github.com/chhoumann/quickadd) (MIT) |
| `.obsidian/plugins/realclaudian` | [obsidian-claudian-dist](https://github.com/adamkopelman/obsidian-claudian-dist) | Claudian 2.2.6 — agent side panel in Obsidian | [YishenTu/claudian](https://github.com/YishenTu/claudian) (MIT) |
| `.obsidian/plugins/smart-second-brain` | [obsidian-smart-second-brain-dist](https://github.com/adamkopelman/obsidian-smart-second-brain-dist) | Smart Second Brain 2.0.5 — semantic search/chat | [s2b-dev/smart-second-brain](https://github.com/s2b-dev/smart-second-brain) (MIT) |
| `.obsidian/plugins/record-meeting` | [obsidian-record-meeting](https://github.com/adamkopelman/obsidian-record-meeting) | Record/transcribe meetings from Obsidian | — (this project) |
| `vendor/whisper-cpp` | [whisper-cpp](https://github.com/adamkopelman/whisper-cpp) | whisper.cpp Windows binaries; model downloaded on demand | [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) (MIT) |
| `scripts/quick_capture` | [gtd-quick-capture](https://github.com/adamkopelman/gtd-quick-capture) | Windows global capture shortcuts | — (this project) |

`git submodule status` shows what's checked out (a leading `-` means not). Skipping a plugin
submodule? Install it from Obsidian's Community plugins instead and re-run `/gtd-setup`. Update
them all with `git submodule update --remote` (then commit the new pointers).

Not a submodule: the Outlook MCP server binary. `gtd-setup` downloads `outlook-mcp-rs.exe` v0.3.0
from the [adamkopelman/outlook-mcp-rs](https://github.com/adamkopelman/outlook-mcp-rs) releases
(MIT) into `vendor/outlook-mcp-rs/` (git-ignored), verifying its SHA-256 — or run
`vendor\outlook-mcp-rs\download-outlook-mcp-rs.ps1` yourself. See `docs/gtd/outlook.md`.

## Conventions (quick reference)
- Contexts: `#computer` `#phone` `#errands` `#home` `#office` `#anywhere` `#agenda`
- Status: `#next` (do now) · `#waiting` (delegated) · `#someday`
- Fields: `[due:: YYYY-MM-DD]` · `[scheduled:: YYYY-MM-DD]` · `[since:: YYYY-MM-DD]` · `[completion:: YYYY-MM-DD]`; `#evening` = This Evening

Full details: `30 Resources/GTD System.md`. Design/plan: `docs/superpowers/`. Harness guide: `AGENTS.md`.
