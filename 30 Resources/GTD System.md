---
type: reference
tags: [system, gtd]
---

# GTD System — How This Vault Works

PARA-style folders say *where things live*; tags + frontmatter say *what state things are in*. The
dashboards read these conventions, so keeping to them keeps everything in sync.

## Steps → where
Capture → `00 Inbox/` (`/gtd-capture`). Clarify → `/gtd-process-inbox`. Organize → Projects/Areas/
Resources or tasks. Reflect → `/gtd-weekly-review` + `Weekly Review.md`. Engage → `Dashboard.md`,
`/gtd-next-actions`, `/gtd-status`.

## Folders (PARA)
`00 Inbox/` unprocessed · `10 Projects/` outcomes needing >1 action · `20 Areas/` ongoing
responsibilities · `30 Resources/` reference · `40 Archive/` inactive · `Journal/` dailies ·
`People/` per-person · `Meetings/` notes.

## Tasks
Checkboxes inside project/daily notes, with tags + inline fields:

    - [ ] Draft the Q3 proposal #next #computer [due:: 2026-09-20] [[Q3 Proposal]]
    - [ ] Waiting on Sam for figures #waiting [[Sam Rivera]] [since:: 2026-09-08]
    - [ ] Someday: learn to sail #someday

Contexts (one per action): #computer #phone #errands #home #office #anywhere #agenda (pair #agenda
with [[Person]]). Status: #next (ready now — shown on dashboard), #waiting (delegated; + [[Person]] +
[since:: DATE]), #someday. Fields: [due:: DATE], [scheduled:: DATE] (tickler), [since:: DATE].

Rule of thumb: every active project has at least one #next action.

## Project frontmatter

    ---
    type: project
    status: active        # active | someday | done
    area: "[[Career]]"
    created: 2026-09-09
    review: 2026-09-16
    ---

## People frontmatter

    ---
    type: person
    tags: [person]
    ---

## Required plugins
Dataview powers `Dashboard.md` (Settings → Community plugins → Dataview). QuickAdd powers the
dashboard's Actions row (Settings → Community plugins → QuickAdd) — see
`docs/gtd/obsidian-plugins.md` for its configured choices. Or use `/gtd-dashboard` for a portable
`dashboard.html` that needs no plugin (note its Actions row won't be clickable there either way).
