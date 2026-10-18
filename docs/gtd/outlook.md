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
A prebuilt binary (release v0.3.0) comes with the optional `vendor/outlook-mcp-rs` submodule
([adamkopelman/outlook-mcp-rs-bin](https://github.com/adamkopelman/outlook-mcp-rs-bin)) at
`vendor/outlook-mcp-rs/outlook-mcp-rs.exe` — `git submodule update --init vendor/outlook-mcp-rs` if
you didn't clone with `--recurse-submodules`. You only need to build it yourself (above) or download
it from the [releases](https://github.com/adamkopelman/outlook-mcp-rs/releases) to get a different
version. On a day-first Windows locale (e.g. en-IL), v0.3.0's MCP date filters can return the wrong
range ([issue #1](https://github.com/adamkopelman/outlook-mcp-rs/issues/1), fixed on upstream `main`,
not yet released) — build `main` and point `OUTLOOK_MCP_BIN` at that `target\release\outlook-mcp-rs.exe`
instead. The local dashboard already works around it.

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
