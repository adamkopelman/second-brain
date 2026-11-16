---
name: gtd-process-inbox
description: Use when the user wants to process, clarify, or empty their GTD inbox — walking each captured item through the GTD decision tree and filing it. Triggers on "process inbox", "clarify", "empty my inbox", "clear the inbox".
---

# GTD Process Inbox (Clarify & Organize)

Walk every item in `00 Inbox/` through the GTD clarify workflow until the inbox is empty. Read
`30 Resources/GTD System.md` first.

**Low-context start:** delegate to the `inbox-triage` subagent — it reads every item and returns a
one-line-per-item filing plan. Confirm the plan with the user (in batches), then apply it. Without
subagents: `python3 scripts/gtd_query.py inbox`, then open items one at a time.

## Process
Take files in `00 Inbox/` (ignore `README.md`) oldest first. For each, confirm before moving files:
1. Actionable? No → trash (delete), or reference (move to `30 Resources/` / `20 Areas/`,
   `type: reference`), or someday (`status: someday` project, or `#someday` task).
2. Actionable → one action or several?
   - Several (project) → new note in `10 Projects/` from `_templates/Project.md`; outcome +
     at least one `#next` action.
   - One action: <2 min → do now then delete; delegate → `#waiting` + `[[Person]]` +
     `[since:: today]`; defer → `#next` + context tag (or `[scheduled:: DATE]`).
3. Remove the processed file from `00 Inbox/` once filed.

## Rules
- End state: empty inbox (only `README.md`). Say so when done.
- Confirm before deleting anything the user might keep.
- Every touched project ends with at least one `#next` action.
