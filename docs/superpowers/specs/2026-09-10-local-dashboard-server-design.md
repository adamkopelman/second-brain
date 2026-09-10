# Local Dashboard Server — Design

**Status:** Approved by user (via iterative Q&A this session), ready for implementation plan.
**Date:** 2026-09-10

## Problem

The Obsidian-based dashboard (`Dashboard.md` + QuickAdd, built earlier this session) is genuinely
live and interactive, but it's constrained by Obsidian's rendering pipeline: raw `innerHTML`
anchors don't get Obsidian's link-click interception (a real bug we had to work around), Canvas
can't run live queries at all, and every fix required the user to manually test in the Obsidian GUI
since no agent in this session has GUI access. The user's actual use case — a screen open ~80% of
the time, paired with Claude Code on a second monitor, showing everything with zero scrolling — is
better served by a normal browser tab than by fighting Obsidian's plugin sandbox.

## Goals

1. A local, `127.0.0.1`-only web page showing the user's GTD state (inbox, tasks, waiting, due,
   projects, someday) on one screen with no scrolling.
2. Full task CRUD from the page itself: complete, create, inline-edit (text + due date), delete —
   writing directly to the real vault `.md` files, so Obsidian and this page never disagree.
3. Stays live: auto-refreshes and picks up edits made elsewhere (e.g. directly in Obsidian) within
   a few seconds, no manual reload.
4. Zero new dependencies — stdlib-only Python backend, vanilla JS frontend — matching this repo's
   existing convention (`gtd-setup`, `scripts/build_dashboard.py` are both stdlib-only).
5. Comprehensive automated test coverage for both the backend (parsing, write-back, API) and the
   frontend (pure rendering/filtering logic), runnable without installing anything beyond what's
   already on the machine (Python's `unittest`/`pytest`, Node's built-in `node:test`).

## Non-goals

- Not replacing the Obsidian `Dashboard.md`/QuickAdd setup — that stays as-is, working, as a
  fallback if the user opens Obsidian directly. This spec adds a second, independent way to view
  and edit the same vault files.
- Not building project CRUD beyond view + create (renaming, status changes, outcome edits happen
  in the project note itself — projects have more fields than a task line and are edited rarely
  enough that this isn't worth the extra write-back surface).
- Not building inbox-processing UI (turning an inbox item into a task/project from the page) — the
  user explicitly declined this; `/gtd-process-inbox` remains the way to do that.
- Not building a weekly-review reminder banner — declined.
- No real-time push (WebSocket/SSE) — the user chose polling over a file-watcher; simpler, fewer
  moving parts, "a few seconds of staleness" is an accepted trade-off.
- No browser-based E2E testing (Playwright etc.) — would add an npm dependency this repo doesn't
  otherwise have. Frontend logic is instead structured as pure, dependency-free functions so it's
  unit-testable with Node's built-in test runner; DOM wiring itself is thin and not separately
  covered. This is a deliberate scope line, flagged here rather than silently skipped.

## Design

### Architecture

One new file, `scripts/dashboard_server.py` — a single stdlib-only Python script combining:
- The existing parsing logic from `scripts/build_dashboard.py` (task-line regex, tag/field/link
  stripping, project frontmatter reading), extended to track `(file, line_text)` per task instead
  of just aggregating counts, so writes can address an exact line.
- An `http.server.ThreadingHTTPServer` bound to `127.0.0.1` only, serving:
  - `GET /` — the HTML page shell (static, ships the CSS/JS inline or as sibling static files)
  - `GET /api/state` — current JSON snapshot (KPIs, tasks by context, due soon, waiting, active
    projects, someday)
  - `POST /api/complete-task` — `{file, line_text}`
  - `POST /api/new-task` — `{text, context, project?}`
  - `POST /api/edit-task` — `{file, line_text, new_text?, new_due?}`
  - `POST /api/delete-task` — `{file, line_text}`
  - `POST /api/new-project` — `{title}`

Run with `python scripts/dashboard_server.py` (default port 8787, overridable via `--port`); the
user leaves that process running and opens `http://localhost:8787` in a browser tab.

### Write-back addressing and safety

Every mutating endpoint identifies its target line by **exact current text match**, not a line
number — line numbers shift as a file is edited elsewhere between the dashboard's polls. On each
write:
1. Re-read the target file fresh from disk (never trust the in-memory state the last `/api/state`
   response was built from).
2. Search for a line whose content, after stripping trailing whitespace, exactly equals the
   `line_text` the client sent (which is exactly what the client's last successful `/api/state`
   or DOM update showed it).
3. If found exactly once, apply the edit and write the file back.
4. If not found (the line changed or was removed by an edit elsewhere since the client last
   polled) or found more than once (ambiguous), return an error status without writing anything;
   the client re-fetches `/api/state` and the user retries against current data. This is
   optimistic concurrency, not a lock — acceptable for a single-user local tool with a ~4s poll
   window, and it fails *safely* (refuses the write) rather than silently editing the wrong line.

`new-task` (no project): one file per item in `00 Inbox/`, filename
`00 Inbox/<today> <slug>.md`, frontmatter `type: inbox` / `captured: <date>` — matching
`.claude/skills/gtd-capture/SKILL.md`'s real convention (verified during the QuickAdd work
earlier this session).

`new-task` (project chosen): inserts `- [ ] <text> #next #<context>` under that project's
`## Next actions` heading, creating the heading at the top of the file if it's missing (same
resilience QuickAdd's "New Next Action" choice needed, for the same reason: a project file might
not have that heading yet).

`new-project`: copies `_templates/Project.md`, substitutes `{{title}}` and the two
`{{date:YYYY-MM-DD}}` occurrences (`created`, `review` — both today's date, matching the earlier
QuickAdd design decision) with plain Python string substitution, writes to
`10 Projects/<title>.md`.

### Frontend

Single HTML page, vanilla JS, no build step, no framework:
- Polls `GET /api/state` every 4 seconds; re-renders from the JSON response (not incremental DOM
  diffing — simple full re-render of each card from a pure `render(state)` function keeps the
  logic testable and avoids drift bugs).
- Layout: CSS Grid sized to fit one viewport (`100vh`/`100vw`-based, not content-flow-based) so
  the whole board is visible without scrolling, reusing the visual language already established in
  `.obsidian/snippets/dashboard.css` (card radii, KPI tile style, pill badges, overdue-red styling)
  translated to plain CSS custom properties instead of Obsidian's `var(--...)` theme tokens.
- Search/filter: a text input that filters the rendered task list client-side (no server round
  trip) by substring match against task text, project name, or context.
- Keyboard quick-add: a global `keydown` listener (ignored while an input/textarea has focus) that
  opens the new-task input on a dedicated key (`n`).
- Theme: a toggle button; choice persisted in `localStorage`; applied via a `data-theme` attribute
  on `<html>` with light/dark CSS variable blocks (light default, dark override).
- Pure logic — filtering, grouping-by-context, date-overdue calculation, HTML-escaping — lives in
  plain functions with no DOM/fetch dependency, importable by both the page (via `<script>`) and
  Node's test runner (via `require`/`import` in a CommonJS or ES-module file), so it's testable
  without a browser.

### Testing approach

- **Backend (Python):** `pytest` (already a dependency of this repo's test environment, used by
  `gtd-setup`'s own tests) covering: the task-line/frontmatter parser against fixture files, each
  API endpoint's success and conflict paths (using `tempfile` vault fixtures, not the real vault),
  and the exact-line-match write-back logic specifically for its concurrent-edit failure mode
  (line missing, line duplicated).
- **Frontend (JS):** Node's built-in `node:test` + `assert` (zero install — confirmed present:
  this machine runs Node 22) covering the pure functions described above: filtering, grouping,
  overdue calculation, HTML escaping/XSS-safety of rendered task text, and the full `render(state)`
  function's output shape given fixture JSON states (empty state, populated state, overdue state).
- Explicitly out of scope (see Non-goals): real browser/DOM/E2E testing. The plan will call out manual
  browser verification as a final step per relevant task, the same pattern used for the Obsidian
  QuickAdd work (no agent in this session has a GUI to click through with).

## Open risks

- **Concurrent edits are handled defensively but not perfectly.** If the user edits the *exact*
  same line in Obsidian in the ~4-second gap between the dashboard's polls, the dashboard's write
  will correctly refuse (line text won't match) rather than corrupt anything, but the user will see
  a failed action they have to retry after the next poll. Accepted trade-off per the user's chosen
  polling model.
- **No authentication.** Acceptable because the server binds to `127.0.0.1` only — nothing on the
  local network (let alone the internet) can reach it. Worth restating plainly to the user at
  handover, not just in this doc.
