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
