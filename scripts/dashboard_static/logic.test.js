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
