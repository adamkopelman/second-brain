---
name: gtd-maintain
description: Use when the user wants a health check of their GTD vault, or to run a maintenance pass — finding stuck projects, stale waiting-for items, overdue reviews, and archive candidates. Triggers on "maintain", "health check", "tidy the vault", "what's stuck", "gtd maintenance".
---

# GTD Maintain (health pass)

A read-only audit that surfaces problems and *proposes* fixes (never auto-edits without confirming).
Read `30 Resources/GTD System.md`. Runs in any harness; can be scheduled (see below).

## Checks
1. **Stuck projects** — `status: active` notes in `10 Projects/` with no open `#next` task.
2. **Stale waiting-for** — `#waiting` tasks whose `[since:: DATE]` is > 14 days ago.
3. **Overdue reviews** — active projects whose `review:` date is in the past.
4. **Aging inbox** — count of `00 Inbox/` items (excluding `README.md`); flag if not empty.
5. **Archive candidates** — `status: done` projects still outside `40 Archive/`.

## Output
A short report grouped by check, each item naming the file. Then offer concrete fixes:
add a `#next`, ping a person (`#agenda`), bump `review:`, archive a done project — applying only
what the user approves.

## Scheduling (optional, per harness)
- Claude Code: a Routine / cron that sends "run /gtd-maintain and summarize" on a schedule.
- opencode / other: the harness's own scheduler, or a system cron invoking the agent.
Keep scheduled runs read-only (report only); apply fixes interactively.

## Rules
- Read-only by default; confirm before any edit or archive move. Never delete notes.
