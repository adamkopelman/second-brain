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
- Install: it's the `.obsidian/plugins/realclaudian` submodule (`git submodule update --init
  .obsidian/plugins/realclaudian`), or Community plugins → "Claudian"; it requires a CLI agent
  already installed on your machine.
- Skills: it runs the underlying agent, which discovers `.claude/skills/` — all `gtd-*` skills work.
- MCP/brief: inherited from whichever agent Claudian runs (Claude Code → `.mcp.json` + hook;
  opencode → `opencode.json` + `/gtd-status`).
- This is the recommended day-to-day setup: live `Dashboard.md` and skills in one window.

## Optional components (git submodules)
The Obsidian plugins, whisper.cpp, the outlook-mcp-rs binary and Quick Capture are git submodules,
each in its own repository (the list, with upstreams and licenses, is in `README.md` →
"Optional components"). The skills, scripts, dashboards and notes all live in this repo and work
without any of them.
- Everything: `git clone --recurse-submodules https://github.com/adamkopelman/second-brain.git`, or
  `git submodule update --init` in an existing clone.
- Only some: `git clone https://github.com/adamkopelman/second-brain.git`, then
  `git submodule update --init <path> ...` — e.g. `.obsidian/plugins/dataview .obsidian/plugins/quickadd`
  for the live dashboard. A submodule you never initialize stays an empty folder and costs nothing.
- After checking out plugins, run `/gtd-setup` (or `python .claude/skills/gtd-setup/apply.py .`) to
  apply the vault's plugin presets.
- Updates: `git pull` then `git submodule update --init --recursive` brings the submodules to the
  commits this repo pins; `git submodule update --remote` moves them to their latest commits.

## Any other skills+MCP harness
- Place/point skills at `.claude/skills/`. Configure the Outlook server per that harness's MCP
  format using `$OUTLOOK_MCP_BIN`. Use `/gtd-status` for the brief.

## Principle
Every automatic behavior is also a skill, so no capability is locked to one harness. Claude-only
extras (e.g. publishing the dashboard as an Artifact) are optional bonuses, never the only path.
