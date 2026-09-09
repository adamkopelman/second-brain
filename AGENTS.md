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
