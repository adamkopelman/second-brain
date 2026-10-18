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
