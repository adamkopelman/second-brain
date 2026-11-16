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
- `gtd-transcribe-meeting` — transcribe pending meeting recordings (mechanical); on-demand full pipeline.
- `gtd-summarize-meetings` — summarize transcribed meetings into notes/decisions/action items (Claude Code, real generation; scheduler-safe).
- `gtd-organize` — housekeeping: archive finished material, move long transcripts out (dry run first).
- `gtd-lean-mode` — switch to lean mode for light / small-context models.

## Context budget (read this first — keeps light models from compacting)
1. **Query, don't read.** `python3 scripts/gtd_query.py brief|next|waiting|inbox|projects|health|meetings|find <text>|sizes`
   answers most questions in a few lines with `file:line` pointers. Use it before any Read/Grep.
2. **Read narrowly.** Open a note only to change it; read just the lines you need (offset/limit),
   edit one line rather than rewriting a file. Grep one folder at a time with a result limit.
3. **Never read** `vendor/`, `.obsidian/`, `docs/superpowers/`, `scripts/`, `40 Archive/` (unless asked),
   `Meetings/recordings/`, `dashboard.html`. Don't open the developer (Superpowers) skills for GTD work.
4. **Delegate heavy reading** to subagents (`.claude/agents/`): `vault-scout` lookups,
   `inbox-triage` inbox plan, `meeting-summarizer` one meeting each, `vault-organizer` housekeeping.
5. **Keep replies short**; don't echo file contents back. One GTD task per session — `/clear` between.
6. Big vault? `/gtd-organize`. Light model? `python3 scripts/lean_mode.py on`. Still compacting?
   `python3 scripts/context_report.py` shows what filled the last session (see `docs/gtd/light-models.md`).

## Conventions
Tasks are markdown checkboxes. Contexts: `#computer #phone #errands #home #office #anywhere #agenda #unknown`.
Status: `#next` `#waiting` `#someday`. Fields: `[due:: ]` `[scheduled:: ]` `[since:: ]`. Full spec:
`30 Resources/GTD System.md`.

## Optional components (git submodules)
Obsidian plugins (`.obsidian/plugins/*`), `vendor/whisper-cpp` and `scripts/quick_capture` are git
submodules, each in its own repo — all optional. Clone with
`git clone --recurse-submodules`; in an existing clone `git submodule update --init [<path>...]`.
`git submodule status` marks unchecked-out ones with `-`. After checking out plugins, run `gtd-setup`
to apply the vault's plugin presets. Not in git, downloaded on demand: the Whisper model
(`vendor/whisper-cpp/download-model.ps1`) and `outlook-mcp-rs.exe` (gtd-setup on Windows, or
`vendor/outlook-mcp-rs/download-outlook-mcp-rs.ps1`; then set `OUTLOOK_MCP_BIN` to it). List and upstreams: `README.md` → "Optional components".

## Harness notes
- Skills are discovered from `.claude/skills/` by Claude Code, opencode, and Claudian (the Obsidian
  plugin that runs one of those agents in a side panel — the recommended way to use the vault).
- MCP: Claude Code reads `.mcp.json`; opencode reads `opencode.json`. Both launch the Outlook server
  from `$OUTLOOK_MCP_BIN`.
- The session brief is the `gtd-status` skill. Claude Code additionally auto-runs it via a
  `SessionStart` hook (`.claude/settings.json`); other harnesses: run `/gtd-status`.
- Optional: `gtd-maintain` runs a lightweight vault health pass; schedule it per harness if wanted.
- Outside any harness: `scripts/quick_capture/` (Windows tray app) adds global shortcuts that write
  captures to `00 Inbox/` in the same format as `gtd-capture`. See `docs/gtd/quick-capture.md`.
