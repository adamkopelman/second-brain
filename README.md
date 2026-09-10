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
| Local browser dashboard | `scripts/dashboard_server.py` — a second, independent live view with full task CRUD, no Obsidian required. See `docs/gtd/local-dashboard.md`. |
| Meeting recording | 🎙️/💬 ribbon buttons (`record-meeting` plugin) to record a meeting to WAV and transcribe it — fully offline, vendored multilingual `whisper.cpp`. Summarizing into notes/decisions/action items runs separately in Claude Code (`gtd-summarize-meetings`). See `docs/gtd/meeting-recording.md`. |
| Home board | `Home.canvas` — a spatial launchpad (Obsidian Canvas) embedding the dashboard + link-cards. |
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
