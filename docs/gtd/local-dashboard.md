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

- Shows inbox size, tasks (grouped by context), due-soon, waiting-for, active projects, and
  someday/maybe on one no-scroll screen.
- Checking a task's box, editing its text or due date, or deleting it writes straight to the real
  `.md` file — Obsidian and the browser page never disagree, because there's only ever one copy of
  the data.
- "New task" (press `n` or use the form) captures to `00 Inbox/` if you don't pick a project, or
  inserts under that project's `## Next actions` heading if you do — matching `/gtd-capture`'s and
  QuickAdd's conventions.
- Auto-refreshes every ~4 seconds, so edits made directly in Obsidian show up here too.

## Safety model

Every write re-reads its target file immediately before editing and matches the exact line of text
it's changing — never a stored line number, which could point at the wrong line if the file changed
in between. If that exact line isn't there anymore (you edited it elsewhere in the last few
seconds), the write is refused rather than applied to the wrong line; the page just re-fetches
current state on its next poll.
