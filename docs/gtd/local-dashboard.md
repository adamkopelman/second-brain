# Local dashboard server

A second, independent way to view and edit this vault's GTD state — a plain browser page instead
of Obsidian. Complements (doesn't replace) `Dashboard.md` + QuickAdd in Obsidian, which keeps
working on its own.

## Run it

```
python scripts/dashboard_server.py            # serves the repo root as the vault, port 8787
python scripts/dashboard_server.py /path/to/vault --port 9000
python scripts/dashboard_server.py --no-outlook   # don't read the Outlook calendar
```

Leave that process running and open `http://localhost:8787` (or your chosen port) in a browser
tab. It's local-only — the server binds to `127.0.0.1`, so nothing outside your machine can reach
it, and there's no login because there's nothing to log into.

## What it does

- Six pages: `1 Today · 2 Week · 3 Tasks · 4 Inbox · 5 Waiting · 6 Projects`. Each tab shows its
  count and a red dot when something on it needs attention; the page is kept in the URL (`#today`,
  `#week`, …).
- **Today** (the landing page): today's Outlook meetings, then what's overdue, due today, and due this
  week, then "Needs attention" (inbox to process, tasks needing triage, project reviews, meetings to
  transcribe or summarize) and "On your lists" reminders (waiting-for, other next actions). Empty
  groups are hidden.
- **Week**: the 7 days (today + the next 6) side by side, each with its meetings and tasks due.
  Overdue tasks stay on Today; the Week page links to them in one line.
- More than 3 overdue project reviews show as one "N project reviews overdue" line (Enter jumps to
  Projects) instead of one line per project.
- **Tasks** (by context, with needs-triage on top), **Inbox** (every capture in `00 Inbox/`; `Enter`
  opens one in Obsidian — clarify them with `/gtd-process-inbox`), **Waiting**, **Projects** (active +
  someday/maybe).
- Fully keyboard-driven: `1`–`6` switch pages, `j`/`k` (or `↓`/`↑`) move through rows, `h`/`l` (or
  `←`/`→`) move between columns, `Enter` opens the selected row (or follows a Today-page link), `x`
  completes, `d` deletes, `u` undoes the last delete, `/` searches (press `Enter` to jump into the
  results), `n` adds a task, `r` records a meeting, `Esc` closes, and `?` shows the full list. Inside a
  task's detail view, `Enter` saves. Shortcuts are matched on the physical key, so they work the same
  with the keyboard switched to Hebrew (or any other layout); Hebrew task text reads right-to-left.
- Search filters the page you're on, and the tab counts show how many matches each page has. While a
  filter is active a banner says so; `Esc` (in the box or on the page) clears it.
- **Outlook calendar**: the server reads the next 7 days of your calendar through the vendored
  `outlook-mcp-rs` MCP server (`$OUTLOOK_MCP_BIN`, else `vendor/outlook-mcp-rs/outlook-mcp-rs.exe`),
  refreshing every minute in the background. Read-only — it only ever calls `list_events` — and
  meetings you declined are left out. Needs classic Outlook running (see `docs/gtd/outlook.md`); if it
  isn't reachable, Today says so in one line and everything else works as usual.
- **Record a meeting**: `r` or the **● Record** button starts recording your microphone (the browser
  asks for mic permission the first time); press again to stop. It's named after the Outlook meeting
  happening now (or starting within 10 minutes) and carries its attendees — or select a meeting on
  Today/Week and press `Enter` to record that one. On stop it's saved exactly like the Obsidian mic
  button (`Meetings/recordings/<stamp>.wav` + a linked `Meetings/<stamp> <title>.md` note) and
  transcribed automatically in the background. If saving fails, the audio is kept and the button
  offers a retry; closing the tab mid-recording asks first.
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
- Meeting follow-ups live on Today's "Needs attention": "N meetings to transcribe" (press `Enter` on it
  to transcribe recordings made elsewhere, e.g. with the Obsidian mic button), "N to summarize" (run
  `/gtd-summarize-meetings`), and "N failed to transcribe". Any task whose context came back
  `#unknown` from meeting summarization shows under "Needs triage" at the top of the Tasks page —
  resolve one by opening its detail overlay and picking a real context from the dropdown.
- The delete (×) button on a row only appears when you hover or select that row; it's also in every
  task's detail view.

## Safety model

Every write re-reads its target file immediately before editing and matches the exact line of text
it's changing — never a stored line number, which could point at the wrong line if the file changed
in between. If that exact line isn't there anymore (you edited it elsewhere in the last few
seconds), the write is refused rather than applied to the wrong line; the page just re-fetches
current state on its next poll.
