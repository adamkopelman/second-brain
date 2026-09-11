// scripts/dashboard_static/logic.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("./logic.js");

test("escapeHtml escapes the five XSS-relevant characters", () => {
  assert.equal(L.escapeHtml(`<a href="x">&'</a>`),
    "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
});

test("escapeHtml handles null/undefined safely", () => {
  assert.equal(L.escapeHtml(null), "");
  assert.equal(L.escapeHtml(undefined), "");
});

test("isOverdue is true only for a date strictly before today", () => {
  assert.equal(L.isOverdue("2026-09-01", "2026-09-10"), true);
  assert.equal(L.isOverdue("2026-09-10", "2026-09-10"), false);
  assert.equal(L.isOverdue("2026-09-11", "2026-09-10"), false);
  assert.equal(L.isOverdue(null, "2026-09-10"), false);
});

test("filterTasks matches text, project, or context case-insensitively", () => {
  const tasks = [
    { text: "Finalize homepage wireframe", project: "Website Redesign", context: "#computer" },
    { text: "Call hosting provider", project: "Website Redesign", context: "#phone" },
    { text: "Order flight", project: "Plan Family Trip", context: "#anywhere" },
  ];
  assert.equal(L.filterTasks(tasks, "").length, 3);
  assert.equal(L.filterTasks(tasks, "flight").length, 1);
  assert.equal(L.filterTasks(tasks, "WEBSITE").length, 2);
  assert.equal(L.filterTasks(tasks, "phone").length, 1);
});

test("render produces per-tab counts for a populated state", () => {
  const state = {
    inbox_count: 2,
    tasks_by_context: {
      "#computer": [{ text: "Finalize homepage wireframe", file: "f.md",
        line_text: "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]",
        project: "Website Redesign", due: "2026-09-12" }],
      "#phone": [{ text: "Call hosting provider", file: "f.md",
        line_text: "- [ ] Call hosting provider #next #phone", project: "Website Redesign" }],
    },
    waiting: [{ text: "Logo files", file: "f.md", line_text: "- [ ] Logo files #waiting" }],
    due_soon: [{ text: "Finalize homepage wireframe", file: "f.md",
      line_text: "- [ ] Finalize homepage wireframe #next #computer [due:: 2026-09-12]",
      due: "2026-09-12" }],
    active_projects: [{ name: "Website Redesign", file: "10 Projects/Website Redesign.md",
      review: "2026-09-15", review_overdue: false }],
    someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  const counts = Object.fromEntries(Object.entries(out.tabs).map(([k, v]) => [k, v.count]));
  assert.deepEqual(counts, { today: 1, week: 1, tasks: 2, inbox: 0, waiting: 1, projects: 1 });
  assert.match(out.tasksHtml, /Finalize homepage wireframe/);
  assert.match(out.projectsHtml, /Website Redesign/);
  assert.match(out.projectsHtml, /Someday \/ Maybe<\/h2><p class="empty">None\.<\/p>/);
});

test("render escapes task text (no raw HTML injection)", () => {
  const state = {
    inbox_count: 0,
    tasks_by_context: { "#computer": [{ text: '<img src=x onerror=alert(1)>', file: "f.md",
      line_text: "x", project: null }] },
    waiting: [], due_soon: [], active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.doesNotMatch(out.tasksHtml, /<img/);
  assert.match(out.tasksHtml, /&lt;img/);
});

test("render respects the search query across sections", () => {
  const state = {
    inbox_count: 0,
    tasks_by_context: {
      "#computer": [{ text: "Finalize homepage wireframe", file: "f.md", line_text: "x",
        project: "Website Redesign" }],
      "#phone": [{ text: "Call hosting provider", file: "f.md", line_text: "y",
        project: "Website Redesign" }],
    },
    waiting: [], due_soon: [], active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "hosting", "2026-09-10");
  assert.doesNotMatch(out.tasksHtml, /Finalize/);
  assert.match(out.tasksHtml, /Call hosting provider/);
});

test("render marks an overdue due date distinctly from a future one", () => {
  const state = {
    inbox_count: 0, tasks_by_context: {}, waiting: [],
    due_soon: [
      { text: "Late one", file: "f.md", line_text: "x", due: "2026-09-01" },
      { text: "On time", file: "f.md", line_text: "y", due: "2026-09-14" },
    ],
    active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.match(out.todayHtml, /class="due overdue" title="2026-09-01">2026-09-01</);
  assert.match(out.todayHtml, /class="due" title="2026-09-14">Mon</);
});

test("tasksForProject collects a project's tasks from every context plus waiting, deduplicated", () => {
  const state = {
    tasks_by_context: {
      "#computer": [
        { text: "A", file: "f.md", line_text: "a", project: "Website Redesign" },
        { text: "B", file: "f.md", line_text: "b", project: "Plan Family Trip" },
      ],
      "#phone": [
        { text: "A", file: "f.md", line_text: "a", project: "Website Redesign" }, // duplicate of A
        { text: "C", file: "f.md", line_text: "c", project: "Website Redesign" },
      ],
    },
    waiting: [{ text: "D", file: "f.md", line_text: "d", project: "Website Redesign" }],
  };
  const out = L.tasksForProject(state, "Website Redesign");
  assert.equal(out.length, 3); // A, C, D — B excluded (different project), A not duplicated
  assert.deepEqual(out.map((t) => t.text).sort(), ["A", "C", "D"]);
});

test("taskDetailHtml renders editable text/due fields and escapes content", () => {
  const t = { text: '<b>x</b>', file: "f.md", line_text: "- [ ] <b>x</b> #next #computer [due:: 2026-09-01]",
    project: "Website Redesign", context: "#computer", due: "2026-09-01" };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, /id="detail-text" value="&lt;b&gt;x&lt;\/b&gt;"/);
  assert.match(html, /id="detail-due" value="2026-09-01"/);
  assert.match(html, /class="pill overdue">overdue/); // 2026-09-01 is before 2026-09-10
  assert.match(html, /class="detail-save"/);
  assert.match(html, /class="detail-mark-done"/);
  assert.match(html, /class="detail-delete"/);
  assert.match(html, /proj-open" data-name="Website Redesign"/);
});

test("taskDetailHtml shows 'none' for an inbox task with no project", () => {
  const t = { text: "x", file: "00 Inbox/a.md", line_text: "- [ ] x", project: null, context: null, due: null };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, /none — inbox capture/);
  assert.doesNotMatch(html, /class="pill overdue"/);
});

test("projectDetailHtml shows outcome, review pill, and its open tasks", () => {
  const p = { name: "Website Redesign", file: "10 Projects/Website Redesign.md",
    review: "2026-09-15", review_overdue: false, outcome: "Ship the new site." };
  const tasks = [{ text: "Finalize wireframe", file: "f.md", line_text: "x", project: "Website Redesign" }];
  const html = L.projectDetailHtml(p, tasks, "2026-09-10");
  assert.match(html, /Ship the new site\./);
  assert.match(html, /Finalize wireframe/);
  assert.doesNotMatch(html, /No outcome set yet/);
  assert.match(html, /Open full note in Obsidian/);
});

test("projectDetailHtml shows placeholders for a project with no outcome and no open tasks", () => {
  const p = { name: "Learn Spanish", file: "10 Projects/Learn Spanish.md", review: null, review_overdue: false, outcome: null };
  const html = L.projectDetailHtml(p, [], "2026-09-10");
  assert.match(html, /No outcome set yet\./);
  assert.match(html, /No open tasks\./);
});

test("taskDetailHtml renders a context select with the task's context selected", () => {
  const t = { text: "x", file: "f.md", line_text: "x", project: "P", context: "#phone", due: null };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, /<select id="detail-context">/);
  assert.match(html, /<option value="phone" selected>phone<\/option>/);
  assert.match(html, /<option value="unknown">unknown<\/option>/);
});

test("taskDetailHtml shows a meeting pill and 'Meeting' label for a task with no project but a meeting", () => {
  const t = { text: "Email the vendor", file: "Meetings/2026-09-10 Sync.md", line_text: "x",
    project: null, meeting: "2026-09-10 Sync", context: "#unknown", due: null };
  const html = L.taskDetailHtml(t, "2026-09-10");
  assert.match(html, />Meeting<\/span>/);
  assert.match(html, /meeting-open" data-file="Meetings\/2026-09-10 Sync\.md"/);
  assert.doesNotMatch(html, /none — inbox capture/);
});

test("taskLine shows a meeting pill when the task has no project but has a meeting", () => {
  // #unknown tasks live only in the Needs-triage card (renderTasksByContext's ctxOrder excludes
  // "#unknown" by design — see the renderNeedsTriage tests below), so this exercises taskLine's
  // meeting-pill behavior through a normal, already-triaged context instead.
  const t = { text: "Email the vendor", file: "Meetings/2026-09-10 Sync.md",
    line_text: "- [ ] Email the vendor #next #computer", project: null, meeting: "2026-09-10 Sync" };
  const html = L.render(
    { inbox_count: 0, tasks_by_context: { "#computer": [t] }, waiting: [], due_soon: [],
      active_projects: [], someday_projects: [] },
    "", "2026-09-10"
  ).tasksHtml;
  assert.match(html, /meeting-open" data-file="Meetings\/2026-09-10 Sync\.md"/);
});

test("renderNeedsTriage lists every #unknown-context task", () => {
  const state = { tasks_by_context: { "#unknown": [
    { text: "Email the vendor", file: "Meetings/x.md", line_text: "x", project: null, meeting: "Sync" },
  ] } };
  const html = L.renderNeedsTriage(state, "2026-09-10");
  assert.match(html, /Email the vendor/);
  assert.match(html, /meeting-open" data-file="Meetings\/x\.md"/);
});

test("renderNeedsTriage shows an empty state when nothing needs triage", () => {
  const html = L.renderNeedsTriage({ tasks_by_context: {} }, "2026-09-10");
  assert.equal(html, '<p class="empty">Nothing to triage.</p>');
});


test("obsidianUrl addresses a note by vault name and vault-relative path", () => {
  assert.equal(L.obsidianUrl("second brain", "Meetings/2026-09-10 Sync.md"),
    "obsidian://open?vault=second%20brain&file=Meetings%2F2026-09-10%20Sync.md");
});

test("projectDetailHtml links to the note by vault name, not a relative path", () => {
  const p = { name: "Website Redesign", file: "10 Projects/Website Redesign.md", review: null, outcome: null };
  const html = L.projectDetailHtml(p, [], "2026-09-10", "second-brain");
  assert.match(html, /href="obsidian:\/\/open\?vault=second-brain&amp;file=10%20Projects%2FWebsite%20Redesign\.md"/);
});

test("taskLine shows a chip for each linked note, e.g. the person you're waiting on", () => {
  const out = L.render({ inbox_count: 0, tasks_by_context: {}, due_soon: [], active_projects: [], someday_projects: [],
    waiting: [{ text: "Logo files", file: "f.md", line_text: "x", project: "Website Redesign", links: ["Design <Agency>"] }] },
    "", "2026-09-10");
  assert.match(out.waitingHtml, /class="link-chip">Design &lt;Agency&gt;</);
});

test("render shows an Undo row in place of a task whose delete is pending", () => {
  const t = { text: "Call hosting provider", file: "f.md", line_text: "- [ ] Call hosting provider #next #phone", project: "P" };
  const state = { inbox_count: 0, tasks_by_context: { "#phone": [t] }, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [] };
  const pending = {};
  pending[L.taskKey(t.file, t.line_text)] = true;
  const out = L.render(state, "", "2026-09-10", pending);
  assert.match(out.tasksHtml, /class="task-undo"/);
  assert.doesNotMatch(out.tasksHtml, /class="task-check"/);
});

test("search also filters Waiting and the Today page, matching linked names", () => {
  const state = { inbox_count: 0, tasks_by_context: {}, active_projects: [], someday_projects: [],
    waiting: [
      { text: "Logo files", file: "f.md", line_text: "a", links: ["Design Agency"] },
      { text: "Figures", file: "f.md", line_text: "b", links: ["Sam Rivera"] },
    ],
    due_soon: [{ text: "Pay invoice", file: "f.md", line_text: "c", due: "2026-09-12" }],
  };
  const out = L.render(state, "agency", "2026-09-10");
  assert.match(out.waitingHtml, /Logo files/);
  assert.doesNotMatch(out.waitingHtml, /Figures/);
  assert.doesNotMatch(out.todayHtml, /Pay invoice/);
  assert.match(out.todayHtml, /No due tasks match your search/);
  assert.equal(out.tabs.waiting.count, 1);
  assert.equal(out.tabs.today.count, 0);
});



test("render omits the Needs-triage section when nothing needs triage", () => {
  const state = {
    inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.doesNotMatch(out.tasksHtml, /Needs triage/);
});

test("the Tasks page puts #unknown tasks in a Needs-triage section above the contexts", () => {
  const state = { inbox_count: 0, waiting: [], due_soon: [], active_projects: [], someday_projects: [],
    tasks_by_context: {
      "#unknown": [{ text: "Email the vendor", file: "Meetings/x.md", line_text: "u", meeting: "Sync" }],
      "#phone": [{ text: "Call Sam", file: "f.md", line_text: "p" }],
    } };
  const html = L.render(state, "", "2026-09-10").tasksHtml;
  assert.ok(html.indexOf("Needs triage") < html.indexOf("Call Sam"));
  assert.match(html, /Email the vendor/);
});

test("dueLabel says today/tomorrow/weekday inside a week, and the ISO date otherwise", () => {
  const today = "2026-09-11"; // a Friday
  assert.equal(L.dueLabel("2026-09-11", today), "today");
  assert.equal(L.dueLabel("2026-09-12", today), "tomorrow");
  assert.equal(L.dueLabel("2026-09-14", today), "Mon");
  assert.equal(L.dueLabel("2026-09-17", today), "Thu");
  assert.equal(L.dueLabel("2026-09-18", today), "2026-09-18"); // a week out: weekday would be ambiguous
  assert.equal(L.dueLabel("2026-09-01", today), "2026-09-01"); // overdue keeps its date
  assert.equal(L.dueLabel("someday", today), "someday");        // unparseable text passes through
  assert.equal(L.dueLabel(null, today), "");
});

test("bucketDue splits due-soon tasks into overdue, today and this week, each sorted by date", () => {
  const b = L.bucketDue([
    { text: "c", due: "2026-09-15" }, { text: "a", due: "2026-09-02" }, { text: "t", due: "2026-09-11" },
    { text: "b", due: "2026-09-12" }, { text: "z", due: "2026-09-01" },
  ], "2026-09-11");
  assert.deepEqual(b.overdue.map((t) => t.text), ["z", "a"]);
  assert.deepEqual(b.today.map((t) => t.text), ["t"]);
  assert.deepEqual(b.week.map((t) => t.text), ["b", "c"]);
});

test("attentionItems covers inbox, triage, reviews, meetings, waiting and undated next actions", () => {
  const due = { text: "Wireframe", file: "f.md", line_text: "w", due: "2026-09-12" };
  const state = {
    inbox_count: 2,
    tasks_by_context: {
      "#computer": [due, { text: "Email", file: "f.md", line_text: "e" }],
      "#phone": [{ text: "Call", file: "f.md", line_text: "c" }],
      "#unknown": [{ text: "?", file: "m.md", line_text: "u" }],
    },
    due_soon: [due],
    waiting: [{ text: "Logo", file: "f.md", line_text: "l" }],
    active_projects: [
      { name: "Trip", review: "2026-09-01", review_overdue: true },
      { name: "Site", review: "2026-09-15", review_overdue: false },
      { name: "Later", review: "2026-10-30", review_overdue: false },
    ],
    meetings: [
      { name: "A", transcription_status: "pending" },
      { name: "B", transcription_status: "done", summary_status: "pending" },
      { name: "C", transcription_status: "done", summary_status: "done" },
      { name: "D", transcription_status: null },
    ],
  };
  const items = L.attentionItems(state, "2026-09-11");
  const byKey = Object.fromEntries(items.map((a) => [a.key, a]));
  assert.equal(byKey.inbox.text, "2 inbox items to process");
  assert.equal(byKey.inbox.page, "inbox");
  assert.equal(byKey["mtg-transcribe"].action, "transcribe");
  assert.match(byKey["mtg-summarize"].hint, /gtd-summarize-meetings/);
  assert.equal(byKey.triage.page, "tasks");
  assert.equal(byKey["review|Trip"].alert, true);
  assert.equal(byKey["review|Site"].text, "Site: review due Tue");
  assert.equal(byKey["review|Site"].alert, false);
  assert.equal(byKey["review|Later"], undefined);
  assert.equal(byKey["mtg-transcribe"].text, "1 meeting to transcribe");
  assert.equal(byKey["mtg-summarize"].text, "1 meeting to summarize");
  assert.equal(byKey["mtg-failed"], undefined);
  assert.equal(byKey.waiting.page, "waiting");
  // the due task is already on the Today page, so only the two undated ones count here
  assert.equal(byKey.next.text, "2 other next actions — computer 1 · phone 1");
});

test("the Today page shows only non-empty groups and says so when nothing is due", () => {
  const empty = { inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [], active_projects: [], someday_projects: [] };
  const html = L.render(empty, "", "2026-09-11").todayHtml;
  assert.match(html, /Nothing due this week\./);
  assert.doesNotMatch(html, /Overdue|Due today|This week<|Needs attention|On your lists/);

  const busy = { ...empty, inbox_count: 1,
    due_soon: [{ text: "Pay rent", file: "f.md", line_text: "r", due: "2026-09-11" }] };
  const html2 = L.render(busy, "", "2026-09-11").todayHtml;
  assert.match(html2, /Due today<\/h2>.*Pay rent/);
  assert.doesNotMatch(html2, /Overdue|This week</);
  assert.match(html2, /Needs attention<\/h2>.*1 inbox item to process/);
});

test("tabInfo flags overdue work, triage and overdue reviews", () => {
  const state = { inbox_count: 0, waiting: [], someday_projects: [],
    tasks_by_context: { "#home": [{ text: "Fix tap", file: "f.md", line_text: "t", due: "2026-09-01" }] },
    due_soon: [{ text: "Fix tap", file: "f.md", line_text: "t", due: "2026-09-01" }],
    active_projects: [{ name: "Trip", review_overdue: true }],
    meetings: [{ name: "A", transcription_status: "failed" }] };
  const info = L.tabInfo(state, "", "2026-09-11");
  assert.equal(info.today.alert, true);
  assert.equal(info.tasks.alert, true);
  assert.equal(info.waiting.alert, false);
  assert.equal(info.projects.alert, true);
});

test("renderTabs numbers the pages, marks the current one and shows alert dots", () => {
  const info = { today: { count: 1, alert: true }, tasks: { count: 3, alert: false },
    waiting: { count: 0, alert: false }, projects: { count: 2, alert: false }, inbox: { count: 0, alert: false },
    week: { count: 0, alert: false } };
  const html = L.renderTabs(info, "tasks");
  assert.match(html, /href="#today" class="tab"><kbd>1<\/kbd>Today <span class="tab-n">1<\/span><span class="dot"/);
  assert.match(html, /href="#tasks" class="tab current" aria-current="page"><kbd>3<\/kbd>Tasks/);
  assert.equal((html.match(/class="dot"/g) || []).length, 1);
});

test("every navigable row carries a stable data-key", () => {
  const t = { text: "Call", file: "f.md", line_text: "- [ ] Call #next #phone" };
  const state = { inbox_count: 0, waiting: [], due_soon: [], someday_projects: [],
    tasks_by_context: { "#phone": [t] }, active_projects: [{ name: "Site" }],
    inbox_items: [{ file: "00 Inbox/a.md", text: "Idea", captured: "2026-09-11" }] };
  const out = L.render(state, "", "2026-09-11");
  assert.match(out.tasksHtml, /class="task nav-item" data-key="f\.md\|- \[ \] Call #next #phone"/);
  assert.match(out.projectsHtml, /class="nav-item" data-key="proj\|Site"/);
  assert.match(out.inboxHtml, /class="nav-item" data-key="inbox\|00 Inbox\/a\.md"/);
});

test("search filters projects and inbox items", () => {
  const state = { inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [{ name: "Website Redesign" }, { name: "Plan Family Trip" }],
    someday_projects: [{ name: "Learn Spanish" }],
    inbox_items: [{ file: "00 Inbox/a.md", text: "Buy trip insurance" }, { file: "00 Inbox/b.md", text: "Idea" }] };
  const out = L.render(state, "trip", "2026-09-11");
  assert.match(out.projectsHtml, /Plan Family Trip/);
  assert.doesNotMatch(out.projectsHtml, /Website Redesign|Learn Spanish/);
  assert.match(out.inboxHtml, /Buy trip insurance/);
  assert.doesNotMatch(out.inboxHtml, /Idea/);
  assert.equal(out.tabs.inbox.count, 1);
  assert.equal(out.tabs.projects.count, 1);
});

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

test("filterBannerHtml explains an active filter and how to clear it, escaping the query", () => {
  assert.equal(L.filterBannerHtml(""), "");
  const html = L.filterBannerHtml("<b>דוח</b>");
  assert.match(html, /Showing matches for/);
  assert.match(html, /&lt;b&gt;דוח&lt;\/b&gt;/);
  assert.match(html, /class="filter-clear"/);
  assert.match(html, /<kbd>Esc<\/kbd>/);
});

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
  // an indented full-width section above the columns (Needs triage) is not a column of its own
  const withTriage = [{ left: 13, right: 600, top: -40, bottom: -20 }, r(0, 0), r(320, 0)];
  assert.equal(L.pickHorizontal(withTriage, 1, 1), 2);
  assert.equal(L.pickHorizontal(withTriage, 2, -1), 1);
  assert.equal(L.pickHorizontal(withTriage, 0, 1), 2);
});

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
