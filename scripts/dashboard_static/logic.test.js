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

test("render produces correct KPI counts for a populated state", () => {
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
  assert.deepEqual(out.kpis, { inbox: 2, tasks: 2, waiting: 1, due: 1 });
  assert.match(out.tasksHtml, /Finalize homepage wireframe/);
  assert.match(out.projectsHtml, /Website Redesign/);
  assert.equal(out.somedayHtml, '<p class="empty">None.</p>');
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
  assert.match(out.dueSoonHtml, /class="due overdue"/);
  assert.match(out.dueSoonHtml, /class="due">/);
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

test("renderMeetings lists meetings with status pills and an Obsidian link", () => {
  const meetings = [
    { name: "2026-09-10 Sync", file: "Meetings/2026-09-10 Sync.md", date: "2026-09-10",
      transcription_status: "done", summary_status: "pending" },
    { name: "2026-09-09 Standup", file: "Meetings/2026-09-09 Standup.md", date: "2026-09-09",
      transcription_status: "pending", summary_status: "pending" },
  ];
  const html = L.renderMeetings(meetings, "second brain");
  assert.match(html, /2026-09-10 Sync/);
  assert.match(html, /pending summary/);
  assert.match(html, /pending transcription/);
  assert.match(html, /obsidian:\/\/open\?vault=second%20brain&amp;file=Meetings%2F2026-09-10%20Sync\.md/);
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

test("search also filters Waiting and Due soon, matching linked names", () => {
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
  assert.doesNotMatch(out.dueSoonHtml, /Pay invoice/);
});

test("renderMeetings shows no transcription pill for a hand-written note with no recording", () => {
  const html = L.renderMeetings([{ name: "2026-09-08 Kickoff", file: "Meetings/2026-09-08 Kickoff.md",
    date: "2026-09-08", transcription_status: null, summary_status: null }], "v");
  assert.match(html, /2026-09-08 Kickoff/);
  assert.doesNotMatch(html, /class="pill/);
});

test("renderMeetings shows an empty state with no meetings", () => {
  assert.equal(L.renderMeetings([]), '<p class="empty">No meetings yet.</p>');
});

test("render includes needsTriageHtml and meetingsHtml", () => {
  const state = {
    inbox_count: 0, tasks_by_context: {}, waiting: [], due_soon: [],
    active_projects: [], someday_projects: [],
    meetings: [{ name: "Sync", file: "Meetings/Sync.md", date: "2026-09-10",
      transcription_status: "done", summary_status: "done" }],
  };
  const out = L.render(state, "", "2026-09-10");
  assert.match(out.needsTriageHtml, /Nothing to triage/);
  assert.match(out.meetingsHtml, /Sync/);
});
