---
name: gtd-organize
description: Use when the user wants to organize, tidy, clean up, or shrink the vault — archiving finished projects, old meetings and dailies, and moving long transcripts out of the way so agents read less and compact less. Triggers on "organize the vault", "tidy up", "clean up", "archive old stuff", "the vault is too big", "gtd organize". Run every week or two.
---

# GTD Organize (housekeeping)

Keeps the working set small. Mechanical work is done by `scripts/vault_tidy.py`; the
`vault-organizer` subagent runs it so the details never enter this conversation.

## Steps
1. Delegate a **dry run**: Task/Agent → `vault-organizer`, prompt: "dry run".
   (No subagents in this harness? Run `python3 scripts/vault_tidy.py` and
   `python3 scripts/gtd_query.py health` yourself.)
2. Show the user the report (it is ≤20 lines). Ask: apply all, apply some steps
   (`--only projects,meetings,journal,transcripts`), or skip.
3. On yes: Agent → `vault-organizer`, prompt: "apply" (or "apply --only …"). Relay its summary.
4. Health issues (stuck projects, stale waiting-fors) need the user: offer `/gtd-weekly-review`
   or fix one at a time. Never invent `#next` actions.

## Rules
- Dry run first, always. Nothing is deleted: everything moves into `40 Archive/`, and anything
  with an open `- [ ]` task stays put.
- Thresholds: meetings 90 days, dailies 60 days, transcripts > 4000 chars (flags on the script).
