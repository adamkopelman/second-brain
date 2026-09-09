# Vendored binaries

## outlook-mcp-rs
Prebuilt MCP server that drives the classic Outlook desktop app on Windows (26 email/calendar/task/
note tools). Committed so the repo is self-contained.

- **Source:** https://github.com/adamkopelman/outlook-mcp-rs (release: latest)
- **File:** `outlook-mcp-rs.exe`
- **Platform:** Windows x86-64 (PE32+). Does nothing on macOS/Linux.
- **sha256:** `b033325029562cac858551052ce6870010ecf8c9325206cf0233f45212619048`
- **Use:** set `OUTLOOK_MCP_BIN` to this file's absolute path; both `.mcp.json` and
  `opencode.json` launch it. Requires Outlook running and signed in. See `docs/gtd/outlook.md`.
- **Updating:** rebuild with `cargo build --release` on Windows (or download a newer release
  asset) and replace this file.
