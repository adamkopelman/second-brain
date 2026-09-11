# Local dashboard server

A second, independent way to view and edit this vault's GTD state — a plain browser page instead
of Obsidian. Complements (doesn't replace) `Dashboard.md` + QuickAdd in Obsidian, which keeps
working on its own.

## Run it

```
python scripts/dashboard_server.py            # serves the repo root as the vault, port 8787
python scripts/dashboard_server.py /path/to/vault --port 9000
```

Leave that process running and open `http://localhost:8787` (or your chosen port) in a browser
tab. It's local-only — the server binds to `127.0.0.1`, so nothing outside your machine can reach
it, and there's no login because there's nothing to log into.

## What it does

- Opens on a **Today** page: what's overdue, due today, and due this week, then a short "Needs
  attention" list (inbox to process, tasks needing triage, project reviews, meetings to transcribe or
  summarize) and "On your lists" reminders (waiting-for, other next actions). Empty groups are hidden.
- The rest lives on four more pages — **Tasks** (by context, with needs-triage on top), **Waiting**,
  **Projects** (active + someday/maybe) and **Meetings**. Each tab shows its count and a red dot when
  something on it needs attention. The page is kept in the URL (`#today`, `#tasks`, …).
- Fully keyboard-driven: `1`–`5` switch pages, `j`/`k` (or `↓`/`↑`) move through rows, `Enter` opens
  the selected row (or follows a Today-page link), `x` completes, `d` deletes, `u` undoes the last
  delete, `/` searches (press `Enter` to jump into the results), `n` adds a task, `Esc` closes, and
  `?` shows the full list. Inside a task's detail view, `Enter` saves.
- Search filters the page you're on; the tab counts show how many matches each page has.
- Checking a task's box, editing its text or due date, or deleting it writes straight to the real
  `.md` file — Obsidian and the browser page never disagree, because there's only ever one copy of
  the data. Deleting shows an **Undo** for 5 seconds; the line is only removed from the file once
  that window closes.
- Linked notes on a task (e.g. the `[[Person]]` on a `#waiting` item) show as chips beside its text,
  and search matches them too.
- "New task" (press `n` or use the form) captures to `00 Inbox/` if you don't pick a project, or
  inserts under that project's `## Next actions` heading if you do — matching `/gtd-capture`'s and
  QuickAdd's conventions.
- Auto-refreshes every ~4 seconds, so edits made directly in Obsidian show up here too.
- The Meetings page lists recent meetings (transcription/summary status at a glance) with a
  "Transcribe pending" button. Any task whose context came back `#unknown` from meeting summarization
  shows under "Needs triage" at the top of the Tasks page — resolve one by opening its detail overlay
  and picking a real context from the dropdown.
- The delete (×) button on a row only appears when you hover or select that row; it's also in every
  task's detail view.

## Safety model

Every write re-reads its target file immediately before editing and matches the exact line of text
it's changing — never a stored line number, which could point at the wrong line if the file changed
in between. If that exact line isn't there anymore (you edited it elsewhere in the last few
seconds), the write is refused rather than applied to the wrong line; the page just re-fetches
current state on its next poll.
