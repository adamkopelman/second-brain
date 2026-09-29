# Local dashboard server

A second, independent way to view and edit this vault's GTD state — a browser page modelled on
[Things 3](https://culturedcode.com/things/) instead of Obsidian. Complements (doesn't replace)
`Dashboard.md` + QuickAdd in Obsidian, which keeps working on its own.

## Run it

```
python scripts/dashboard_server.py            # serves the repo root as the vault, port 8787
python scripts/dashboard_server.py /path/to/vault --port 9000
python scripts/dashboard_server.py --no-outlook   # don't read the Outlook calendar
```

Leave that process running and open `http://localhost:8787` (or your chosen port) in a browser
tab. It's local-only — the server binds to `127.0.0.1`, so nothing outside your machine can reach
it, and there's no login because there's nothing to log into.

## How the vault maps onto Things

Nothing new is stored anywhere: every list is a view over the same markdown checkboxes, tags and
fields described in `30 Resources/GTD System.md`.

| Things | In the vault |
| --- | --- |
| **Inbox** | Everything in `00 Inbox/` — checkbox captures as to-dos, plain captures as notes (open in Obsidian). |
| **Today** | Open to-dos with `[scheduled:: ]` today or earlier, or `[due:: ]` today or overdue (overdue first), under today's Outlook meetings. |
| **This Evening** | Today's to-dos that also carry `#evening`. |
| **Upcoming** | The next seven days one by one — each with its meetings and to-dos scheduled (or, if unscheduled, due) that day — then later months. |
| **Anytime** | Every available next action: `#next` (and any to-do inside a project or area note) that isn't scheduled ahead, grouped by project and area. |
| **Someday** | `#someday` to-dos, and projects with `status: someday`. |
| **Waiting** | `#waiting` to-dos, oldest first, with how many days you've been waiting (red after a week). Not in Things — it's GTD's. |
| **Logbook** | Checked-off to-dos, grouped by the `[completion:: ]` date the dashboard stamps (Obsidian Tasks' `✅ date` is read too). |
| **Areas** | Notes in `20 Areas/`, plus any `area: "[[…]]"` a project names. An area lists its active projects and its own to-dos. |
| **Projects** | `10 Projects/*.md` with `status: active` (sidebar) or `someday`. The ring fills in as to-dos get done; the note's `## headings` become Things' headings; `**Outcome:**` shows as the project's notes. |
| **When** | `[scheduled:: DATE]` — Today, This Evening (`#evening`), a date, Someday (`#someday`), or cleared (Anytime). |
| **Deadline** | `[due:: DATE]` — a red flag with "3 days left" / "2 days ago". |
| **Tags** | The GTD contexts (`#computer`, `#phone`, …) plus any other tags; the tag bar above a list filters it. |

## Working in it

- **Sidebar**: Inbox; Today (red badge = deadlines due or overdue, grey = the rest), Upcoming,
  Anytime, Someday, Waiting; Logbook; then projects without an area, then each area with its
  projects. A red dot marks a project that's due for review. The URL follows the list (`#today`,
  `#project/Website%20Redesign`, …), so reload and Back keep your place.
- **To-dos**: click to select, click again (or double-click, or `Enter`) to open it as a card —
  edit the title in place, and set When, Deadline, tag, or Move from the card's toolbar. The title
  saves when you close the card (`Enter`, `Esc`, or click outside). On a touch screen one tap opens.
  Items that are in Today show a ★ (or ☾ for This Evening) in every other list.
- **Checking a box** strikes the to-do through; it moves to the Logbook a moment later (click again
  to change your mind). In the Logbook, unchecking reopens it.
- **New To-Do** (`n`, `Space`, or `+` in the bottom bar) opens a card at the top of the list you're
  on and files it there: Today → scheduled today, Upcoming → tomorrow, Someday → `#someday`, a
  project or area → under its `## Next actions`, anywhere else → a new capture in `00 Inbox/`. Type
  `#phone` etc. in the title to tag it. `Enter` saves and starts the next one; `Esc` stops.
- **When** (`w`, or the calendar button): Today, This Evening, a month calendar, Someday, or
  Clear — or type "fri", "next week", "in 3 days", "oct 3" and press `Enter`.
- **Move** (`m`, or the arrow button): pick the Inbox, a project, or an area (type to narrow it).
  Moving the only line out of an inbox capture removes that capture — the item's been processed.
- **Quick Find** (`/` or `f`): lists, areas, projects, tags and to-dos by name; `Enter` jumps
  there, opening the to-do you picked.
- **Projects**: the `…` menu marks the project reviewed (next review in 7 days), moves it to or from
  Someday, completes it (`status: done`, `completed:` date — it leaves the sidebar), or opens it in
  Obsidian. "Show N logged items" reveals its finished to-dos.
- **Delete** (`d`/`Delete`, or the bin on the card) hides the to-do with an **Undo** toast for 5
  seconds (`u` also undoes); only then is the line removed from its note.
- **Today's heads-up lines** (above the to-dos) flag what the lists can't: to-dos from meetings
  whose context came back `#unknown` (opens Anytime filtered to them — open each and pick a real
  tag), projects due for review, and meetings to transcribe (press `Enter` on it to run
  transcription), to summarize (run `/gtd-summarize-meetings`) or that failed.
- Linked notes on a to-do (e.g. the `[[Person]]` on a `#waiting` item) show as chips beside its
  title, and Quick Find matches them too. Hebrew (or any right-to-left) text reads right-to-left.
- Light and dark themes follow your system until you pick one (the ◐ button). On a narrow window the
  sidebar tucks behind the ☰ button.

## Keyboard

| Key | Does |
| --- | --- |
| `1`–`7` | Inbox, Today, Upcoming, Anytime, Someday, Waiting, Logbook |
| `j` / `↓`, `k` / `↑` | Next / previous item |
| `Enter` | Open the selected to-do (on a meeting: record it; on a heads-up line: follow it) |
| `Esc` | Close the open to-do or popover; then clear the tag filter |
| `n` or `Space` | New To-Do here |
| `x` | Complete the selected to-do |
| `t` · `e` · `s` · `a` | When: Today · This Evening · Someday · Anytime (no date) |
| `w` | When… |
| `m` | Move… |
| `d` or `Delete` | Delete (5 s to undo); `u` undoes |
| `o` | Open the to-do's note in Obsidian |
| `/` or `f` | Quick Find |
| `r` | Record a meeting / stop |
| `?` | Show the shortcuts |

Shortcuts are matched on the physical key, so they work the same with the keyboard switched to
Hebrew (or any other layout).

## Outlook calendar and meeting recording

- The server reads the next 7 days of your calendar through the vendored `outlook-mcp-rs` MCP
  server (`$OUTLOOK_MCP_BIN`, else `vendor/outlook-mcp-rs/outlook-mcp-rs.exe`), refreshing every
  minute in the background. Read-only — it only ever calls `list_events` — and meetings you declined
  are left out. Today lists today's meetings (dimmed once over); Upcoming lists each day's. Needs
  classic Outlook running (see `docs/gtd/outlook.md`); if it isn't reachable, Today says so in one
  line and everything else works as usual.
- **Record** (bottom bar, or `r`) records your microphone (the browser asks for mic permission the
  first time); press again to stop. It's named after the Outlook meeting happening now (or starting
  within 10 minutes) and carries its attendees — or select a meeting and press `Enter` to record that
  one. On stop it's saved exactly like the Obsidian mic button (`Meetings/recordings/<stamp>.wav` + a
  linked `Meetings/<stamp> <title>.md` note) and transcribed automatically in the background. If
  saving fails, the audio is kept and the button offers a retry; closing the tab mid-recording asks
  first.

## Safety model

Every write re-reads its target file immediately before editing and matches the exact line of text
it's changing — never a stored line number, which could point at the wrong line if the file changed
in between. If that exact line isn't there anymore (you edited it elsewhere in the last few
seconds), the write is refused rather than applied to the wrong line and the page says so; it
re-fetches current state on its next poll (every ~4 seconds, so edits made in Obsidian show up here
too). Obsidian and the browser page never disagree, because there's only ever one copy of the data.

## API

All `POST`s take and return JSON and are refused from other origins.

| Endpoint | Body |
| --- | --- |
| `GET /api/state` | → `todos`, `projects`, `areas`, `inbox_notes`, `meetings`, `calendar`, `vault_name` |
| `/api/new-task` | `text`, `context?`, `project?` or `area?`, `when?`, `deadline?`, `status?` (`next`/`waiting`/`someday`) |
| `/api/edit-task` | `file`, `line_text`, `new_text?`, `new_due?` (`""` clears), `new_context?`, `new_when?` (`today`/`evening`/`someday`/`anytime`/ISO date) |
| `/api/complete-task`, `/api/uncomplete-task`, `/api/delete-task` | `file`, `line_text` |
| `/api/move-task` | `file`, `line_text`, `project?` or `area?` (neither: back to the inbox) |
| `/api/new-project` | `title`, `area?` |
| `/api/project-status` | `project`, `status` (`active`/`someday`/`done`) |
| `/api/review-project` | `project`, `days?` (default 7) |
| `/api/transcribe` | — |
| `/api/record-meeting` | raw 16 kHz mono PCM; `started`, `title`, `attendees` in the query |
