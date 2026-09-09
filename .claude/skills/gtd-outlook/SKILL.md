---
name: gtd-outlook
description: Use when the user wants to bring Microsoft Outlook email or calendar into their GTD second brain — turning flagged/starred emails into inbox items or pulling the calendar into the weekly review. Triggers on "outlook", "my email", "flagged emails to inbox", "pull my calendar".
---

# GTD Outlook bridge

Bridges the `outlook` MCP server (from outlook-mcp-rs) into GTD flows. Capture-only by default —
never sends mail or changes calendar events unless the user explicitly asks.

## Preconditions
The `outlook` MCP server must be configured (`.mcp.json` / `opencode.json`) and reachable — that
means classic Outlook running and signed in on a Windows machine, with `$OUTLOOK_MCP_BIN` set. If
its tools aren't available, tell the user how to enable it (`docs/gtd/outlook.md`) and stop.

## Flows
### Email → inbox
1. Use the Outlook tools to list flagged/important unread emails (`list_emails`, then `get_email`).
2. For each, run the capture pattern: write a file to `00 Inbox/` with the subject as the item, the
   sender and a one-line summary, and the Outlook item id / a note to find it. Mark `type: inbox`.
3. Do not mark the email read or reply. Report how many were captured; the user runs
   `/gtd-process-inbox` next.

### Calendar → weekly review
1. During `/gtd-weekly-review`, use `list_events` for the next two weeks.
2. Summarize commitments so they're reviewed alongside projects. Do not create events.

## Rules
- Read/capture only unless explicitly asked to send or schedule (then confirm first).
- Nothing is auto-filed — captured items land in `00 Inbox/` for normal processing.
