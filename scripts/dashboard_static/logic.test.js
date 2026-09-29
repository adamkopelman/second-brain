// scripts/dashboard_static/logic.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("./logic.js");

const TODAY = "2026-09-29"; // a Tuesday

function todo(over) {
  return Object.assign({
    file: "10 Projects/P.md", line_text: "- [ ] " + (over.text || "x"), text: "x", links: [], done: false,
    completed: null, status: "next", context: "computer", tags: [], when: null, evening: false, deadline: null,
    since: null, heading: null, project: null, area: null, meeting: null, inbox: false,
  }, over, { line_text: over.line_text || "- [ ] " + (over.text || "x") });
}

function stateWith(todos, extra) {
  return Object.assign({ vault_name: "Vault", todos: todos, projects: [], areas: [], inbox_notes: [], meetings: [] }, extra);
}

const titles = (list) => list.map((t) => t.text);

test("escapeHtml escapes the five XSS-relevant characters and tolerates null", () => {
  assert.equal(L.escapeHtml(`<a href="x">&'</a>`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
  assert.equal(L.escapeHtml(null), "");
});

test("Today holds what's scheduled for today or earlier, or due by today; evening items split off", () => {
  const s = stateWith([
    todo({ text: "scheduled today", when: TODAY }),
    todo({ text: "scheduled earlier", when: "2026-09-20" }),
    todo({ text: "due today", deadline: TODAY }),
    todo({ text: "overdue", deadline: "2026-09-27" }),
    todo({ text: "evening", when: TODAY, evening: true }),
    todo({ text: "tomorrow", when: "2026-09-30" }),
    todo({ text: "someday but dated", when: TODAY, status: "someday" }),
    todo({ text: "done", when: TODAY, done: true }),
    todo({ text: "plain" }),
  ]);
  const t = L.listToday(s, TODAY);
  assert.deepEqual(titles(t.day), ["overdue", "scheduled today", "scheduled earlier", "due today"]); // overdue first
  assert.deepEqual(titles(t.evening), ["evening"]);
});

test("Anytime is every available next action: not inbox, waiting, someday or scheduled ahead", () => {
  const s = stateWith([
    todo({ text: "loose next" }),
    todo({ text: "project, untagged", status: null, project: "P" }),
    todo({ text: "untagged journal line", status: null, file: "Journal/d.md" }),
    todo({ text: "inbox", inbox: true }),
    todo({ text: "waiting", status: "waiting" }),
    todo({ text: "someday", status: "someday" }),
    todo({ text: "later", when: "2026-10-05" }),
    todo({ text: "today", when: TODAY }),
    todo({ text: "in someday project", project: "S" }),
  ], { projects: [{ name: "P", status: "active" }, { name: "S", status: "someday" }] });
  assert.deepEqual(titles(L.listAnytime(s, TODAY)), ["loose next", "project, untagged", "today"]);
});

test("Someday lists someday to-dos and someday projects; Waiting sorts oldest first", () => {
  const s = stateWith([
    todo({ text: "sail", status: "someday" }),
    todo({ text: "inside someday project", status: "someday", project: "S" }),
    todo({ text: "newer", status: "waiting", since: "2026-09-20" }),
    todo({ text: "older", status: "waiting", since: "2026-09-01" }),
  ], { projects: [{ name: "S", status: "someday" }] });
  const sd = L.listSomeday(s);
  assert.deepEqual(titles(sd.todos), ["sail"]);
  assert.deepEqual(sd.projects.map((p) => p.name), ["S"]);
  assert.deepEqual(titles(L.listWaiting(s)), ["older", "newer"]);
});

test("Upcoming has the next seven days one by one, with events, then later months", () => {
  const s = stateWith([
    todo({ text: "thu", when: "2026-10-01" }),
    todo({ text: "deadline only", deadline: "2026-10-02" }),
    todo({ text: "october", when: "2026-10-20" }),
    todo({ text: "november", deadline: "2026-11-03" }),
    todo({ text: "someday", when: "2026-10-01", status: "someday" }),
    todo({ text: "today", when: TODAY }),
  ], { calendar: { status: "ok", events: [
    { date: "2026-09-30", start: "2026-09-30T11:00:00", end: "2026-09-30T11:30:00", subject: "1:1" },
    { date: TODAY, start: TODAY + "T09:00:00", end: TODAY + "T09:30:00", subject: "Standup" },
  ] } });
  const u = L.listUpcoming(s, TODAY);
  assert.equal(u.days.length, 7);
  assert.equal(u.days[0].date, "2026-09-30");
  assert.deepEqual(u.days[0].events.map((e) => e.subject), ["1:1"]); // today's standup is on Today, not here
  assert.deepEqual(titles(u.days[1].todos), ["thu"]);
  assert.deepEqual(titles(u.days[2].todos), ["deadline only"]);
  assert.deepEqual(u.months.map((m) => [m.month, titles(m.todos)]), [["2026-10", ["october"]], ["2026-11", ["november"]]]);
});

test("Logbook groups completed to-dos: Today, Yesterday, weekdays, then months", () => {
  const s = stateWith([
    todo({ text: "a", done: true, completed: TODAY }),
    todo({ text: "b", done: true, completed: "2026-09-28" }),
    todo({ text: "c", done: true, completed: "2026-09-25" }),
    todo({ text: "d", done: true, completed: "2026-08-02" }),
    todo({ text: "e", done: true, completed: null }),
    todo({ text: "open" }),
  ]);
  assert.deepEqual(L.listLogbook(s, TODAY).map((g) => [g.label, titles(g.todos)]),
    [["Today", ["a"]], ["Yesterday", ["b"]], ["Friday", ["c"]], ["August", ["d"]], ["Earlier", ["e"]]]);
});

test("parseWhen understands Things-style dates", () => {
  const cases = {
    today: "today", tonight: "evening", "this evening": "evening", someday: "someday", anytime: "anytime",
    tomorrow: "2026-09-30", fri: "2026-10-02", friday: "2026-10-02", "next fri": "2026-10-09", tue: "2026-10-06",
    "in 3 days": "2026-10-02", "2w": "2026-10-13", "next week": "2026-10-05", "next month": "2026-10-01",
    weekend: "2026-10-03", "oct 3": "2026-10-03", "3 oct": "2026-10-03", "sep 1": "2027-09-01",
    "2026-10-05": "2026-10-05", "2026-09-01": "today",
  };
  for (const [text, want] of Object.entries(cases)) assert.equal(L.parseWhen(text, TODAY), want, text);
  for (const junk of ["", "xyz", "ma", "feb 31"]) assert.equal(L.parseWhen(junk, TODAY), null, junk);
});

test("dates read like Things: weekday this week, then month and day; deadlines count down", () => {
  assert.equal(L.shortDate("2026-10-02", TODAY), "Fri");
  assert.equal(L.shortDate("2026-10-12", TODAY), "Oct 12");
  assert.equal(L.shortDate("2027-01-03", TODAY), "Jan 3, 2027");
  assert.equal(L.deadlineLabel("2026-09-27", TODAY), "2 days ago");
  assert.equal(L.deadlineLabel(TODAY, TODAY), "today");
  assert.equal(L.deadlineLabel("2026-09-30", TODAY), "tomorrow");
  assert.equal(L.deadlineLabel("2026-10-02", TODAY), "3 days left");
  assert.equal(L.whenLabel({ when: TODAY, evening: true }, TODAY), "This Evening");
  assert.equal(L.whenLabel({ when: "2026-10-02" }, TODAY), "Fri, Oct 2");
  assert.equal(L.whenLabel({ status: "someday" }, TODAY), "Someday");
});

test("routes round-trip through the URL hash, including project names with spaces", () => {
  assert.deepEqual(L.parseRoute("#upcoming"), { view: "upcoming" });
  assert.deepEqual(L.parseRoute(""), { view: "today" });
  assert.deepEqual(L.parseRoute("#nonsense"), { view: "today" });
  const r = { view: "project", name: "Website Redesign" };
  assert.deepEqual(L.parseRoute(L.routeHash(r)), r);
});

test("homeRoute sends a to-do where it lives; newTodoDefaults files a new one where you are", () => {
  const s = stateWith([], { projects: [{ name: "P", status: "active" }] });
  assert.deepEqual(L.homeRoute(todo({ project: "P" }), s, TODAY), { view: "project", name: "P" });
  assert.deepEqual(L.homeRoute(todo({ inbox: true }), s, TODAY), { view: "inbox" });
  assert.deepEqual(L.homeRoute(todo({ when: TODAY }), s, TODAY), { view: "today" });
  assert.deepEqual(L.homeRoute(todo({ when: "2026-10-09" }), s, TODAY), { view: "upcoming" });
  assert.deepEqual(L.homeRoute(todo({ done: true }), s, TODAY), { view: "logbook" });
  assert.equal(L.newTodoDefaults({ view: "today" }, TODAY).when, "today");
  assert.equal(L.newTodoDefaults({ view: "upcoming" }, TODAY).when, "2026-09-30");
  assert.equal(L.newTodoDefaults({ view: "someday" }, TODAY).status, "someday");
  assert.equal(L.newTodoDefaults({ view: "project", name: "P" }, TODAY).project, "P");
  assert.equal(L.newTodoDefaults({ view: "anytime" }, TODAY, "phone").context, "phone");
});

test("Anytime groups loose to-dos first, then projects, areas gathering their own", () => {
  const s = stateWith([], { projects: [{ name: "Site", area: "Work" }, { name: "Garage" }] });
  const groups = L.groupByProject([
    todo({ text: "site", project: "Site", area: "Work" }), todo({ text: "loose" }),
    todo({ text: "work area", area: "Work" }), todo({ text: "garage", project: "Garage" }),
  ], s);
  assert.deepEqual(groups.map((g) => g.kind + ":" + (g.name || "")), ["loose:", "project:Garage", "area:Work", "project:Site"]);
});

test("tags are contexts plus extra tags, ordered like the GTD contexts, and filter lists", () => {
  const todos = [todo({ context: "phone" }), todo({ context: "computer", tags: ["reading"] }), todo({ context: "phone" })];
  assert.deepEqual(L.tagCounts(todos), [{ tag: "computer", count: 1 }, { tag: "phone", count: 2 }, { tag: "reading", count: 1 }]);
  assert.equal(L.byTag(todos, "phone").length, 2);
  assert.equal(L.byTag(todos, null).length, 3);
});

test("a to-do row escapes its text, marks direction, and shows star, deadline and project", () => {
  const html = L.todoRow(todo({ text: "<b>x</b>", deadline: "2026-09-27", when: TODAY, project: "Site" }), { today: TODAY, list: "anytime" });
  assert.ok(html.includes("&lt;b&gt;x&lt;/b&gt;"));
  assert.ok(!html.includes("<b>x</b>"));
  assert.ok(html.includes('dir="auto"'));
  assert.ok(html.includes("i-today"), "items in Today carry a star elsewhere");
  assert.ok(/deadline urgent[^>]*>.*2 days ago/.test(html));
  assert.ok(html.includes('class="where" dir="auto">Site'));
  assert.ok(!L.todoRow(todo({ when: TODAY }), { today: TODAY, list: "today" }).includes("i-today"), "no star on Today itself");
});

test("an open to-do renders as an editable card with When, Deadline, tag and Move", () => {
  const t = todo({ text: "Draft", when: "2026-10-02", deadline: "2026-10-09", context: "phone" });
  const key = L.taskKey(t.file, t.line_text);
  const html = L.todoRow(t, { today: TODAY, list: "anytime", expanded: key });
  assert.ok(html.includes('class="card-title"') && html.includes('value="Draft"'));
  assert.ok(html.includes("Fri, Oct 2"));
  assert.ok(html.includes('value="2026-10-09"'));
  assert.ok(/<option value="phone" selected>/.test(html));
  assert.ok(!html.includes("No tag"), "a set context can be changed, not removed");
  assert.ok(html.includes('data-act="move"') && html.includes('data-act="delete"'));
});

test("renderView shows Today with meetings, heads-up items and This Evening", () => {
  const s = stateWith([todo({ text: "day", when: TODAY }), todo({ text: "night", when: TODAY, evening: true }),
    todo({ text: "needs tag", context: "unknown" })],
  { calendar: { status: "ok", events: [{ date: TODAY, start: TODAY + "T09:00:00", end: TODAY + "T09:30:00", subject: "Standup" }] },
    meetings: [{ name: "m", transcription_status: "pending" }] });
  const html = L.renderView(s, { view: "today" }, { today: TODAY, now: TODAY + "T10:00", list: "today" });
  assert.ok(html.includes("Standup") && html.includes("event-past"));
  assert.ok(html.includes("This Evening"));
  assert.ok(html.includes("1 meeting to transcribe") && html.includes('data-action="transcribe"'));
  assert.ok(html.includes("1 to-do from meetings needs a tag"));
});

test("empty lists say something kind instead of rendering nothing", () => {
  const s = stateWith([]);
  for (const v of L.LISTS.filter((x) => x !== "upcoming")) {
    assert.ok(L.renderView(s, { view: v }, { today: TODAY, list: v }).includes('class="empty"'), v);
  }
  // Upcoming always shows the coming week, each day greyed while empty — as Things does
  assert.equal((L.renderView(s, { view: "upcoming" }, { today: TODAY, list: "upcoming" }).match(/day-empty/g) || []).length, 7);
});

test("a pending delete hides the to-do everywhere until Undo expires", () => {
  const t = todo({ text: "gone", when: TODAY });
  const pending = { [L.taskKey(t.file, t.line_text)]: 1 };
  assert.equal(L.listToday(stateWith([t]), TODAY, pending).day.length, 0);
});

test("project pages group to-dos by the note's headings and hide logged items behind a toggle", () => {
  const s = stateWith([
    todo({ text: "task-build", project: "P", heading: "Build" }), todo({ text: "task-design", project: "P", heading: "Design" }),
    todo({ text: "task-top", project: "P", heading: null }), todo({ text: "task-logged", project: "P", done: true }),
  ], { projects: [{ name: "P", status: "active", headings: ["Design", "Build"], open: 3, done: 1, review_overdue: true }] });
  const html = L.renderView(s, { view: "project", name: "P" }, { today: TODAY, list: "project" });
  const order = ["task-top", ">Design<", "task-design", ">Build<", "task-build"].map((x) => html.indexOf(x));
  assert.ok(order.every((i) => i >= 0));
  assert.deepEqual([...order].sort((a, b) => a - b), order);
  assert.ok(html.includes("Show 1 logged item") && !html.includes("task-logged"));
  assert.ok(html.includes("Mark as reviewed"));
  assert.ok(L.renderView(s, { view: "project", name: "P" }, { today: TODAY, list: "project", showLogged: true }).includes("task-logged"));
});

test("the sidebar counts Inbox and Today, badges deadlines, and nests projects under areas", () => {
  const s = stateWith([
    todo({ text: "i", inbox: true }), todo({ text: "due", deadline: TODAY }), todo({ text: "sched", when: TODAY }),
    todo({ text: "w", status: "waiting" }),
  ], { inbox_notes: [{ file: "00 Inbox/n.md", text: "n" }], areas: [{ name: "Work", file: null }],
    projects: [{ name: "Site", area: "Work", status: "active", open: 1, done: 1 }, { name: "Loose", status: "active" },
      { name: "Idea", status: "someday" }] });
  assert.deepEqual(L.sidebarCounts(s, TODAY), { inbox: 2, today: 2, todayDue: 1, waiting: 1 });
  const html = L.sidebarHtml(s, { view: "project", name: "Site" }, TODAY);
  assert.ok(html.indexOf("Loose") < html.indexOf("Work") && html.indexOf("Work") < html.indexOf("Site"));
  assert.ok(!html.includes("Idea"), "someday projects live in Someday, not the sidebar");
  assert.ok(/sb-project current/.test(html) && html.includes("--p:50"));
  assert.ok(html.includes('class="badge">1<'));
});

test("Quick Find matches lists, projects, tags and to-dos, and knows where each lives", () => {
  const s = stateWith([todo({ text: "Call the bank", context: "phone", project: "Money" })],
    { projects: [{ name: "Money", status: "active" }] });
  const r = L.quickFind(s, "mon", TODAY);
  assert.deepEqual(r.map((x) => x.kind + ":" + x.label), ["project:Money", "todo:Call the bank"]);
  assert.deepEqual(r[1].route, { view: "project", name: "Money" });
  assert.deepEqual(L.quickFind(s, "phone", TODAY).map((x) => x.kind), ["tag"]);
  assert.deepEqual(L.quickFind(s, "upc", TODAY)[0].route, { view: "upcoming" });
  assert.equal(L.quickFind(s, "  ", TODAY).length, 0);
  assert.ok(L.quickFindHtml(L.quickFind(s, "<", TODAY), 0) === "");
});

test("the When popover's calendar stars today and won't offer past days", () => {
  const html = L.calendarGrid("2026-09", TODAY, "2026-10-02");
  assert.ok(html.includes("September 2026"));
  assert.ok(!html.includes('data-date="2026-09-28"'));
  assert.ok(/data-date="2026-09-29">.*i-today/.test(html));
  assert.ok(html.includes('cal-day other sel" data-date="2026-10-02"'));
});

test("Move offers the inbox, loose projects, and each area with its projects", () => {
  const s = stateWith([], { areas: [{ name: "Home", file: "20 Areas/Home.md" }, { name: "Work", file: null }],
    projects: [{ name: "Garage", area: "Home" }, { name: "Solo" }] });
  assert.deepEqual(L.moveTargets(s).map((m) => m.kind + ":" + m.name), ["inbox:Inbox", "project:Solo", "area:Home", "project:Garage"]);
  assert.ok(L.movePopoverHtml(s, "gar").includes("Garage") && !L.movePopoverHtml(s, "gar").includes("Solo"));
});

test("keyAction maps shortcuts by physical key, so a Hebrew layout works too", () => {
  const k = (code, key, extra) => L.keyAction(Object.assign({ code, key: key || "" }, extra));
  assert.equal(k("KeyJ", "ח"), "down");
  assert.equal(k("KeyT", "א"), "when:today");
  assert.equal(k("KeyE", "ק"), "when:evening");
  assert.equal(k("KeyS", "ד"), "when:someday");
  assert.equal(k("KeyM", "צ"), "move");
  assert.equal(k("Space", " "), "new");
  assert.equal(k("Digit7", "7"), "list:7");
  assert.equal(k("Slash", "."), "search");
  assert.equal(k("Slash", "?", { shiftKey: true }), "help");
  assert.equal(k("Backspace", "Backspace"), "delete");
  assert.equal(k("KeyJ", "j", { ctrlKey: true }), null);
  assert.equal(k("KeyQ", "q"), null);
});

test("attentionItems covers triage, overdue reviews and meeting follow-ups", () => {
  const s = stateWith([todo({ context: "unknown" })], {
    projects: [{ name: "A", review_overdue: true }, { name: "B", review_overdue: true }],
    meetings: [{ transcription_status: "failed" }, { transcription_status: "done", summary_status: "pending" }],
  });
  const items = L.attentionItems(s, TODAY);
  assert.deepEqual(items.map((a) => a.key), ["triage", "review", "mtg-summarize", "mtg-failed"]);
  assert.equal(items[0].tag, "unknown");
  assert.equal(items[1].text, "2 projects due for review");
});

test("currentEvent picks the timed meeting under way or starting within 10 minutes", () => {
  const cal = { events: [
    { date: TODAY, start: TODAY + "T09:00:00", end: TODAY + "T09:30:00", subject: "early", all_day: false },
    { date: TODAY, start: TODAY + "T10:05:00", end: TODAY + "T11:00:00", subject: "soon", all_day: false },
  ] };
  assert.equal(L.currentEvent(cal, TODAY + "T09:10").subject, "early");
  assert.equal(L.currentEvent(cal, TODAY + "T09:58").subject, "soon");
  assert.equal(L.currentEvent(cal, TODAY + "T12:00"), null);
});

test("recordingUrl encodes a Hebrew title and attendees for the upload", () => {
  const url = L.recordingUrl({ started: "2026-09-29T10:00:00", title: "פגישה", attendees: "Dana" });
  assert.equal(url, "/api/record-meeting?started=2026-09-29T10%3A00%3A00&title=%D7%A4%D7%92%D7%99%D7%A9%D7%94&attendees=Dana");
});

test("localDateTime formats local time without a timezone", () => {
  assert.equal(L.localDateTime(new Date(2026, 8, 29, 7, 5, 9)), "2026-09-29T07:05:09");
});
