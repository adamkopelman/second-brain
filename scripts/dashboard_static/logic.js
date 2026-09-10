// scripts/dashboard_static/logic.js
// Pure rendering/filtering logic for the local dashboard. No DOM, no fetch —
// runs identically under Node's test runner and in the browser.
(function (root) {
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function isOverdue(dateStr, today) {
    if (!dateStr) return false;
    var d = new Date(dateStr + "T00:00:00");
    var t = today ? new Date(today + "T00:00:00") : new Date();
    t.setHours(0, 0, 0, 0);
    return d < t;
  }

  function filterTasks(tasks, query) {
    if (!query) return tasks;
    var q = query.toLowerCase();
    return tasks.filter(function (t) {
      return (t.text || "").toLowerCase().indexOf(q) !== -1 ||
        (t.project || "").toLowerCase().indexOf(q) !== -1 ||
        (t.context || "").toLowerCase().indexOf(q) !== -1;
    });
  }

  function taskLine(t, today) {
    var due = t.due
      ? '<span class="due' + (isOverdue(t.due, today) ? " overdue" : "") + '">' +
        escapeHtml(t.due) + "</span>"
      : "";
    var proj = t.project ? '<span class="proj">' + escapeHtml(t.project) + "</span>" : "";
    return '<li class="task" data-file="' + escapeHtml(t.file) + '" data-line="' +
      escapeHtml(t.line_text) + '">' +
      '<input type="checkbox" class="task-check">' +
      '<span class="task-text" contenteditable="true">' + escapeHtml(t.text) + "</span>" +
      proj + due +
      '<button class="task-delete" title="Delete">×</button>' +
      "</li>";
  }

  function renderTasksByContext(tasksByContext, query, today) {
    var ctxOrder = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"];
    var html = "";
    ctxOrder.forEach(function (ctx) {
      var items = filterTasks(tasksByContext[ctx] || [], query);
      if (!items.length) return;
      html += '<div class="ctx-col"><div class="ctx-h">' + escapeHtml(ctx.slice(1)) +
        " (" + items.length + ')</div><ul class="task-list">' +
        items.map(function (t) { return taskLine(t, today); }).join("") + "</ul></div>";
    });
    return html || '<p class="empty">No tasks.</p>';
  }

  function renderSimpleList(items, today) {
    if (!items.length) return '<p class="empty">Nothing here.</p>';
    return '<ul class="task-list">' +
      items.map(function (t) { return taskLine(t, today); }).join("") + "</ul>";
  }

  function renderProjects(projects) {
    if (!projects.length) return '<p class="empty">None.</p>';
    return "<ul>" + projects.map(function (p) {
      var pill = p.review_overdue
        ? '<span class="pill overdue">review overdue</span>'
        : (p.review ? '<span class="pill">review ' + escapeHtml(p.review) + "</span>" : "");
      return '<li><a href="obsidian://open?path=' + encodeURIComponent(p.file) + '">' +
        escapeHtml(p.name) + "</a>" + pill + "</li>";
    }).join("") + "</ul>";
  }

  function render(state, query, today) {
    var totalTasks = Object.keys(state.tasks_by_context || {}).reduce(function (n, k) {
      return n + state.tasks_by_context[k].length;
    }, 0);
    return {
      kpis: {
        inbox: state.inbox_count,
        tasks: totalTasks,
        waiting: (state.waiting || []).length,
        due: (state.due_soon || []).length,
      },
      tasksHtml: renderTasksByContext(state.tasks_by_context || {}, query, today),
      dueSoonHtml: renderSimpleList(state.due_soon || [], today),
      waitingHtml: renderSimpleList(state.waiting || [], today),
      projectsHtml: renderProjects(state.active_projects || []),
      somedayHtml: renderProjects(state.someday_projects || []),
    };
  }

  var api = { escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DashboardLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
