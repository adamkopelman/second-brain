---
name: gtd-status
description: Use when the user opens the vault or asks for a status brief / overview of their GTD system — inbox size, active projects, weekly-review recency, and next actions ready now. Triggers on "status", "brief me", "where am I", "gtd status", "what's my day".
---

# GTD Status (brief)

Print a short, read-only brief. Works in any harness (no dependency on hooks). If the shell hook
`.claude/hooks/gtd-status.sh` exists you may run it for speed; otherwise compute directly.

## Compute
1. **Inbox:** count files in `00 Inbox/` excluding `README.md`.
2. **Active projects:** notes in `10 Projects/` whose frontmatter has `status: active`.
3. **Weekly review recency:** most recent `Journal/` note containing `weekly-review`
   (exclude `README.md`); report age in days; flag if ≥7 or none.
4. **Next actions ready:** up to 5 open `#next` tasks (not `#waiting`, `[scheduled::]` not in the
   future), across content folders (skip `40 Archive/`, `_templates/`, reference docs).

## Output (example shape)
```
🧠 Second Brain — GTD status
📥 Inbox: 3 to process · 📋 5 active projects
⚠️  Weekly review is 9 days old — run /gtd-weekly-review
⚡ Next actions ready:
   • Draft Q3 proposal  (Q3 Proposal)  📅 2026-09-20
```

## Rules
- Read-only. Keep it to a few lines. Never invent tasks.
