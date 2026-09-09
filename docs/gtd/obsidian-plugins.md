# Obsidian plugins for this vault

## Required
### Dataview — powers `Dashboard.md`
1. Settings → Community plugins → turn off Restricted mode (first time).
2. Browse → "Dataview" → Install → Enable.
3. Reopen `Dashboard.md`; the query blocks render.
Without Dataview, use `/gtd-dashboard` (the portable `dashboard.html`) instead — no plugin needed.

## Optional
- **Smart Second Brain** (`obsidian-smart2brain`) — semantic / RAG search + an AI assistant that
  knows your notes. Complements Dataview: Dataview does *structured* queries (tags, fields),
  Smart Second Brain does *fuzzy/semantic* retrieval ("what did I note about pricing?"). Install via
  Community plugins → "Smart Second Brain".
- **Tasks** — richer task querying/recurrence; compatible with our checkbox conventions.
- **Calendar** — month view tied to `Journal/` daily notes.
- **Templater** — dynamic templates; our `_templates/` use core Templates and work without it.

## Core plugins already enabled
Templates (`_templates`), Daily notes (`Journal`, template `_templates/Daily Note.md`), Properties,
Tag pane, Backlinks, Graph — see `.obsidian/core-plugins.json`.
