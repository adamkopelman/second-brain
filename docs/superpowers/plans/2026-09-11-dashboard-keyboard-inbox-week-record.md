# Dashboard: Hebrew-safe keys, Inbox + Week pages, Outlook meetings, Record a meeting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Act on the user's nine notes about the local dashboard (`scripts/dashboard_static/` +
`scripts/dashboard_server.py`): keyboard shortcuts that work under a Hebrew layout, left/right
movement, correct scrolling, a visible/clearable search filter, an Inbox page, a Week page, today's
Outlook meetings on the Today page, and a "Record a meeting" button + shortcut — while dropping the
Meetings page.

**Architecture:** Pure rendering/keyboard logic stays in `logic.js` (unit-tested under `node --test`);
DOM wiring stays in `app.js` (verified in a real browser); microphone capture gets its own
`recorder.js`. The Python server gains a stdlib-only Outlook calendar client
(`scripts/outlook_calendar.py`) that talks to the vendored `outlook-mcp-rs` MCP server over stdio
JSON-RPC from a background thread, and a raw-PCM upload endpoint that writes the same WAV + meeting
note the Obsidian `record-meeting` plugin writes, then kicks off transcription in the background.

**Tech Stack:** Vanilla ES5-style JS (no build, no npm deps), Python 3 stdlib (`http.server`,
`subprocess`, `wave`, `threading`), `node --test`, `pytest`.

**Spec:** The user's notes of 2026-09-11 (listed verbatim under *Requirements*) plus the
*Design decisions* below. The previous redesign is commit `b0b5fd6`.

## Global Constraints

- Python: stdlib only (no pip installs). JS: no dependencies, no build step, ES5 style (`var`, `function`) like the existing files.
- The server stays bound to `127.0.0.1`; every POST keeps the existing Origin/Host checks.
- Outlook access is read-only: only the `list_events` tool is ever called.
- Every new shortcut is matched on the physical key (`KeyboardEvent.code`) so it works under a Hebrew layout.
- User-visible text that can be Hebrew (task text, inbox text, event subjects, search box, inputs) gets `dir="auto"`.
- Static files are served from the explicit `STATIC_FILES` map in `dashboard_server.py` — a new static file must be added there.
- Test commands: `node --test scripts/dashboard_static/logic.test.js scripts/dashboard_static/recorder.test.js` and `python -m pytest scripts/tests -q`. Baseline before Task 1: 36 JS tests, 69 Python tests, all passing.

## Requirements (the user's notes, verbatim)

1. "jk shortcut does not work if im in hebrew (which i would be a lot of time since most of my tasks will be in hebrew)"
2. "in tasks, i would also need to navigate left and right."
3. "not sure whats the point of a meeting page: the only thing i need in the meeting is to have an option to record a new one and save it in my second brain"
4. "when i go down and then all the way up, the website doest show the top of the list (even tho im there)"
5. "search and then pressing esc keep the search filter but it does not show it."
6. "the inbox items to process need to be a different tab"
7. "in today page i would like to have the page also show the meetings i have for today (using the outlook-mcp)"
8. "week tab would also be very good"
9. "add a "record a meeting" button and shortcut as well."

## Design decisions

- **Keys by physical position.** `keyAction(event)` maps `e.code` (`KeyJ`, `Slash`, `Digit3`, …) to
  an action name; arrows/Enter by `e.key`. Under Hebrew, `j` types `ח` but `e.code` is still `KeyJ`.
- **Left/right = spatial.** `h`/`l`/`←`/`→` jump to the nearest row in the neighbouring column, by
  on-screen position (works for the Tasks grid, the Week grid, and wrapping layouts).
- **Scrolling.** Rows get `scroll-margin-top` = sticky-header height + room for a section title; the
  first row scrolls the page to the very top.
- **Search.** `Esc` in the search box clears the filter; `Enter` keeps it and jumps into the
  results; while a filter is active a banner says so ("Showing matches for …  Esc clears") and `Esc`
  on the page clears it.
- **Pages (final):** `1 Today · 2 Week · 3 Tasks · 4 Inbox · 5 Waiting · 6 Projects`. Meetings page
  removed. Meeting follow-ups stay on Today's *Needs attention*: "N meetings to transcribe" (Enter
  runs transcription), "N to summarize — run /gtd-summarize-meetings", "N failed to transcribe".
- **Inbox page** lists `00 Inbox/*.md` items (first line of text, capture date); `Enter` opens one in
  Obsidian. Clarifying stays with `/gtd-process-inbox`.
- **Outlook.** The server spawns the vendored `outlook-mcp-rs.exe` (or `$OUTLOOK_MCP_BIN`), does the
  MCP handshake, calls `list_events` for today..today+7, and caches the result, refreshing every
  5 minutes on a background thread so `/api/state` never waits on Outlook. Declined meetings are
  dropped. If Outlook is unavailable the Today page says so in one muted line. `--no-outlook` turns it off.
- **Week page:** a column per day (today + 6), each with that day's meetings and tasks due; an
  "Overdue" column first when anything is overdue.
- **Record a meeting:** header button `● Record` and `r` toggle recording (16 kHz mono via Web Audio,
  like the Obsidian plugin). The recording is named after the Outlook meeting happening now (or
  starting within 10 min), with its attendees; `Enter` on a meeting row records *that* meeting. On
  stop, the browser uploads raw 16-bit PCM; the server writes `Meetings/recordings/<stamp>.wav` and
  `Meetings/<stamp> <title>.md` (`transcription_status: pending`) and starts transcription in the
  background. If the upload fails the audio is kept in memory and the button offers a retry.

---

## File structure

| File | Responsibility | Tasks |
|---|---|---|
| `scripts/dashboard_static/logic.js` | pure render + key/nav logic | 1, 3, 4, 6, 8, 9, 11 |
| `scripts/dashboard_static/logic.test.js` | unit tests for logic.js | 1, 3, 4, 6, 8, 9, 11 |
| `scripts/dashboard_static/app.js` | DOM wiring, keyboard, polling, recording UI | 1, 2, 3, 4, 6, 8, 9, 11 |
| `scripts/dashboard_static/index.html` | page shell | 1, 3, 6, 9, 11 |
| `scripts/dashboard_static/style.css` | styles | 2, 3, 6, 8, 9, 11 |
| `scripts/dashboard_static/recorder.js` (new) | mic capture → Int16 PCM | 11 |
| `scripts/dashboard_static/recorder.test.js` (new) | tests for recorder.js pure part | 11 |
| `scripts/dashboard_parser.py` | adds `inbox_items` | 5 |
| `scripts/outlook_calendar.py` (new) | MCP stdio client + cache | 7 |
| `scripts/dashboard_writer.py` | `save_meeting_recording`, transcription lock/background | 10 |
| `scripts/dashboard_server.py` | calendar in state, record endpoint, `/recorder.js` | 7, 10, 11 |
| `scripts/tests/fake_outlook_mcp.py` (new) | fake MCP server for tests | 7 |
| `scripts/tests/test_outlook_calendar.py` (new) | calendar client tests | 7 |
| `scripts/tests/test_dashboard_*.py` | parser/writer/server tests | 5, 7, 10, 11 |
| `docs/gtd/local-dashboard.md`, `docs/gtd/meeting-recording.md` | docs | 12 |

---

### Task 1: Shortcuts by physical key (Hebrew layout) + RTL-friendly text

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (add `keyAction`; `dir="auto"` in `taskLine` and `taskDetailHtml`)
- Modify: `scripts/dashboard_static/app.js` (keydown handler → `keyAction` + `runAction`)
- Modify: `scripts/dashboard_static/index.html` (`dir="auto"` on text inputs)
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Produces: `DashboardLogic.keyAction(ev) -> string|null`, one of `"down" "up" "left" "right" "open" "complete" "delete" "undo" "search" "new" "help" "record" "page:N"` (N = 1–9). `app.js` gets `runAction(action) -> boolean` (true = key consumed); later tasks add `case`s to it.

- [ ] **Step 1: Write the failing tests** (append to `logic.test.js`)

```js
const keyEv = (o) => Object.assign({ key: "", code: "", shiftKey: false, ctrlKey: false, metaKey: false, altKey: false }, o);

test("keyAction maps shortcuts by physical key, so a Hebrew layout works too", () => {
  assert.equal(L.keyAction(keyEv({ key: "j", code: "KeyJ" })), "down");
  assert.equal(L.keyAction(keyEv({ key: "ח", code: "KeyJ" })), "down");
  assert.equal(L.keyAction(keyEv({ key: "ל", code: "KeyK" })), "up");
  assert.equal(L.keyAction(keyEv({ key: "י", code: "KeyH" })), "left");
  assert.equal(L.keyAction(keyEv({ key: "ך", code: "KeyL" })), "right");
  assert.equal(L.keyAction(keyEv({ key: "ס", code: "KeyX" })), "complete");
  assert.equal(L.keyAction(keyEv({ key: "ג", code: "KeyD" })), "delete");
  assert.equal(L.keyAction(keyEv({ key: "ו", code: "KeyU" })), "undo");
  assert.equal(L.keyAction(keyEv({ key: "מ", code: "KeyN" })), "new");
  assert.equal(L.keyAction(keyEv({ key: "ר", code: "KeyR" })), "record");
  assert.equal(L.keyAction(keyEv({ key: ".", code: "Slash" })), "search"); // the "/" key under Hebrew
  assert.equal(L.keyAction(keyEv({ key: "?", code: "Slash", shiftKey: true })), "help");
  assert.equal(L.keyAction(keyEv({ key: "3", code: "Digit3" })), "page:3");
  assert.equal(L.keyAction(keyEv({ key: "3", code: "Numpad3" })), "page:3");
  assert.equal(L.keyAction(keyEv({ key: "ArrowDown", code: "ArrowDown" })), "down");
  assert.equal(L.keyAction(keyEv({ key: "ArrowRight", code: "ArrowRight" })), "right");
  assert.equal(L.keyAction(keyEv({ key: "Enter", code: "Enter" })), "open");
});

test("keyAction ignores modified and unmapped keys", () => {
  assert.equal(L.keyAction(keyEv({ key: "j", code: "KeyJ", ctrlKey: true })), null);
  assert.equal(L.keyAction(keyEv({ key: "J", code: "KeyJ", shiftKey: true })), null);
  assert.equal(L.keyAction(keyEv({ key: "q", code: "KeyQ" })), null);
});

test("task text is marked dir=auto so Hebrew renders right-to-left", () => {
  const html = L.render({ inbox_count: 0, waiting: [], due_soon: [], active_projects: [], someday_projects: [],
    tasks_by_context: { "#phone": [{ text: "להתקשר לאינסטלטור", file: "f.md", line_text: "x" }] } }, "", "2026-09-11").tasksHtml;
  assert.match(html, /<span class="task-text" dir="auto">להתקשר לאינסטלטור/);
  const detail = L.taskDetailHtml({ text: "שלום", file: "f.md", line_text: "x", context: "#phone" }, "2026-09-11");
  assert.match(detail, /id="detail-text" value="שלום" dir="auto"/);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: FAIL — `L.keyAction is not a function`, and the `dir="auto"` regexes don't match.

- [ ] **Step 3: Implement `keyAction`** (in `logic.js`, after `shortcutsHtml`)

```js
  // Shortcuts are matched on the physical key (e.code), not the typed character, so they keep
  // working when the keyboard is switched to Hebrew (where "j" types "ח").
  var CODE_ACTIONS = {
    KeyJ: "down", KeyK: "up", KeyH: "left", KeyL: "right",
    KeyX: "complete", KeyD: "delete", KeyU: "undo", KeyN: "new", KeyR: "record",
  };
  var KEY_ACTIONS = { ArrowDown: "down", ArrowUp: "up", ArrowLeft: "left", ArrowRight: "right", Enter: "open" };

  function keyAction(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return null;
    var code = ev.code || "";
    if (code === "Slash") return ev.shiftKey ? "help" : "search";
    if (ev.key === "?") return "help";
    var digit = /^(?:Digit|Numpad)([1-9])$/.exec(code);
    if (digit && !ev.shiftKey) return "page:" + digit[1];
    if (KEY_ACTIONS[ev.key]) return KEY_ACTIONS[ev.key];
    if (!ev.shiftKey && CODE_ACTIONS[code]) return CODE_ACTIONS[code];
    return null;
  }
```

Add `keyAction: keyAction,` to the `api` object.

In `taskLine`, change both `'<span class="task-text">'` occurrences to `'<span class="task-text" dir="auto">'`.
In `taskDetailHtml`, change
`'<input type="text" id="detail-text" value="' + escapeHtml(t.text) + '"></div>'` to
`'<input type="text" id="detail-text" value="' + escapeHtml(t.text) + '" dir="auto"></div>'`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test scripts/dashboard_static/logic.test.js`
Expected: PASS (39 tests).

- [ ] **Step 5: Route app.js keys through `keyAction`**

Replace the `// ---- keyboard ----` keydown listener in `app.js` with:

```js
  // ---- keyboard ----

  var searchEl = document.getElementById("search");

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeQuickAdd();
      closeDetailModal();
      if (document.activeElement === searchEl) searchEl.blur();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target.tagName || "").toLowerCase();

    // Enter in the search box drops you onto the first result, ready for j/k
    if (e.target === searchEl) {
      if (e.key === "Enter" || e.key === "ArrowDown") {
        e.preventDefault();
        searchEl.blur();
        select(0, true);
      }
      return;
    }
    // Enter in a task's detail fields saves it
    if (e.key === "Enter" && tag === "input" && detailBody.contains(e.target)) {
      var save = detailBody.querySelector(".detail-save");
      if (save) { e.preventDefault(); save.click(); }
      return;
    }
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    if (anyModalOpen()) return;
    // a focused button/link handles its own Enter/Space
    if ((e.key === "Enter" || e.key === " ") && (tag === "button" || tag === "a")) return;

    var action = DashboardLogic.keyAction(e);
    if (action && runAction(action)) e.preventDefault();
  });

  // Returns true when the key was used, so the browser's default (scrolling, typing) is skipped.
  function runAction(action) {
    var el = selectedEl();
    var isTask = el && el.classList.contains("task");
    if (action.indexOf("page:") === 0) {
      var n = parseInt(action.slice(5), 10);
      if (n > PAGES.length) return false;
      goTo(PAGES[n - 1]);
      return true;
    }
    switch (action) {
      case "down": return move(1);
      case "up": return move(-1);
      case "open":
        if (!el) return false;
        activate(el);
        return true;
      case "complete":
        if (isTask) completeTask(el.getAttribute("data-file"), el.getAttribute("data-line"));
        return true;
      case "delete":
        if (isTask) scheduleDelete(el.getAttribute("data-file"), el.getAttribute("data-line"));
        return true;
      case "undo": undoLastDelete(); return true;
      case "search": searchEl.focus(); return true;
      case "new": openQuickAdd(); return true;
      case "help": openHelp(); return true;
    }
    return false;
  }
```

Also change `document.getElementById("search").addEventListener("input", …)` to `searchEl.addEventListener("input", …)` (move the listener below the `searchEl` declaration if needed).

In `index.html` add `dir="auto"` to `#search`, `#quick-add-text` and `#quick-add-project`.

- [ ] **Step 6: Verify in the browser**

Start `python scripts/dashboard_server.py <scratch vault> --port 8792`, hard-reload. Switch the OS keyboard to Hebrew (or dispatch `new KeyboardEvent("keydown", {key: "ח", code: "KeyJ", bubbles: true})` from the console). Expected: `j`/`k`/digits/`/`/`n` behave exactly as under English.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/logic.js scripts/dashboard_static/logic.test.js scripts/dashboard_static/app.js scripts/dashboard_static/index.html
git commit -m "fix(dashboard): match shortcuts on the physical key so they work under Hebrew; dir=auto text"
```

---

### Task 2: Scrolling keeps the selected row (and the top of the list) visible

**Files:**
- Modify: `scripts/dashboard_static/app.js` (`select`, new `syncTopbarHeight`)
- Modify: `scripts/dashboard_static/style.css`

**Interfaces:**
- Produces: CSS custom property `--topbar-h` on `:root`, kept equal to the sticky header's height.

- [ ] **Step 1: Reproduce** — scratch vault with 40+ tasks on the Tasks page; press `j` ×20 then `k` ×20. Expected today (bug): the first row ends up under the sticky header; its section title is hidden.

- [ ] **Step 2: Implement**

In `app.js` `select()`, replace `if (scroll) el.scrollIntoView({ block: "nearest" });` with:

```js
    if (scroll) {
      // the first row means "top of the page": show the section titles above it too
      if (i === 0) window.scrollTo(0, 0);
      else el.scrollIntoView({ block: "nearest" });
    }
```

Add after `applyTheme`:

```js
  // Rows scroll clear of the sticky header (see .nav-item scroll-margin in style.css).
  function syncTopbarHeight() {
    document.documentElement.style.setProperty("--topbar-h", document.querySelector(".topbar").offsetHeight + "px");
  }
```

and at the bottom, before `applyTheme(...)`: `syncTopbarHeight(); window.addEventListener("resize", syncTopbarHeight);`

In `style.css`, after `.nav-item.selected { … }`:

```css
/* keep a selected row (and the section title above it) out from under the sticky header */
.nav-item { scroll-margin-top: calc(var(--topbar-h, 56px) + 40px); scroll-margin-bottom: 24px; }
```

- [ ] **Step 3: Verify** — repeat Step 1. Expected: each row stays fully visible below the header while moving; reaching the first row shows the page top, including its section title.

- [ ] **Step 4: Commit**

```bash
git add scripts/dashboard_static/app.js scripts/dashboard_static/style.css
git commit -m "fix(dashboard): scroll rows clear of the sticky header; first row shows the page top"
```

---

### Task 3: Search filter is always visible and Esc clears it

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (add `filterBannerHtml`)
- Modify: `scripts/dashboard_static/app.js` (`setQuery`, Escape handling, banner)
- Modify: `scripts/dashboard_static/index.html` (`type="text"`, banner element)
- Modify: `scripts/dashboard_static/style.css`
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Produces: `DashboardLogic.filterBannerHtml(query) -> string` ("" when no query). `app.js` gets `setQuery(q)`.

- [ ] **Step 1: Write the failing test**

```js
test("filterBannerHtml explains an active filter and how to clear it, escaping the query", () => {
  assert.equal(L.filterBannerHtml(""), "");
  const html = L.filterBannerHtml("<b>דוח</b>");
  assert.match(html, /Showing matches for/);
  assert.match(html, /&lt;b&gt;דוח&lt;\/b&gt;/);
  assert.match(html, /class="filter-clear"/);
  assert.match(html, /<kbd>Esc<\/kbd>/);
});
```

- [ ] **Step 2: Run to verify it fails** — `node --test scripts/dashboard_static/logic.test.js` → FAIL (`filterBannerHtml is not a function`).

- [ ] **Step 3: Implement** (in `logic.js`, and export `filterBannerHtml`)

```js
  function filterBannerHtml(query) {
    if (!query) return "";
    return 'Showing matches for “<b dir="auto">' + escapeHtml(query) + '</b>” · ' +
      '<button type="button" class="filter-clear">Clear</button> or press <kbd>Esc</kbd>';
  }
```

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Wire it up**

`index.html`: change the search input to `type="text"` (a `type="search"` box clears itself on Esc without telling the page — the root cause of the bug) and add, as the first child of `<main>`:
`<div id="filter-banner" class="filter-banner" hidden></div>`

`app.js`:

```js
  function setQuery(q) {
    query = q;
    searchEl.value = q;
    renderAll();
  }
```

In `renderAll()` add:

```js
    var banner = document.getElementById("filter-banner");
    banner.innerHTML = DashboardLogic.filterBannerHtml(query);
    banner.hidden = !query;
```

Replace the Escape branch at the top of the keydown listener with:

```js
    if (e.key === "Escape") {
      if (anyModalOpen()) { closeQuickAdd(); closeDetailModal(); return; }
      // Esc in the box, or anywhere while a filter is active, clears the search
      if (e.target === searchEl) searchEl.blur();
      if (query) setQuery("");
      return;
    }
```

The search `input` listener becomes `searchEl.addEventListener("input", function () { query = searchEl.value; renderAll(); });`.
In the document click handler, first thing: `if (e.target.closest(".filter-clear")) { setQuery(""); return; }`.

`style.css`:

```css
.filter-banner {
  margin: 0 0 14px; padding: 6px 10px; border-radius: 8px; font-size: 0.85rem;
  background: var(--sel); color: var(--text);
}
.filter-clear { border: none; background: none; color: var(--accent); cursor: pointer; padding: 0; font: inherit; }
```

- [ ] **Step 6: Verify** — `/`, type `hotel`, `Esc` → box empty, full lists back, no banner. `/`, `hotel`, `Enter` → banner "Showing matches for “hotel”", first result selected; `Esc` → filter cleared.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/
git commit -m "fix(dashboard): Esc clears the search; a banner shows whenever a filter is active"
```

---

### Task 4: Left/right movement between columns

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (add `pickHorizontal`, shortcut rows)
- Modify: `scripts/dashboard_static/app.js` (`moveHorizontal`, `runAction` cases)
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Consumes: `keyAction` → `"left"` / `"right"` (Task 1).
- Produces: `DashboardLogic.pickHorizontal(rects, from, dir) -> number` — `rects` are `{left, right, top, bottom}`, `dir` is `-1`/`+1`; returns the target index or `-1`.

- [ ] **Step 1: Write the failing test**

```js
test("pickHorizontal moves to the level row in the nearest column, or stays put at the edge", () => {
  const r = (left, top) => ({ left, right: left + 100, top, bottom: top + 20 });
  // three columns (x = 0, 120, 240); column 2 has rows at y = 0 and 40, column 3 only at y = 0;
  // a second grid row of columns starts at y = 200
  const rects = [r(0, 0), r(0, 40), r(0, 80), r(120, 0), r(120, 40), r(240, 0), r(0, 200), r(120, 200)];
  assert.equal(L.pickHorizontal(rects, 1, 1), 4);   // col 1 row 2 → col 2 row 2
  assert.equal(L.pickHorizontal(rects, 2, 1), 4);   // col 1 row 3 → col 2's nearest row
  assert.equal(L.pickHorizontal(rects, 4, 1), 5);   // → col 3 (only row)
  assert.equal(L.pickHorizontal(rects, 5, 1), -1);  // right edge
  assert.equal(L.pickHorizontal(rects, 3, -1), 0);  // back left
  assert.equal(L.pickHorizontal(rects, 6, 1), 7);   // second grid row stays in its row
  assert.equal(L.pickHorizontal(rects, 0, -1), -1); // left edge
});
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`pickHorizontal is not a function`).

- [ ] **Step 3: Implement** (export `pickHorizontal`)

```js
  // For ←/→: the nearest column over (by left edge), then the row in it closest in height to the
  // current one. Works for any grid of rows, including ones that wrap onto a second line.
  function pickHorizontal(rects, from, dir) {
    var cur = rects[from];
    var cy = (cur.top + cur.bottom) / 2;
    var colLeft = null;
    rects.forEach(function (r) {
      var ahead = dir > 0 ? r.left > cur.left + 10 : r.left < cur.left - 10;
      if (ahead && (colLeft === null || Math.abs(r.left - cur.left) < Math.abs(colLeft - cur.left))) colLeft = r.left;
    });
    if (colLeft === null) return -1;
    var best = -1, bestDy = Infinity;
    rects.forEach(function (r, i) {
      if (Math.abs(r.left - colLeft) > 10) return;
      var dy = Math.abs((r.top + r.bottom) / 2 - cy);
      if (dy < bestDy) { bestDy = dy; best = i; }
    });
    return best;
  }
```

Add to `SHORTCUTS` after the `k / ↑` row: `["h / ←", "Column to the left"], ["l / →", "Column to the right"],`.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Wire it up** (`app.js`, next to `move`)

```js
  function moveHorizontal(dir) {
    var items = navItems();
    if (!items.length) return false;
    if (sel.index < 0) { select(0, true); return true; }
    var rects = items.map(function (el) { return el.getBoundingClientRect(); });
    var i = DashboardLogic.pickHorizontal(rects, sel.index, dir);
    if (i >= 0) select(i, true);
    return true;
  }
```

In `runAction` add `case "left": return moveHorizontal(-1);` and `case "right": return moveHorizontal(1);`.

- [ ] **Step 6: Verify** — Tasks page with 3+ context columns: `j` into column 1, `l` → same height in column 2, `h` back. From the triage list, `l` goes to column 2.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/
git commit -m "feat(dashboard): h/l and left/right arrows move between columns"
```

---

### Task 5: Parser lists inbox items

**Files:**
- Modify: `scripts/dashboard_parser.py` (`_inbox_items`, `collect_state` key `inbox_items`)
- Test: `scripts/tests/test_dashboard_parser.py`

**Interfaces:**
- Produces: `state["inbox_items"]`: `list[{"file": str, "name": str, "text": str, "captured": str | None}]`, sorted by `(captured or "", file)`. `inbox_count` stays and equals its length.

- [ ] **Step 1: Write the failing test**

```python
def test_collect_state_lists_inbox_items_with_text_and_capture_date(tmp_path):
    _mk_vault(tmp_path)
    ib = tmp_path / "00 Inbox"
    (ib / "2026-09-10 call-plumber.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-10\n---\n- [ ] Call plumber about the leaky faucet\n", encoding="utf-8")
    (ib / "2026-09-11 idea.md").write_text(
        "---\ntype: inbox\n---\n\nCheck out [[Atomic Habits]] — recommended by Sam\nsecond line\n", encoding="utf-8")
    (ib / "2026-09-11 hebrew.md").write_text(
        "---\ntype: inbox\ncaptured: 2026-09-11\n---\n- [ ] להתקשר לאינסטלטור #next #phone\n", encoding="utf-8")
    (ib / "2026-09-12 empty.md").write_text("---\ntype: inbox\ncaptured: 2026-09-12\n---\n", encoding="utf-8")
    state = P.collect_state(tmp_path)
    items = state["inbox_items"]
    by_file = {i["file"]: i for i in items}
    assert by_file["00 Inbox/2026-09-10 call-plumber.md"]["text"] == "Call plumber about the leaky faucet"
    assert by_file["00 Inbox/2026-09-11 idea.md"]["text"] == "Check out Atomic Habits — recommended by Sam"
    assert by_file["00 Inbox/2026-09-11 idea.md"]["captured"] == "2026-09-11"  # from the file name
    assert by_file["00 Inbox/2026-09-11 hebrew.md"]["text"] == "להתקשר לאינסטלטור"
    assert by_file["00 Inbox/2026-09-12 empty.md"]["text"] == "2026-09-12 empty"  # falls back to the name
    assert [i["file"] for i in items][0] == "00 Inbox/loose.md"  # captured 2026-09-09 sorts first
    assert "00 Inbox/README.md" not in by_file
    assert state["inbox_count"] == len(items) == 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest scripts/tests/test_dashboard_parser.py -q -k inbox_items`
Expected: FAIL with `KeyError: 'inbox_items'`.

- [ ] **Step 3: Implement** (`dashboard_parser.py`, above `collect_state`)

```python
_DATE_PREFIX_RE = _re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _inbox_item(vault: Path, p: Path) -> dict:
    """One inbox capture: its first line of text (task checkbox, tags and fields stripped), and when
    it was captured (frontmatter `captured`, else the file name's date prefix)."""
    text = p.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:]
    first = next((l.strip() for l in body.splitlines() if l.strip()), "")
    m = BD.TASK_RE.match(first)
    if m:
        first = m.group("b")
    first = BD._clean(_re.sub(r"^#+\s+", "", first))
    date = _DATE_PREFIX_RE.match(p.stem)
    return {
        "file": str(p.relative_to(vault)).replace("\\", "/"),
        "name": p.stem,
        "text": first or p.stem,
        "captured": fm.get("captured") or (date.group(1) if date else None),
    }
```

In `collect_state`, replace the inbox block with:

```python
    inbox_items: list[dict] = []
    ib = vault / "00 Inbox"
    if ib.is_dir():
        inbox_items = [_inbox_item(vault, p) for p in ib.glob("*.md") if p.name != "README.md"]
        inbox_items.sort(key=lambda i: (i["captured"] or "", i["file"]))
    inbox_count = len(inbox_items)
```

and add `"inbox_items": inbox_items,` to the returned dict (after `"inbox_count"`).

- [ ] **Step 4: Run tests** — `python -m pytest scripts/tests -q` → all pass (70).

- [ ] **Step 5: Commit**

```bash
git add scripts/dashboard_parser.py scripts/tests/test_dashboard_parser.py
git commit -m "feat(dashboard): parser lists inbox items with their text and capture date"
```

---

### Task 6: Inbox page replaces the Meetings page

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (`PAGES`, `renderInbox`, `filterInbox`, `attentionItems`, `renderAttention`, `tabInfo`, `render`; delete `renderMeetings`)
- Modify: `scripts/dashboard_static/app.js`, `index.html`, `style.css`
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Consumes: `state.inbox_items` (Task 5).
- Produces: `PAGES = ["today", "tasks", "inbox", "waiting", "projects"]`; `render(...)` returns `{tabs, todayHtml, tasksHtml, inboxHtml, waitingHtml, projectsHtml}` (no `meetingsHtml`). Attention items may carry `action: "transcribe"`, rendered as `<a href="#" class="att-run" data-action="transcribe">`.

- [ ] **Step 1: Update and add tests**

Delete the three `renderMeetings …` tests. Then:

- In "render produces per-tab counts for a populated state": expected counts become `{ today: 1, tasks: 2, inbox: 0, waiting: 1, projects: 1 }`.
- Rename "render omits the Needs-triage section when nothing needs triage, and renders meetings" → "render omits the Needs-triage section when nothing needs triage"; drop its `meetings` field and the `meetingsHtml` assertion.
- In "tabInfo flags overdue work, …": delete `assert.equal(info.meetings.alert, true);` and rename to "tabInfo flags overdue work, triage and overdue reviews".
- In "renderTabs numbers the pages…": replace `meetings: { count: 0, alert: false }` with `inbox: { count: 0, alert: false }`.
- In "every navigable row carries a stable data-key": replace `meetings: [...]` with `inbox_items: [{ file: "00 Inbox/a.md", text: "Idea", captured: "2026-09-11" }]` and the meetings assertion with `assert.match(out.inboxHtml, /class="nav-item" data-key="inbox\|00 Inbox\/a\.md"/);`.
- In "search filters projects and meetings by name": rename to "search filters projects and inbox items"; replace `meetings: [...]` with `inbox_items: [{ file: "00 Inbox/a.md", text: "Buy trip insurance" }, { file: "00 Inbox/b.md", text: "Idea" }]`, and replace the meetings assertion with `assert.match(out.inboxHtml, /Buy trip insurance/); assert.doesNotMatch(out.inboxHtml, /Idea/); assert.equal(out.tabs.inbox.count, 1);`.
- In "attentionItems covers …": replace `assert.equal(byKey.inbox.text, "2 inbox items to process");` with
  `assert.equal(byKey.inbox.text, "2 inbox items to process"); assert.equal(byKey.inbox.page, "inbox");` and add
  `assert.equal(byKey["mtg-transcribe"].action, "transcribe"); assert.match(byKey["mtg-summarize"].hint, /gtd-summarize-meetings/);`.

New tests:

```js
test("renderInbox lists captures with Obsidian links and says so when empty", () => {
  const items = [{ file: "00 Inbox/2026-09-10 call-plumber.md", text: "להתקשר לאינסטלטור", captured: "2026-09-10" }];
  const html = L.render({ inbox_count: 1, inbox_items: items, tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [], vault_name: "second-brain" }, "", "2026-09-11").inboxHtml;
  assert.match(html, /href="obsidian:\/\/open\?vault=second-brain&amp;file=00%20Inbox%2F2026-09-10%20call-plumber\.md" dir="auto">להתקשר לאינסטלטור/);
  assert.match(html, /2026-09-10/);
  assert.match(html, /gtd-process-inbox/);
  const empty = L.render({ inbox_count: 0, inbox_items: [], tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [] }, "", "2026-09-11").inboxHtml;
  assert.match(empty, /Inbox zero/);
});

test("a pending-transcription attention item is an action link", () => {
  const html = L.render({ inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [], active_projects: [],
    someday_projects: [], meetings: [{ name: "A", transcription_status: "pending" }] }, "", "2026-09-11").todayHtml;
  assert.match(html, /<a href="#" class="att-run" data-action="transcribe">1 meeting to transcribe<\/a>/);
});
```

- [ ] **Step 2: Run to verify failures** — `node --test scripts/dashboard_static/logic.test.js` → the new/edited tests FAIL (no `inboxHtml`, no `action`).

- [ ] **Step 3: Implement in `logic.js`**

```js
  var PAGES = ["today", "tasks", "inbox", "waiting", "projects"];
  var PAGE_LABELS = { today: "Today", week: "Week", tasks: "Tasks", inbox: "Inbox", waiting: "Waiting", projects: "Projects" };
```

In `attentionItems`: the inbox item becomes
`items.push({ key: "inbox", alert: true, page: "inbox", text: plural(inbox, "inbox item") + " to process" });`
and the three meeting items become:

```js
    if (counts.failed) items.push({ key: "mtg-failed", alert: true, text: plural(counts.failed, "meeting") + " failed to transcribe",
      hint: "see the note in Obsidian" });
    if (counts.transcribe) items.push({ key: "mtg-transcribe", alert: true, action: "transcribe",
      text: plural(counts.transcribe, "meeting") + " to transcribe" });
    if (counts.summarize) items.push({ key: "mtg-summarize", alert: true, text: plural(counts.summarize, "meeting") + " to summarize",
      hint: "run /gtd-summarize-meetings" });
```

`renderAttention` (full replacement):

```js
  function renderAttention(items) {
    return '<ul class="att-list">' + items.map(function (a) {
      var text = escapeHtml(a.text);
      var body = a.project
        ? '<a href="#" class="proj-open" data-name="' + escapeHtml(a.project) + '">' + text + "</a>"
        : a.page ? '<a href="#' + a.page + '">' + text + "</a>"
        : a.action ? '<a href="#" class="att-run" data-action="' + escapeHtml(a.action) + '">' + text + "</a>"
        : "<span>" + text + "</span>";
      var hint = a.hint ? ' <span class="att-hint">' + escapeHtml(a.hint) + "</span>" : "";
      var nav = a.project || a.page || a.action;
      return '<li class="att' + (a.alert ? " att-alert" : "") + (nav ? ' nav-item" data-key="' + escapeHtml("att|" + a.key) + '"' : '"') +
        ">" + body + hint + "</li>";
    }).join("") + "</ul>";
  }
```

New (next to `filterByName`):

```js
  function filterInbox(items, query) {
    if (!query) return items;
    var q = query.toLowerCase();
    return items.filter(function (it) { return (it.text || "").toLowerCase().indexOf(q) !== -1; });
  }

  function renderInbox(items, query, vaultName) {
    if (!items.length) return '<p class="empty">Inbox zero — nothing to process.</p>';
    var shown = filterInbox(items, query);
    if (!shown.length) return '<p class="empty">No inbox items match your search.</p>';
    return '<p class="page-note">Clarify these with <code>/gtd-process-inbox</code> in Claude Code · ' +
      "<kbd>Enter</kbd> opens one in Obsidian</p>" +
      '<ul class="inbox-list">' + shown.map(function (it) {
        return '<li class="nav-item" data-key="' + escapeHtml("inbox|" + it.file) + '">' +
          '<a href="' + escapeHtml(obsidianUrl(vaultName, it.file)) + '" dir="auto">' + escapeHtml(it.text) + "</a>" +
          (it.captured ? '<span class="due">' + escapeHtml(it.captured) + "</span>" : "") + "</li>";
      }).join("") + "</ul>";
  }
```

In `tabInfo`, replace the `meetings: {…}` entry with `inbox: { count: filterInbox(state.inbox_items || [], query).length, alert: false },`.

`render` becomes:

```js
  function render(state, query, today, pending) {
    return {
      tabs: tabInfo(state, query, today),
      todayHtml: renderToday(state, query, today, pending),
      tasksHtml: renderTasksPage(state, query, today, pending),
      inboxHtml: renderInbox(state.inbox_items || [], query, state.vault_name),
      waitingHtml: renderSimpleList(state.waiting || [], today, query, pending, "Not waiting on anything."),
      projectsHtml: renderProjectsPage(state, query),
    };
  }
```

Delete `renderMeetings` and remove it from `api`.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Wire up the page**

`index.html`: replace the whole `<section class="page" id="page-meetings" …>…</section>` with
`<section class="page" id="page-inbox" hidden><div id="inbox"></div></section>`, placed between `page-tasks` and `page-waiting`.

`app.js`:
- In `renderAll`, replace the `meetings` line with `document.getElementById("inbox").innerHTML = out.inboxHtml;`.
- Delete the `transcribe-btn` click listener.
- Add near the top: `var transcribing = false;`, and at the end of `renderAll`:

```js
    if (transcribing) {
      var run = document.querySelector('.att-run[data-action="transcribe"]');
      if (run) run.textContent = "Transcribing…";
    }
```

- In the document click handler, before the `.proj-open` check:

```js
    var runLink = e.target.closest(".att-run");
    if (runLink) {
      e.preventDefault();
      if (runLink.getAttribute("data-action") === "transcribe" && !transcribing) {
        transcribing = true;
        renderAll();
        post("/api/transcribe", {}).catch(function () {}).then(function () { transcribing = false; refresh(); });
      }
      return;
    }
```

`style.css`: extend the row selector `.task-list li, #projects li, #meetings li, .att-list li` to
`.task-list li, #projects li, .inbox-list li, .att-list li`; delete the `#transcribe-btn` rules; add
`.page-note { color: var(--muted); font-size: 0.85rem; margin: 0 0 10px; }` and
`.inbox-list a { flex: 1 1 12em; color: var(--text); }`.

- [ ] **Step 6: Verify** — `4` opens Inbox, `j` + `Enter` opens the note in Obsidian; Today's "2 inbox items to process" + `Enter` lands on Inbox; with a pending recording, Enter on "1 meeting to transcribe" shows "Transcribing…" and the item disappears when done.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/
git commit -m "feat(dashboard): Inbox page; drop the Meetings page, keep meeting follow-ups on Today"
```

---

### Task 7: Outlook calendar client + calendar in `/api/state`

**Files:**
- Create: `scripts/outlook_calendar.py`
- Create: `scripts/tests/fake_outlook_mcp.py`, `scripts/tests/test_outlook_calendar.py`
- Modify: `scripts/dashboard_server.py` (`make_handler(vault, calendar=None, auto_transcribe=False)`, `main`)
- Test: `scripts/tests/test_dashboard_server.py`

**Interfaces:**
- Produces: `OC.resolve_command() -> list[str] | None`; `OC.call_list_events(command, start: date, end: date, timeout=60) -> list[dict]` (raises `OC.OutlookUnavailable`); `OC.normalize(events) -> list[{"subject","start","end","date","all_day","location","attendees"}]` (`start`/`end` = `"YYYY-MM-DDTHH:MM"`, `date` = `"YYYY-MM-DD"`); `OC.CalendarCache(command, ttl=300, days=7, fetch=call_list_events, today=date.today)` with `.snapshot() -> {"status": "ok"|"loading"|"unavailable", "error": str|None, "events": list, "updated": str|None}`, `.refresh()`, `.start()`.
- `/api/state` gains `calendar`: the snapshot, or `{"status": "off", "error": None, "events": [], "updated": None}` when no cache is configured.

- [ ] **Step 1: Write the fake MCP server** (`scripts/tests/fake_outlook_mcp.py`)

```python
"""Stand-in for outlook-mcp-rs in tests: answers `initialize` and `tools/call list_events` over
stdio JSON-RPC. argv[1] picks a mode: ok (default), error (tool error), hang (never answers)."""
import json
import sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "ok"
EVENTS = [
    {"id": "1", "subject": "סנכרון שבועי", "start": "2026-09-11T09:30:00", "end": "2026-09-11T10:00:00",
     "location": "Room 1", "all_day": False, "my_response": "accepted", "required_attendees": "Dana; Omer"},
    {"id": "2", "subject": "Declined thing", "start": "2026-09-11T08:00:00", "end": "2026-09-11T09:00:00",
     "location": "", "all_day": False, "my_response": "declined", "required_attendees": ""},
    {"id": "3", "subject": "Holiday", "start": "2026-09-12T00:00:00", "end": "2026-09-13T00:00:00",
     "location": "", "all_day": True, "my_response": "organizer", "required_attendees": ""},
]

for line in sys.stdin:
    msg = json.loads(line)
    if MODE == "hang" or "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "0"}}
    elif msg["method"] == "tools/call":
        args = msg["params"].get("arguments", {})
        if MODE == "error" or msg["params"]["name"] != "list_events" or "start_date" not in args or "end_date" not in args:
            result = {"content": [{"type": "text", "text": "Outlook is not running"}], "isError": True}
        else:
            result = {"content": [{"type": "text", "text": json.dumps(EVENTS, ensure_ascii=False)}], "isError": False}
    else:
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
```

- [ ] **Step 2: Write the failing tests** (`scripts/tests/test_outlook_calendar.py`)

```python
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import outlook_calendar as OC

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_outlook_mcp.py")]
D1, D2 = dt.date(2026, 9, 11), dt.date(2026, 9, 18)


def test_call_list_events_speaks_mcp_over_stdio():
    events = OC.call_list_events(FAKE, D1, D2)
    assert [e["subject"] for e in events] == ["סנכרון שבועי", "Declined thing", "Holiday"]


def test_call_list_events_raises_unavailable_on_a_tool_error():
    with pytest.raises(OC.OutlookUnavailable, match="not running"):
        OC.call_list_events(FAKE + ["error"], D1, D2)


def test_call_list_events_times_out_on_a_hung_server():
    with pytest.raises(OC.OutlookUnavailable):
        OC.call_list_events(FAKE + ["hang"], D1, D2, timeout=2)


def test_call_list_events_raises_unavailable_when_the_binary_is_missing(tmp_path):
    with pytest.raises(OC.OutlookUnavailable):
        OC.call_list_events([str(tmp_path / "missing.exe")], D1, D2)


def test_normalize_drops_declined_trims_times_and_sorts_all_day_first():
    out = OC.normalize([
        {"subject": "Late", "start": "2026-09-11T15:00:00", "end": "2026-09-11T16:00:00", "all_day": False},
        {"subject": "Declined", "start": "2026-09-11T08:00:00", "end": "2026-09-11T09:00:00", "my_response": "declined"},
        {"subject": "Off", "start": "2026-09-11T00:00:00", "end": "2026-09-12T00:00:00", "all_day": True},
        {"subject": "", "start": "2026-09-11T10:00:00", "end": "2026-09-11T10:30:00", "location": "Zoom",
         "required_attendees": "Dana"},
        {"subject": "No start"},
    ])
    assert [e["subject"] for e in out] == ["Off", "(no subject)", "Late"]
    assert out[1] == {"subject": "(no subject)", "start": "2026-09-11T10:00", "end": "2026-09-11T10:30",
                      "date": "2026-09-11", "all_day": False, "location": "Zoom", "attendees": "Dana"}


def test_calendar_cache_reports_loading_then_ok():
    cache = OC.CalendarCache(["x"], fetch=lambda cmd, s, e: [
        {"subject": "A", "start": "2026-09-11T10:00:00", "end": "2026-09-11T11:00:00"}],
        today=lambda: D1)
    assert cache.snapshot()["status"] == "loading"
    cache.refresh()
    snap = cache.snapshot()
    assert snap["status"] == "ok"
    assert snap["events"][0]["subject"] == "A"
    assert snap["updated"]


def test_calendar_cache_passes_a_week_window_to_the_fetcher():
    seen = []
    cache = OC.CalendarCache(["x"], fetch=lambda cmd, s, e: seen.append((cmd, s, e)) or [], today=lambda: D1)
    cache.refresh()
    assert seen == [(["x"], D1, D1 + dt.timedelta(days=7))]


def test_calendar_cache_without_a_command_is_unavailable():
    snap = OC.CalendarCache(None).snapshot()
    assert snap["status"] == "unavailable"
    assert "not found" in snap["error"]


def test_calendar_cache_reports_a_failed_fetch_as_unavailable():
    def boom(*_):
        raise OC.OutlookUnavailable("Outlook is not running")
    cache = OC.CalendarCache(["x"], fetch=boom)
    cache.refresh()
    snap = cache.snapshot()
    assert (snap["status"], snap["error"], snap["events"]) == ("unavailable", "Outlook is not running", [])
```

- [ ] **Step 3: Run to verify they fail**

Run: `python -m pytest scripts/tests/test_outlook_calendar.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'outlook_calendar'`.

- [ ] **Step 4: Implement** (`scripts/outlook_calendar.py`)

```python
#!/usr/bin/env python3
"""Outlook calendar for the local dashboard, read through the vendored outlook-mcp-rs MCP server
(spoken to directly over stdio JSON-RPC). stdlib only. Read-only: only `list_events` is ever called."""
from __future__ import annotations
import datetime as _dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BIN = REPO_ROOT / "vendor" / "outlook-mcp-rs" / "outlook-mcp-rs.exe"
PROTOCOL_VERSION = "2024-11-05"


class OutlookUnavailable(Exception):
    pass


def resolve_command() -> list[str] | None:
    """$OUTLOOK_MCP_BIN (what .mcp.json uses), else the vendored Windows binary."""
    env = os.environ.get("OUTLOOK_MCP_BIN")
    if env and Path(env).is_file():
        return [env]
    if sys.platform == "win32" and DEFAULT_BIN.is_file():
        return [str(DEFAULT_BIN)]
    return None


def call_list_events(command: list[str], start: _dt.date, end: _dt.date, timeout: float = 60) -> list[dict]:
    """Start the MCP server, handshake, call list_events once, shut it down."""
    try:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise OutlookUnavailable(f"could not start the Outlook MCP server: {e}") from e
    watchdog = threading.Timer(timeout, proc.kill)  # a hung server gets killed, which ends readline()
    watchdog.start()
    try:
        def send(msg: dict) -> None:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        def recv(want_id: int) -> dict:
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise OutlookUnavailable("the Outlook MCP server exited or timed out")
                line = line.strip()
                if line.startswith("{"):
                    msg = json.loads(line)
                    if msg.get("id") == want_id:
                        return msg

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "gtd-dashboard", "version": "1"}}})
        recv(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "list_events",
            "arguments": {"start_date": start.isoformat(), "end_date": end.isoformat()}}})
        msg = recv(2)
    except (OSError, ValueError) as e:  # broken pipe, malformed JSON
        raise OutlookUnavailable(f"talking to the Outlook MCP server failed: {e}") from e
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    if "error" in msg:
        raise OutlookUnavailable(msg["error"].get("message", "list_events failed"))
    result = msg.get("result", {})
    text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    if result.get("isError"):
        raise OutlookUnavailable(text or "list_events failed")
    try:
        events = json.loads(text or "[]")
    except ValueError as e:
        raise OutlookUnavailable(f"unexpected list_events output: {text[:80]!r}") from e
    return events if isinstance(events, list) else []


def normalize(events: list[dict]) -> list[dict]:
    """Just what the dashboard shows, declined meetings dropped, sorted by day (all-day first)."""
    out = []
    for e in events:
        start = str(e.get("start") or "")
        if len(start) < 10 or e.get("my_response") == "declined":
            continue
        out.append({
            "subject": e.get("subject") or "(no subject)",
            "start": start[:16],
            "end": str(e.get("end") or "")[:16],
            "date": start[:10],
            "all_day": bool(e.get("all_day")),
            "location": e.get("location") or "",
            "attendees": e.get("required_attendees") or "",
        })
    out.sort(key=lambda x: (x["date"], not x["all_day"], x["start"]))
    return out


class CalendarCache:
    """Keeps the next `days` days of events fresh from a background thread, so /api/state never
    waits on Outlook; snapshot() is always instant."""

    def __init__(self, command, ttl=300, days=7, fetch=call_list_events, today=_dt.date.today):
        self._command, self._ttl, self._days, self._fetch, self._today = command, ttl, days, fetch, today
        self._lock = threading.Lock()
        if command:
            self._state = {"status": "loading", "error": None, "events": [], "updated": None}
        else:
            self._state = {"status": "unavailable", "error": "Outlook MCP server not found "
                           "(set OUTLOOK_MCP_BIN — see docs/gtd/outlook.md)", "events": [], "updated": None}

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)

    def refresh(self) -> None:
        if not self._command:
            return
        start = self._today()
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        try:
            events = normalize(self._fetch(self._command, start, start + _dt.timedelta(days=self._days)))
            new = {"status": "ok", "error": None, "events": events, "updated": stamp}
        except OutlookUnavailable as e:
            new = {"status": "unavailable", "error": str(e), "events": [], "updated": stamp}
        with self._lock:
            self._state = new

    def start(self) -> None:
        def loop():
            while True:
                self.refresh()
                time.sleep(self._ttl)
        threading.Thread(target=loop, daemon=True, name="outlook-calendar").start()
```

- [ ] **Step 5: Run tests** — `python -m pytest scripts/tests/test_outlook_calendar.py -q` → PASS (9).

- [ ] **Step 6: Server test** (append to `test_dashboard_server.py`)

```python
class _FakeCalendar:
    def snapshot(self):
        return {"status": "ok", "error": None, "events": [{"subject": "Standup"}], "updated": "now"}


def test_state_includes_the_calendar_snapshot(tmp_path):
    _mk_vault(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(tmp_path, calendar=_FakeCalendar()))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            data = json.loads(r.read())
        assert data["calendar"]["events"][0]["subject"] == "Standup"
    finally:
        server.shutdown()


def test_state_calendar_is_off_without_a_calendar(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/state") as r:
            data = json.loads(r.read())
        assert data["calendar"]["status"] == "off"
    finally:
        server.shutdown()
```

Run: `python -m pytest scripts/tests/test_dashboard_server.py -q` → the two new tests FAIL.

- [ ] **Step 7: Implement in `dashboard_server.py`**

Add `import outlook_calendar as OC` next to the other imports, then:

```python
CALENDAR_OFF = {"status": "off", "error": None, "events": [], "updated": None}


def make_handler(vault: Path, calendar=None, auto_transcribe: bool = False):
```

(`auto_transcribe` is used in Task 10.) In `do_GET`:

```python
            if path == "/api/state":
                state = P.collect_state(vault)
                state["calendar"] = calendar.snapshot() if calendar else dict(CALENDAR_OFF)
                self._send_json(state)
                return
```

`main()`:

```python
    ap.add_argument("--no-outlook", action="store_true", help="don't read the Outlook calendar")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    calendar = None
    if not a.no_outlook:
        calendar = OC.CalendarCache(OC.resolve_command())
        calendar.start()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(vault, calendar=calendar, auto_transcribe=True))
```

- [ ] **Step 8: Run all Python tests** — `python -m pytest scripts/tests -q` → all pass.

- [ ] **Step 9: Real-Outlook smoke test** — with Outlook running:
`python -c "import sys; sys.path.insert(0,'scripts'); import outlook_calendar as OC, datetime as d; c=OC.CalendarCache(OC.resolve_command()); c.refresh(); s=c.snapshot(); print(s['status'], s['error'], len(s['events']))"`
Expected: `ok None <n>`.

- [ ] **Step 10: Commit**

```bash
git add scripts/outlook_calendar.py scripts/dashboard_server.py scripts/tests/fake_outlook_mcp.py scripts/tests/test_outlook_calendar.py scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): read the week's Outlook calendar via outlook-mcp-rs into /api/state"
```

---

### Task 8: Today page shows today's meetings

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (`localDateTime`, `eventsOn`, `filterEvents`, `eventTime`, `eventLine`, `calendarNote`, `renderToday`, `render`)
- Modify: `scripts/dashboard_static/app.js` (pass `now`), `style.css`
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Consumes: `state.calendar` (Task 7).
- Produces: `render(state, query, today, pending, now)` — `now` is `"YYYY-MM-DDTHH:MM"` (optional); `DashboardLogic.localDateTime(date) -> "YYYY-MM-DDTHH:MM:SS"`; meeting rows are `<li class="event nav-item" data-subject=… data-attendees=…>` (used by Tasks 9 and 11); `eventLine(ev, now)`, `eventsOn(calendar, date)`, `filterEvents(events, query)`, `calendarNote(calendar)` are internal helpers reused by Task 9.

- [ ] **Step 1: Write the failing tests**

```js
const CAL = { status: "ok", error: null, events: [
  { subject: "Holiday", start: "2026-09-11T00:00", end: "2026-09-12T00:00", date: "2026-09-11", all_day: true, location: "", attendees: "" },
  { subject: "סנכרון שבועי", start: "2026-09-11T09:30", end: "2026-09-11T10:00", date: "2026-09-11", all_day: false, location: "Room 1", attendees: "Dana; Omer" },
  { subject: "Planning", start: "2026-09-11T14:00", end: "2026-09-11T15:00", date: "2026-09-11", all_day: false, location: "", attendees: "" },
  { subject: "Tomorrow thing", start: "2026-09-12T09:00", end: "2026-09-12T09:30", date: "2026-09-12", all_day: false, location: "", attendees: "" },
] };
const BASE = { inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [], active_projects: [], someday_projects: [] };

test("the Today page lists today's meetings first, with times, dimming ones that are over", () => {
  const html = L.render({ ...BASE, calendar: CAL }, "", "2026-09-11", {}, "2026-09-11T12:00").todayHtml;
  assert.ok(html.indexOf("Meetings today") < html.indexOf("Nothing due this week"));
  assert.match(html, /<span class="ev-time">all day<\/span><span class="ev-subject" dir="auto">Holiday/);
  assert.match(html, /class="event nav-item event-past"[^>]*data-subject="סנכרון שבועי" data-attendees="Dana; Omer"/);
  assert.match(html, /<span class="ev-time">09:30–10:00<\/span>/);
  assert.match(html, /<span class="ev-loc" dir="auto">Room 1<\/span>/);
  assert.match(html, /class="event nav-item"[^>]*data-subject="Planning"/);
  assert.doesNotMatch(html, /Tomorrow thing/);
});

test("the Today page says when the Outlook calendar is loading or unavailable, and nothing when off", () => {
  const load = L.render({ ...BASE, calendar: { status: "loading", events: [] } }, "", "2026-09-11").todayHtml;
  assert.match(load, /Loading your Outlook calendar/);
  const down = L.render({ ...BASE, calendar: { status: "unavailable", error: "Outlook is not running", events: [] } }, "", "2026-09-11").todayHtml;
  assert.match(down, /Outlook calendar unavailable — Outlook is not running/);
  const off = L.render({ ...BASE, calendar: { status: "off", events: [] } }, "", "2026-09-11").todayHtml;
  assert.doesNotMatch(off, /Outlook/);
});

test("search filters today's meetings by subject", () => {
  const html = L.render({ ...BASE, calendar: CAL }, "plan", "2026-09-11").todayHtml;
  assert.match(html, /Planning/);
  assert.doesNotMatch(html, /Holiday/);
});

test("localDateTime formats local time without a timezone", () => {
  assert.equal(L.localDateTime(new Date(2026, 8, 11, 9, 5, 7)), "2026-09-11T09:05:07");
});
```

- [ ] **Step 2: Run to verify they fail** → FAIL.

- [ ] **Step 3: Implement** (in `logic.js`; export `localDateTime`)

```js
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function localDateTime(d) {
    return isoDate(d) + "T" + pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
  }

  function eventsOn(calendar, date) {
    return ((calendar && calendar.events) || []).filter(function (ev) { return ev.date === date; });
  }

  function filterEvents(events, query) {
    if (!query) return events;
    var q = query.toLowerCase();
    return events.filter(function (ev) {
      return (ev.subject || "").toLowerCase().indexOf(q) !== -1 || (ev.location || "").toLowerCase().indexOf(q) !== -1;
    });
  }

  function eventTime(ev) {
    if (ev.all_day) return "all day";
    var sameDay = ev.end && ev.end.slice(0, 10) === ev.date;
    return ev.start.slice(11, 16) + (sameDay ? "–" + ev.end.slice(11, 16) : "");
  }

  // A meeting row. Enter on it records that meeting (Task 11), hence the subject/attendees data.
  function eventLine(ev, now) {
    var past = now && !ev.all_day && ev.end && ev.end.slice(0, 16) <= now;
    return '<li class="event nav-item' + (past ? " event-past" : "") + '" data-key="' +
      escapeHtml("ev|" + ev.start + "|" + ev.subject) + '" data-subject="' + escapeHtml(ev.subject) +
      '" data-attendees="' + escapeHtml(ev.attendees || "") + '">' +
      '<span class="ev-time">' + escapeHtml(eventTime(ev)) + "</span>" +
      '<span class="ev-subject" dir="auto">' + escapeHtml(ev.subject) + "</span>" +
      (ev.location ? '<span class="ev-loc" dir="auto">' + escapeHtml(ev.location) + "</span>" : "") + "</li>";
  }

  function calendarNote(calendar) {
    var status = calendar && calendar.status;
    if (status === "loading") return '<p class="cal-note">Loading your Outlook calendar…</p>';
    if (status === "unavailable") {
      return '<p class="cal-note">Outlook calendar unavailable' +
        (calendar.error ? " — " + escapeHtml(calendar.error) : "") + "</p>";
    }
    return "";
  }
```

`renderToday` (full replacement):

```js
  function renderToday(state, query, today, pending, now) {
    var b = bucketDue(filterTasks(state.due_soon || [], query), today);
    var att = attentionItems(state, today);
    var alerts = att.filter(function (a) { return a.alert; });
    var reminders = att.filter(function (a) { return !a.alert; });
    function list(items) {
      return '<ul class="task-list">' + items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>";
    }
    var meetings = filterEvents(eventsOn(state.calendar, today), query);
    var html = calendarNote(state.calendar);
    if (meetings.length) {
      html += section("Meetings today", '<ul class="event-list">' +
        meetings.map(function (ev) { return eventLine(ev, now); }).join("") + "</ul>");
    }
    var due = "";
    if (b.overdue.length) due += section("Overdue", list(b.overdue), "section-alert");
    if (b.today.length) due += section("Due today", list(b.today));
    if (b.week.length) due += section("This week", list(b.week));
    html += due || '<p class="empty today-clear">' + (query ? "No due tasks match your search." : "Nothing due this week.") + "</p>";
    if (alerts.length) html += section("Needs attention", renderAttention(alerts));
    if (reminders.length) html += section("On your lists", renderAttention(reminders));
    return html;
  }
```

In `render`, add the `now` parameter and pass it: `function render(state, query, today, pending, now)` and `todayHtml: renderToday(state, query, today, pending, now),`.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Wire it up**

`app.js` `renderAll`: `var out = DashboardLogic.render(state, query, today(), pendingDeletes, DashboardLogic.localDateTime(new Date()).slice(0, 16));`

`style.css`:

```css
.event-list li {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px;
  padding: 5px 6px; border-bottom: 1px solid var(--border); border-radius: 4px; font-size: 0.9rem;
}
.ev-time { font-size: 0.78rem; color: var(--muted); min-width: 6.5em; font-variant-numeric: tabular-nums; }
.ev-subject { flex: 1 1 10em; }
.ev-loc { font-size: 0.78rem; color: var(--muted); }
.event-past { opacity: 0.55; }
.cal-note { color: var(--muted); font-size: 0.82rem; margin: 0 0 14px; }
```

- [ ] **Step 6: Verify** — with Outlook running, today's meetings show at the top of Today; with `--no-outlook` nothing Outlook-related appears.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/
git commit -m "feat(dashboard): today's Outlook meetings on the Today page"
```

---

### Task 9: Week page

**Files:**
- Modify: `scripts/dashboard_static/logic.js` (`PAGES`, `MONTHS`, `dayHeading`, `renderWeek`, `tabInfo`, `render`, `SHORTCUTS`)
- Modify: `scripts/dashboard_static/app.js`, `index.html`, `style.css`
- Test: `scripts/dashboard_static/logic.test.js`

**Interfaces:**
- Consumes: `eventsOn`, `filterEvents`, `eventLine`, `calendarNote` (Task 8); `pickHorizontal` (Task 4) makes `h`/`l` move between days for free.
- Produces: `PAGES = ["today", "week", "tasks", "inbox", "waiting", "projects"]`; `render(...).weekHtml`; `tabs.week = {count, alert}`.

- [ ] **Step 1: Write the failing tests** (and update "renderTabs numbers the pages…": `<kbd>2<\/kbd>Tasks` → `<kbd>3<\/kbd>Tasks`, and add `week: { count: 0, alert: false }` to its `info`; add `week: 1` into the expected counts of "render produces per-tab counts…" → `{ today: 1, week: 1, tasks: 2, inbox: 0, waiting: 1, projects: 1 }`)

```js
test("the Week page has a column per day with that day's meetings and due tasks", () => {
  const state = { ...BASE, calendar: CAL, due_soon: [
    { text: "Late one", file: "f.md", line_text: "a", due: "2026-09-09" },
    { text: "Pay rent", file: "f.md", line_text: "b", due: "2026-09-12" },
    { text: "Next week", file: "f.md", line_text: "c", due: "2026-09-18" },
  ] };
  const html = L.render(state, "", "2026-09-11", {}, "2026-09-11T08:00").weekHtml;
  const heads = [...html.matchAll(/<div class="ctx-h">([^<]*)<\/div>/g)].map((m) => m[1]);
  assert.deepEqual(heads, ["Overdue", "Today · Fri 11 Sep", "Tomorrow · Sat 12 Sep", "Sun 13 Sep", "Mon 14 Sep",
    "Tue 15 Sep", "Wed 16 Sep", "Thu 17 Sep"]);
  const sat = html.slice(html.indexOf("Tomorrow · Sat"), html.indexOf("Sun 13 Sep"));
  assert.match(sat, /Tomorrow thing/);
  assert.match(sat, /Pay rent/);
  assert.doesNotMatch(html, /Next week/); // a week out: not on this 7-day page
  assert.match(html.slice(0, html.indexOf("Today ·")), /Late one/);
  assert.match(html, /Nothing scheduled/);
});

test("the Week page has no Overdue column when nothing is overdue, and counts the week's tasks", () => {
  const state = { ...BASE, due_soon: [{ text: "Pay rent", file: "f.md", line_text: "b", due: "2026-09-12" }] };
  const out = L.render(state, "", "2026-09-11");
  assert.doesNotMatch(out.weekHtml, />Overdue</);
  assert.deepEqual(out.tabs.week, { count: 1, alert: false });
});
```

- [ ] **Step 2: Run to verify they fail** → FAIL.

- [ ] **Step 3: Implement**

```js
  var PAGES = ["today", "week", "tasks", "inbox", "waiting", "projects"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function dayHeading(date, today) {
    var d = new Date(date + "T00:00:00");
    var label = WEEKDAYS[d.getDay()] + " " + d.getDate() + " " + MONTHS[d.getMonth()];
    if (date === today) return "Today · " + label;
    if (date === addDays(today, 1)) return "Tomorrow · " + label;
    return label;
  }

  function renderWeek(state, query, today, pending, now) {
    var tasks = filterTasks(state.due_soon || [], query);
    function col(title, events, due, cls) {
      var body = (events.length ? '<ul class="event-list">' + events.map(function (ev) { return eventLine(ev, now); }).join("") + "</ul>" : "") +
        (due.length ? '<ul class="task-list">' + due.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>" : "");
      return '<div class="day-col' + (cls ? " " + cls : "") + '"><div class="ctx-h">' + escapeHtml(title) + "</div>" +
        (body || '<p class="empty">Nothing scheduled</p>') + "</div>";
    }
    var cols = [];
    var overdue = tasks.filter(function (t) { return t.due < today; });
    if (overdue.length) cols.push(col("Overdue", [], overdue, "day-overdue"));
    for (var i = 0; i < 7; i++) {
      var date = addDays(today, i);
      var due = tasks.filter(function (t) { return t.due === date; });
      cols.push(col(dayHeading(date, today), filterEvents(eventsOn(state.calendar, date), query), due, i === 0 ? "day-today" : ""));
    }
    return calendarNote(state.calendar) + '<div class="week-grid">' + cols.join("") + "</div>";
  }
```

In `tabInfo` add (after `today`):

```js
      week: {
        count: dueSoon.filter(function (t) { return t.due <= addDays(today, 6); }).length,
        alert: b.overdue.length > 0,
      },
```

In `render` add `weekHtml: renderWeek(state, query, today, pending, now),`.
In `SHORTCUTS` change `"1 – 5"` to `"1 – 6"`.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Wire it up**

`index.html`: add `<section class="page" id="page-week" hidden><div id="week"></div></section>` after `page-today`.
`app.js` `renderAll`: `document.getElementById("week").innerHTML = out.weekHtml;`
`style.css`:

```css
.week-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 18px 22px; align-items: start;
}
.day-today .ctx-h { color: var(--accent); }
.day-overdue .ctx-h { color: var(--red); }
.day-col .ev-time { min-width: 0; }
```

- [ ] **Step 6: Verify** — `2` opens Week; `j`/`k` move within a day, `h`/`l` between days; tabs read `1 Today … 6 Projects`.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/
git commit -m "feat(dashboard): Week page — a column per day with meetings and due tasks"
```

---

### Task 10: Server saves a recorded meeting and transcribes it in the background

**Files:**
- Modify: `scripts/dashboard_writer.py` (`meeting_note_content`, `save_meeting_recording`, lock in `run_transcription`, `start_background_transcription`)
- Modify: `scripts/dashboard_server.py` (`POST /api/record-meeting`)
- Test: `scripts/tests/test_dashboard_writer.py`, `scripts/tests/test_dashboard_server.py`

**Interfaces:**
- Produces: `W.save_meeting_recording(vault, pcm16: bytes, started: datetime, title: str|None = None, attendees: str = "", sample_rate: int = 16000) -> {"note": rel, "recording": rel}` (raises `ValueError` on empty audio); `W.start_background_transcription(vault) -> Thread`.
- HTTP: `POST /api/record-meeting?started=<local ISO>&title=<utf-8>&attendees=<utf-8>`, `Content-Type: application/octet-stream`, body = mono little-endian 16-bit PCM at 16 kHz → `200 {"ok": true, "note", "recording"}`; `415` for other content types; `400` for an empty body.

- [ ] **Step 1: Write the failing writer tests** (append to `test_dashboard_writer.py`; add `import datetime as dt`, `import wave`, `import pytest` at the top if missing)

```python
def test_save_meeting_recording_writes_a_wav_and_a_linked_pending_note(tmp_path):
    started = dt.datetime(2026, 9, 11, 14, 0, 5)
    out = W.save_meeting_recording(tmp_path, b"\x00\x10" * 16000, started,
                                   title="סנכרון שבועי: צוות", attendees="Dana; Omer")
    assert out == {"note": "Meetings/2026-09-11_14-00-05 סנכרון שבועי צוות.md",
                   "recording": "Meetings/recordings/2026-09-11_14-00-05.wav"}
    with wave.open(str(tmp_path / out["recording"]), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 16000)
    note = (tmp_path / out["note"]).read_text(encoding="utf-8")
    assert "transcription_status: pending" in note
    assert 'recording: "[[Meetings/recordings/2026-09-11_14-00-05.wav]]"' in note
    assert "# סנכרון שבועי: צוות" in note
    assert 'attendees: "Dana; Omer"' in note
    import transcribe_meetings as T  # the transcription script must find this recording
    fm, _ = T.parse_frontmatter(note)
    assert T.resolve_recording(tmp_path, fm) == tmp_path / out["recording"]
    assert (tmp_path / out["note"]) in T.find_pending(tmp_path)


def test_save_meeting_recording_without_a_title_matches_the_obsidian_plugin(tmp_path):
    out = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, dt.datetime(2026, 9, 11, 9, 5, 0))
    assert out["note"] == "Meetings/2026-09-11_09-05-00 Meeting.md"
    note = (tmp_path / out["note"]).read_text(encoding="utf-8")
    assert "# Meeting 2026-09-11" in note
    assert "attendees: \n" in note


def test_save_meeting_recording_never_overwrites(tmp_path):
    started = dt.datetime(2026, 9, 11, 9, 5, 0)
    a = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, started, title="Sync")
    b = W.save_meeting_recording(tmp_path, b"\x00\x00" * 10, started, title="Sync")
    assert a["note"] != b["note"] and a["recording"] != b["recording"]
    assert (tmp_path / b["note"]).read_text(encoding="utf-8").count(b["recording"]) == 1


def test_save_meeting_recording_rejects_empty_audio(tmp_path):
    with pytest.raises(ValueError):
        W.save_meeting_recording(tmp_path, b"", dt.datetime(2026, 9, 11, 9, 0, 0))


def test_start_background_transcription_runs_transcription(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "run_transcription", lambda vault: calls.append(vault) or "ok")
    W.start_background_transcription(tmp_path).join(timeout=5)
    assert calls == [tmp_path]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest scripts/tests/test_dashboard_writer.py -q`
Expected: FAIL with `AttributeError: module 'dashboard_writer' has no attribute 'save_meeting_recording'`.

- [ ] **Step 3: Implement** (`dashboard_writer.py`; add `import json as _json`, `import threading as _threading`, `import wave as _wave` to the imports)

```python
RECORDINGS_DIR = "Meetings/recordings"
SAMPLE_RATE = 16000
_UNSAFE_NAME_RE = _re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]+')
_TRANSCRIBE_LOCK = _threading.Lock()


def _one_line(s: str | None) -> str:
    return " ".join((s or "").split())


def _safe_title(title: str | None) -> str:
    """A meeting title usable as (part of) a file name on Windows and in Obsidian links."""
    t = _one_line(_UNSAFE_NAME_RE.sub(" ", title or "")).strip(".")
    return t[:80].strip() or "Meeting"


def meeting_note_content(date_str: str, recording_rel: str, heading: str, attendees: str = "") -> str:
    """Same note the record-meeting Obsidian plugin writes (.obsidian/plugins/record-meeting/lib.js
    meetingNoteContent), plus a real heading/attendees when the recording came from a calendar event."""
    return (
        "---\n"
        "type: meeting\n"
        f"date: {date_str}\n"
        f"attendees: {_json.dumps(attendees, ensure_ascii=False) if attendees else ''}\n"
        f'recording: "[[{recording_rel}]]"\n'
        "transcription_status: pending\n"
        "---\n\n"
        f"# {heading}\n\n"
        f"**Date:** {date_str}\n"
        f"**Attendees:** {attendees}\n\n"
        "## Notes\n\n"
        "## Decisions\n\n"
        "## Transcript\n\n"
        "## Action items\n- [ ]  #next\n"
    )


def save_meeting_recording(vault: Path, pcm16: bytes, started: _dt.datetime, title: str | None = None,
                           attendees: str = "", sample_rate: int = SAMPLE_RATE) -> dict:
    """Write mono 16-bit PCM as Meetings/recordings/<stamp>.wav plus a linked meeting note with
    transcription_status: pending — exactly what the transcription script picks up."""
    if not pcm16:
        raise ValueError("empty recording")
    if len(pcm16) % 2:
        pcm16 = pcm16[:-1]
    vault = Path(vault)
    slug = started.strftime("%Y-%m-%d_%H-%M-%S")
    rec_rel, n = f"{RECORDINGS_DIR}/{slug}.wav", 2
    while _resolve(vault, rec_rel).exists():
        rec_rel, n = f"{RECORDINGS_DIR}/{slug}-{n}.wav", n + 1
    rec_path = _resolve(vault, rec_rel)
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    with _wave.open(str(rec_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16)

    name = _safe_title(title)
    note_rel, n = f"Meetings/{slug} {name}.md", 2
    while _resolve(vault, note_rel).exists():
        note_rel, n = f"Meetings/{slug} {name} {n}.md", n + 1
    date_str = started.date().isoformat()
    heading = _one_line(title) or f"Meeting {date_str}"
    _resolve(vault, note_rel).write_text(
        meeting_note_content(date_str, rec_rel, heading, _one_line(attendees)), encoding="utf-8")
    return {"note": note_rel, "recording": rec_rel}
```

Wrap the body of `run_transcription` in the lock:

```python
def run_transcription(vault: Path) -> str:
    # one run at a time: two concurrent runs would both pick up the same pending note
    with _TRANSCRIBE_LOCK:
        vault = Path(vault)
        script = Path(__file__).resolve().parent / "transcribe_meetings.py"
        result = _subprocess.run(
            [_sys.executable, str(script), str(vault)],
            capture_output=True, text=True, timeout=1800,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "transcription failed")
    return result.stdout.strip()


def start_background_transcription(vault: Path) -> _threading.Thread:
    """Transcribe pending recordings without making the caller wait (a meeting can take minutes)."""
    def work():
        try:
            run_transcription(vault)
        except Exception as e:  # noqa: BLE001 - per-note failures are written into the note itself
            print(f"background transcription failed: {e}", file=_sys.stderr)
    t = _threading.Thread(target=work, daemon=True, name="transcribe")
    t.start()
    return t
```

- [ ] **Step 4: Run writer tests** → PASS.

- [ ] **Step 5: Write the failing server tests** (append to `test_dashboard_server.py`; add `from urllib.parse import urlencode` and `from urllib.error import HTTPError` and `import pytest` if missing)

```python
def _post_audio(server, query, body, content_type="application/octet-stream"):
    req = request.Request(f"http://127.0.0.1:{server.server_port}/api/record-meeting?{query}", data=body,
                          method="POST", headers={"Content-Type": content_type})
    return request.urlopen(req)


def test_record_meeting_saves_a_note_and_wav(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        q = urlencode({"title": "סנכרון", "attendees": "Dana", "started": "2026-09-11T14:00:05"})
        with _post_audio(server, q, b"\x00\x00" * 1600) as r:
            data = json.loads(r.read())
        assert data["note"] == "Meetings/2026-09-11_14-00-05 סנכרון.md"
        assert (tmp_path / data["recording"]).is_file()
        assert "# סנכרון" in (tmp_path / data["note"]).read_text(encoding="utf-8")
    finally:
        server.shutdown()


def test_record_meeting_rejects_json_and_empty_bodies(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with pytest.raises(HTTPError) as e:
            _post_audio(server, "", b"{}", content_type="application/json")
        assert e.value.code == 415
        with pytest.raises(HTTPError) as e:
            _post_audio(server, "", b"")
        assert e.value.code == 400
    finally:
        server.shutdown()


def test_record_meeting_starts_transcription_when_enabled(tmp_path, monkeypatch):
    _mk_vault(tmp_path)
    calls = []
    monkeypatch.setattr(S.W, "start_background_transcription", lambda vault: calls.append(vault))
    server = ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(tmp_path, auto_transcribe=True))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with _post_audio(server, "started=2026-09-11T14:00:05", b"\x00\x00" * 10):
            pass
        assert calls == [tmp_path]
    finally:
        server.shutdown()
```

Run: `python -m pytest scripts/tests/test_dashboard_server.py -q` → the three new tests FAIL (404/415).

- [ ] **Step 6: Implement the endpoint** (`dashboard_server.py`; add `import datetime as _dt` and `from urllib.parse import urlparse, parse_qs`)

```python
MAX_RECORDING_BYTES = 1_000_000_000  # ~8.7 h of 16 kHz mono 16-bit audio
```

Inside the handler class:

```python
        def _record_meeting(self):
            if not self.headers.get("Content-Type", "").startswith("application/octet-stream"):
                self._send_json({"error": "expected application/octet-stream"}, 415)
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0 or length > MAX_RECORDING_BYTES:
                self._send_json({"error": "recording is empty or too large"}, 400)
                return
            pcm = self.rfile.read(length)
            q = parse_qs(urlparse(self.path).query)
            try:
                started = _dt.datetime.fromisoformat(q.get("started", [""])[0])
            except ValueError:
                started = _dt.datetime.now()
            try:
                result = W.save_meeting_recording(vault, pcm, started, q.get("title", [""])[0],
                                                  q.get("attendees", [""])[0])
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
                return
            if auto_transcribe:
                W.start_background_transcription(vault)
            self._send_json({"ok": True, **result})
```

In `do_POST`, right after the Host check and before the `application/json` check:

```python
            if path == "/api/record-meeting":
                try:
                    self._record_meeting()
                except Exception as e:
                    self._send_json({"error": "internal error: " + str(e)}, 500)
                return
```

- [ ] **Step 7: Run all Python tests** — `python -m pytest scripts/tests -q` → all pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/dashboard_writer.py scripts/dashboard_server.py scripts/tests/test_dashboard_writer.py scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): /api/record-meeting saves WAV + meeting note, transcribes in background"
```

---

### Task 11: "Record a meeting" button, `r` shortcut, and Enter-on-a-meeting

**Files:**
- Create: `scripts/dashboard_static/recorder.js`, `scripts/dashboard_static/recorder.test.js`
- Modify: `scripts/dashboard_static/logic.js` (`currentEvent`, `recordingUrl`, `SHORTCUTS`)
- Modify: `scripts/dashboard_static/app.js`, `index.html`, `style.css`
- Modify: `scripts/dashboard_server.py` (`STATIC_FILES`)
- Test: `logic.test.js`, `recorder.test.js`, `scripts/tests/test_dashboard_server.py`

**Interfaces:**
- Consumes: `keyAction` → `"record"` (Task 1); event rows' `data-subject`/`data-attendees` (Task 8); `/api/record-meeting` (Task 10); `localDateTime` (Task 8).
- Produces: `MeetingRecorder.start() -> Promise<{startedAt: Date, stop(): Promise<Int16Array>}>`, `MeetingRecorder.toPcm16(chunks) -> Int16Array`; `DashboardLogic.currentEvent(calendar, now) -> event|null`; `DashboardLogic.recordingUrl({started, title, attendees}) -> string`.

- [ ] **Step 1: Write the failing tests**

`recorder.test.js`:

```js
// scripts/dashboard_static/recorder.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("./recorder.js");

test("toPcm16 joins chunks and scales/clips floats to 16-bit integers", () => {
  const out = R.toPcm16([new Float32Array([0, 1, -1]), new Float32Array([0.5, 2, -2])]);
  assert.ok(out instanceof Int16Array);
  assert.deepEqual(Array.from(out), [0, 32767, -32768, 16383, 32767, -32768]);
});
```

`logic.test.js`:

```js
test("currentEvent picks the timed meeting under way or starting within 10 minutes", () => {
  assert.equal(L.currentEvent(CAL, "2026-09-11T09:25").subject, "סנכרון שבועי");
  assert.equal(L.currentEvent(CAL, "2026-09-11T09:45").subject, "סנכרון שבועי");
  assert.equal(L.currentEvent(CAL, "2026-09-11T10:00"), null); // over; the all-day Holiday never counts
  assert.equal(L.currentEvent(CAL, "2026-09-11T13:55").subject, "Planning");
  assert.equal(L.currentEvent({ status: "off", events: [] }, "2026-09-11T09:30"), null);
});

test("recordingUrl encodes a Hebrew title and attendees for the upload", () => {
  assert.equal(L.recordingUrl({ started: "2026-09-11T14:00:05", title: "", attendees: "" }),
    "/api/record-meeting?started=2026-09-11T14%3A00%3A05");
  assert.equal(L.recordingUrl({ started: "2026-09-11T14:00:05", title: "סנכרון", attendees: "Dana; Omer" }),
    "/api/record-meeting?started=2026-09-11T14%3A00%3A05&title=%D7%A1%D7%A0%D7%9B%D7%A8%D7%95%D7%9F&attendees=Dana%3B%20Omer");
});
```

`test_dashboard_server.py`:

```python
def test_get_recorder_js(tmp_path):
    _mk_vault(tmp_path)
    server = _start_server(tmp_path)
    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/recorder.js") as r:
            assert r.headers["Content-Type"].startswith("application/javascript")
            assert b"MeetingRecorder" in r.read()
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test scripts/dashboard_static/logic.test.js scripts/dashboard_static/recorder.test.js` → FAIL (`Cannot find module './recorder.js'`, `currentEvent is not a function`).
Run: `python -m pytest scripts/tests/test_dashboard_server.py -q -k recorder` → FAIL (404).

- [ ] **Step 3: Implement `recorder.js`**

```js
// scripts/dashboard_static/recorder.js
// Microphone capture for "Record a meeting": 16 kHz mono via Web Audio — the same approach as the
// record-meeting Obsidian plugin — handed back as 16-bit PCM; the server writes the WAV.
(function (root) {
  var SAMPLE_RATE = 16000;

  // Float32 chunks in [-1, 1] → one Int16Array (little-endian on every platform browsers run on).
  function toPcm16(chunks) {
    var total = 0;
    chunks.forEach(function (c) { total += c.length; });
    var out = new Int16Array(total);
    var o = 0;
    chunks.forEach(function (c) {
      for (var i = 0; i < c.length; i++) {
        var s = Math.max(-1, Math.min(1, c[i]));
        out[o++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
    });
    return out;
  }

  function start() {
    return navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
    }).then(function (stream) {
      var ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      var source = ctx.createMediaStreamSource(stream);
      var processor = ctx.createScriptProcessor(4096, 1, 1);
      var chunks = [];
      processor.onaudioprocess = function (ev) {
        chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(ctx.destination);
      return {
        startedAt: new Date(),
        stop: function () {
          processor.disconnect();
          source.disconnect();
          stream.getTracks().forEach(function (t) { t.stop(); });
          return ctx.close().then(function () { return toPcm16(chunks); });
        },
      };
    });
  }

  var api = { SAMPLE_RATE: SAMPLE_RATE, toPcm16: toPcm16, start: start };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.MeetingRecorder = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

`dashboard_server.py` `STATIC_FILES`: add `"/recorder.js": ("recorder.js", "application/javascript; charset=utf-8"),`.

`logic.js` (export both):

```js
  // The timed meeting under way now, or starting within 10 minutes — used to name a recording.
  function currentEvent(calendar, now) {
    var d = new Date(now + ":00");
    d.setMinutes(d.getMinutes() + 10);
    var soon = localDateTime(d).slice(0, 16);
    var hits = ((calendar && calendar.events) || []).filter(function (ev) {
      return !ev.all_day && ev.start.slice(0, 16) <= soon && (ev.end || "").slice(0, 16) > now;
    });
    return hits[0] || null;
  }

  function recordingUrl(meta) {
    var q = "started=" + encodeURIComponent(meta.started);
    if (meta.title) q += "&title=" + encodeURIComponent(meta.title);
    if (meta.attendees) q += "&attendees=" + encodeURIComponent(meta.attendees);
    return "/api/record-meeting?" + q;
  }
```

In `SHORTCUTS`, change the Enter row to `["Enter", "Open the selected item (on a meeting: record it)"]` and add `["r", "Record a meeting / stop recording"]` after the `n` row.

- [ ] **Step 4: Run tests** → PASS (JS and Python).

- [ ] **Step 5: Wire up the UI**

`index.html`: in `.toolbar`, before `#new-task-btn`:
`<button id="record-btn" type="button" title="Record a meeting (r)">● Record</button>`;
before `app.js`: `<script src="recorder.js"></script>`.

`app.js` — add a `// ---- recording ----` block:

```js
  // ---- recording ----

  var RECORD_LABEL = "● Record";
  var recordBtn = document.getElementById("record-btn");
  var rec = null;     // { handle, meta, timer } while recording
  var unsaved = null; // { pcm, meta } when an upload failed — kept so the audio isn't lost

  function setRecordButton(text, cls) {
    recordBtn.textContent = text;
    recordBtn.className = cls || "";
  }

  function toggleRecording(ev) {
    if (unsaved) { upload(unsaved.pcm, unsaved.meta); return; }
    if (rec) stopRecording();
    else startRecording(ev);
  }

  function startRecording(ev) {
    recordBtn.disabled = true;
    MeetingRecorder.start().then(function (handle) {
      var e = ev || DashboardLogic.currentEvent(state && state.calendar, DashboardLogic.localDateTime(new Date()).slice(0, 16));
      rec = { handle: handle, meta: {
        started: DashboardLogic.localDateTime(handle.startedAt),
        title: e ? e.subject : "", attendees: e ? e.attendees || "" : "",
      } };
      recordBtn.disabled = false;
      tick();
      rec.timer = setInterval(tick, 1000);
    }).catch(function () {
      recordBtn.disabled = false;
      flash("Mic unavailable");
    });
  }

  function tick() {
    var secs = Math.floor((Date.now() - rec.handle.startedAt.getTime()) / 1000);
    setRecordButton("■ " + Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0") +
      (rec.meta.title ? " · " + rec.meta.title : ""), "recording");
  }

  function stopRecording() {
    var r = rec;
    rec = null;
    clearInterval(r.timer);
    recordBtn.disabled = true;
    setRecordButton("Saving…");
    r.handle.stop().then(function (pcm) { upload(pcm, r.meta); }, function () { flash("Recording failed"); });
  }

  function upload(pcm, meta) {
    recordBtn.disabled = true;
    setRecordButton("Saving…");
    fetch(DashboardLogic.recordingUrl(meta), {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm.buffer,
    }).then(function (res) {
      if (!res.ok) throw new Error("save failed: " + res.status);
      unsaved = null;
      flash("Saved ✓ transcribing…");
      refresh();
    }).catch(function () {
      unsaved = { pcm: pcm, meta: meta };
      recordBtn.disabled = false;
      setRecordButton("Save failed — retry", "recording");
    });
  }

  function flash(text) {
    recordBtn.disabled = false;
    setRecordButton(text);
    setTimeout(function () { if (!rec && !unsaved) setRecordButton(RECORD_LABEL); }, 4000);
  }

  recordBtn.addEventListener("click", function () { toggleRecording(); });
  window.addEventListener("beforeunload", function (e) {
    if (rec || unsaved) { e.preventDefault(); e.returnValue = ""; }
  });
```

In `runAction` add `case "record": toggleRecording(); return true;`.
In `activate(el)`, before the final `else`:

```js
    } else if (el.classList.contains("event")) {
      toggleRecording({ subject: el.getAttribute("data-subject"), attendees: el.getAttribute("data-attendees") || "" });
```

`style.css`:

```css
#record-btn { max-width: 16rem; overflow: hidden; text-overflow: ellipsis; }
#record-btn.recording { border-color: var(--red); color: var(--red); font-weight: 600; font-variant-numeric: tabular-nums; }
#record-btn:disabled { opacity: 0.6; cursor: default; }
```

- [ ] **Step 6: Verify in the browser** (scratch vault, server restarted so `/recorder.js` is served)
  1. Press `r` → browser asks for the mic (localhost is a secure context) → button shows `■ 0:01 …` counting.
  2. Speak a few seconds, press `r` → "Saving…" then "Saved ✓ transcribing…"; `Meetings/recordings/<stamp>.wav` and `Meetings/<stamp> Meeting.md` exist in the scratch vault; the note has `transcription_status: pending` (then `done`/`failed` once the background run ends).
  3. With a meeting on today's calendar: select it on Today, `Enter` → recording titled with its subject.
  4. Stop the server mid-recording, stop → "Save failed — retry"; restart the server, press `r` → saved.

- [ ] **Step 7: Commit**

```bash
git add scripts/dashboard_static/ scripts/dashboard_server.py scripts/tests/test_dashboard_server.py
git commit -m "feat(dashboard): Record a meeting — button, r shortcut, Enter on a calendar meeting"
```

---

### Task 12: Docs, full verification, worktree rebase

**Files:**
- Modify: `docs/gtd/local-dashboard.md`, `docs/gtd/meeting-recording.md`, `Meetings/README.md`

- [ ] **Step 1: Update `docs/gtd/local-dashboard.md`** — pages are now `1 Today · 2 Week · 3 Tasks · 4 Inbox · 5 Waiting · 6 Projects`; Today shows today's Outlook meetings (needs Outlook running + `outlook-mcp-rs`, `--no-outlook` to disable); Week = a column per day; shortcuts work under any keyboard layout (matched on the physical key); `h`/`l`/`←`/`→` move between columns; `Esc` clears search and a banner shows an active filter; `r` / **● Record** records a meeting (named after the Outlook meeting happening now; `Enter` on a meeting records that one), saved like the Obsidian mic button and transcribed automatically; Meetings page removed (follow-ups live on Today).
- [ ] **Step 2: Update `docs/gtd/meeting-recording.md`** "Recording and transcribing" — add the dashboard's **● Record** button / `r` as a third way to record, and replace the stale "Meetings card has the same Transcribe pending button … Needs triage card" sentence with: the dashboard transcribes its own recordings automatically, Today's *Needs attention* offers "N meetings to transcribe" (Enter runs it) for recordings made elsewhere, and #unknown-context action items show under *Needs triage* on the Tasks page. Add one line to `Meetings/README.md` pointing at the dashboard button.
- [ ] **Step 3: Full test run** — `node --test scripts/dashboard_static/logic.test.js scripts/dashboard_static/recorder.test.js` and `python -m pytest scripts/tests -q` → all pass.
- [ ] **Step 4: Browser pass** — every page via `1`–`6` under a Hebrew layout; `j/k/h/l`; search + `Esc`; record + stop; dark theme; 400 px width.
- [ ] **Step 5: Commit docs**

```bash
git add docs/gtd/local-dashboard.md docs/gtd/meeting-recording.md Meetings/README.md
git commit -m "docs(dashboard): Week/Inbox pages, Outlook meetings, Record a meeting, layout-proof keys"
```

- [ ] **Step 6: Rebase every worktree onto master** — for each `git worktree list` entry other than master: if it has uncommitted changes, move its branch with `git replay --onto master master..<branch>` + `git update-ref` (guarded on the old sha) and check out only the files master changed, so in-progress work is never rewritten on disk; otherwise `git -C <worktree> rebase master`. Confirm its uncommitted diff is unchanged afterwards and its tests pass.
