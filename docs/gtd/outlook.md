# Outlook MCP integration

The `gtd-outlook` skill uses [`outlook-mcp-rs`](https://github.com/adamkopelman/outlook-mcp-rs), an
MCP server that drives the classic Outlook desktop app on Windows (26 tools: email, calendar, tasks,
notes). No auth/tokens — it uses your signed-in Outlook session.

## Requirements
- Windows with the classic Outlook desktop app installed and signed in.
- Rust (2024 edition) to build, or a prebuilt binary.

## Build
    git clone https://github.com/adamkopelman/outlook-mcp-rs
    cd outlook-mcp-rs
    cargo build --release
    # → target/release/outlook-mcp-rs.exe

## Point the vault at it
The binary isn't committed. On Windows, `/gtd-setup` (`python .claude/skills/gtd-setup/apply.py .`)
downloads the prebuilt release **v0.3.0** from the
[releases](https://github.com/adamkopelman/outlook-mcp-rs/releases), verifies its SHA-256 and saves
it as `vendor/outlook-mcp-rs/outlook-mcp-rs.exe` (git-ignored). To fetch it on its own:

    powershell -ExecutionPolicy Bypass -File vendor\outlook-mcp-rs\download-outlook-mcp-rs.ps1 -SetUserEnv

(`-SetUserEnv` also sets `OUTLOOK_MCP_BIN` for you; `-Force` re-downloads over an existing exe;
offline, it stops with a clear error and installs nothing. `sh vendor/outlook-mcp-rs/download-outlook-mcp-rs.sh`
does the same from Git Bash.) Setup never overwrites an exe that's already there, so a build of your
own (above) can live at that path too.

On a day-first Windows locale (e.g. en-IL), v0.3.0's MCP date filters can return the wrong range
([issue #1](https://github.com/adamkopelman/outlook-mcp-rs/issues/1), fixed on upstream `main` but not
in any release yet — v0.3.0 is the latest) — build `main` and point `OUTLOOK_MCP_BIN` at that
`target\release\outlook-mcp-rs.exe` (or copy it over `vendor\outlook-mcp-rs\outlook-mcp-rs.exe`). The
local dashboard already works around it.

Set an environment variable to the binary's full path (both harness configs read it):

    setx OUTLOOK_MCP_BIN "%CD%\vendor\outlook-mcp-rs\outlook-mcp-rs.exe"   # from the repo root, Windows

- Claude Code reads `.mcp.json` → server `outlook` → `command: ${OUTLOOK_MCP_BIN}`.
- opencode reads `opencode.json` → `mcp.outlook.command: ["{env:OUTLOOK_MCP_BIN}"]`.

Restart the harness. Outlook must be running. Then `/gtd-outlook` can pull flagged email into
`00 Inbox/` and surface your calendar during the weekly review.

## Not on Windows?
Everything else in the vault works without Outlook. The `outlook` server just won't start, and
`gtd-outlook` will say it's unavailable. (Network mode: `outlook-mcp-rs.exe --http --port 8080
--token SECRET` exposes it over HTTP if you run Outlook on a separate Windows box.)
