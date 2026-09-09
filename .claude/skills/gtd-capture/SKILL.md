---
name: gtd-capture
description: Use when the user wants to quickly capture a thought, task, idea, link, or note into their GTD second brain without organizing it yet. Triggers on "capture", "add to inbox", "jot down", "remind me to", "note that".
---

# GTD Capture

Friction-free capture into `00 Inbox/`. Speed over organization — do not clarify or file it
(that's `/gtd-process-inbox`).

## Steps
1. Write what the user said to a new file in `00 Inbox/`.
2. Filename: `<today> <short-slug>.md`, e.g. `00 Inbox/2026-09-09 call-dentist.md`.
3. Contents — checkbox if it's clearly an action, plain text otherwise:
   ```
   ---
   type: inbox
   captured: 2026-09-09
   ---
   - [ ] Call the dentist to reschedule
   ```
4. Confirm in one line: "📥 Captured to inbox."

## Rules
- Never route to a project/area during capture. Everything lands in `00 Inbox/`.
- Multiple items → one file each (or one file with several checkboxes if clearly related).
- Single confirmation line only.
