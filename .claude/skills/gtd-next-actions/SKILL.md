---
name: gtd-next-actions
description: Use when the user asks what to work on now, wants their next actions, or filters tasks by context/time/energy. Triggers on "what should I do", "next actions", "what's on my list", "what can I do at my computer", "what's due".
---

# GTD Next Actions (Engage)

Help the user decide what to do now. Read `30 Resources/GTD System.md`. Read-only unless asked to
check something off.

## Steps
1. Grep open `#next` tasks (unchecked, not `#waiting`) across `00 Inbox/`, `10 Projects/`,
   `20 Areas/`, `Journal/`, `People/`, `Meetings/` (skip `40 Archive/`, `_templates/`, reference docs).
2. Hide items whose `[scheduled:: DATE]` is in the future.
3. If given a context (`@computer`, "phone", "errands"), filter to that context tag. If given
   time/energy, prefer short/low-effort items and say why.
4. Show due/overdue (`[due:: DATE]`) first, then group by context; each line: action, project
   (from `[[link]]`), due date. Keep to 5–10 items.
5. Offer to check one off or start one.

## Rules
- Never invent tasks. If nothing is queued, suggest `/gtd-process-inbox` or `/gtd-weekly-review`.
