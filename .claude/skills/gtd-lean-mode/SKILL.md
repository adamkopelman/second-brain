---
name: gtd-lean-mode
description: Use when the agent keeps compacting, runs out of context, is slow or costly, or runs on a light/small model (DeepSeek Flash, Haiku-class, local models) — switches the vault into lean mode and explains the low-context way of working. Triggers on "lean mode", "too much context", "keeps compacting", "save tokens", "light model".
---

# GTD Lean Mode

## Switch
- Check: `python3 scripts/lean_mode.py status`
- On: `python3 scripts/lean_mode.py on` (add `--keep-outlook` if the user uses `/gtd-outlook`)
- Off: `python3 scripts/lean_mode.py off`
Tell the user to **restart the session** afterwards (skills/settings load at start).

`on` parks the 14 developer skills (Superpowers) that load into every session, writes
per-machine deny rules and output caps to `.claude/settings.local.json`, and disables the Outlook
MCP server. Fully reversible; `git status` stays clean.

## Then work the lean way (also in AGENTS.md → "Context budget")
- Answer from `python3 scripts/gtd_query.py <brief|next|waiting|inbox|projects|health|meetings|find|sizes>`
  before reading any note.
- Heavy reading goes to subagents: `vault-scout` (lookups), `inbox-triage` (inbox plan),
  `meeting-summarizer` (one meeting each), `vault-organizer` (housekeeping).
- Run `/gtd-organize` every week or two so transcripts and finished work leave the hot path.
- One GTD task per session; `/clear` between tasks instead of letting it compact.
