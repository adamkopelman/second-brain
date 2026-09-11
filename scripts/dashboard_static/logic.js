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

  function taskKey(file, lineText) {
    return file + "|" + lineText;
  }

  // Obsidian's `path` param wants an absolute filesystem path; a vault-relative one needs `vault` + `file`.
  function obsidianUrl(vaultName, file) {
    return "obsidian://open?vault=" + encodeURIComponent(vaultName || "") + "&file=" + encodeURIComponent(file);
  }

  function filterTasks(tasks, query) {
    if (!query) return tasks;
    var q = query.toLowerCase();
    return tasks.filter(function (t) {
      return (t.text || "").toLowerCase().indexOf(q) !== -1 ||
        (t.project || "").toLowerCase().indexOf(q) !== -1 ||
        (t.context || "").toLowerCase().indexOf(q) !== -1 ||
        (t.links || []).some(function (l) { return l.toLowerCase().indexOf(q) !== -1; });
    });
  }

  function taskLine(t, today, pending) {
    if (pending && pending[taskKey(t.file, t.line_text)]) {
      return '<li class="task-pending"><span class="task-text">Deleted: <s>' + escapeHtml(t.text) + "</s></span>" +
        '<button type="button" class="task-undo" data-file="' + escapeHtml(t.file) + '" data-line="' +
        escapeHtml(t.line_text) + '">Undo</button></li>';
    }
    var due = t.due
      ? '<span class="due' + (isOverdue(t.due, today) ? " overdue" : "") + '">' +
        escapeHtml(t.due) + "</span>"
      : "";
    var proj = t.project
      ? '<span class="proj proj-open" data-name="' + escapeHtml(t.project) + '">' + escapeHtml(t.project) + "</span>"
      : (t.meeting
          ? '<span class="meeting meeting-open" data-file="' + escapeHtml(t.file) + '">' + escapeHtml(t.meeting) + "</span>"
          : "");
    var links = (t.links || []).map(function (l) {
      return '<span class="link-chip">' + escapeHtml(l) + "</span>";
    }).join("");
    return '<li class="task" data-file="' + escapeHtml(t.file) + '" data-line="' +
      escapeHtml(t.line_text) + '">' +
      '<input type="checkbox" class="task-check">' +
      '<span class="task-text">' + escapeHtml(t.text) + links + "</span>" +
      proj + due +
      '<button class="task-delete" title="Delete">×</button>' +
      "</li>";
  }

  function renderTasksByContext(tasksByContext, query, today, pending) {
    var ctxOrder = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"];
    var html = "";
    ctxOrder.forEach(function (ctx) {
      var items = filterTasks(tasksByContext[ctx] || [], query);
      if (!items.length) return;
      html += '<div class="ctx-col"><div class="ctx-h">' + escapeHtml(ctx.slice(1)) +
        ' <span class="ctx-n">' + items.length + '</span></div><ul class="task-list">' +
        items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul></div>";
    });
    return html || '<p class="empty">No tasks.</p>';
  }

  function renderSimpleList(items, today, query, pending) {
    items = filterTasks(items, query);
    if (!items.length) return '<p class="empty">Nothing here.</p>';
    return '<ul class="task-list">' +
      items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>";
  }

  function renderProjects(projects) {
    if (!projects.length) return '<p class="empty">None.</p>';
    return "<ul>" + projects.map(function (p) {
      var pill = p.review_overdue
        ? '<span class="pill overdue">review overdue</span>'
        : (p.review ? '<span class="pill">review ' + escapeHtml(p.review) + "</span>" : "");
      return '<li><a href="#" class="proj-open" data-name="' + escapeHtml(p.name) + '">' +
        escapeHtml(p.name) + "</a>" + pill + "</li>";
    }).join("") + "</ul>";
  }

  // Every open task (any context, plus waiting-for) belonging to one project,
  // deduplicated by (file, line) — used by the project detail overlay.
  function tasksForProject(state, projectName) {
    var seen = {};
    var out = [];
    function addAll(list) {
      (list || []).forEach(function (t) {
        if (t.project !== projectName) return;
        var key = taskKey(t.file, t.line_text);
        if (seen[key]) return;
        seen[key] = true;
        out.push(t);
      });
    }
    Object.keys(state.tasks_by_context || {}).forEach(function (ctx) {
      addAll(state.tasks_by_context[ctx]);
    });
    addAll(state.waiting);
    return out;
  }

  function taskDetailHtml(t, today) {
    var overdue = t.due && isOverdue(t.due, today);
    var sourceLabel = (!t.project && t.meeting) ? "Meeting" : "Project";
    var sourceValue = t.project
      ? '<a href="#" class="proj-open" data-name="' + escapeHtml(t.project) + '">' + escapeHtml(t.project) + "</a>"
      : (t.meeting
          ? '<span class="meeting meeting-open" data-file="' + escapeHtml(t.file) + '">' + escapeHtml(t.meeting) + "</span>"
          : '<span class="empty">none — inbox capture</span>');
    var ctx = (t.context || "#anywhere").replace(/^#/, "");
    var ctxOptions = ["computer", "phone", "errands", "home", "office", "anywhere", "agenda", "unknown"]
      .map(function (c) {
        return '<option value="' + c + '"' + (c === ctx ? " selected" : "") + ">" + c + "</option>";
      }).join("");
    return (
      '<div class="detail-row"><label for="detail-text">Text</label>' +
      '<input type="text" id="detail-text" value="' + escapeHtml(t.text) + '"></div>' +
      '<div class="detail-row"><label for="detail-due">Due date</label>' +
      '<input type="date" id="detail-due" value="' + escapeHtml(t.due || "") + '">' +
      (overdue ? ' <span class="pill overdue">overdue</span>' : "") + "</div>" +
      '<div class="detail-row"><label for="detail-context">Context</label>' +
      '<select id="detail-context">' + ctxOptions + "</select></div>" +
      '<div class="detail-row"><span class="detail-label">' + sourceLabel + '</span><span>' + sourceValue + "</span></div>" +
      '<div class="detail-actions">' +
      '<button type="button" class="detail-save" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Save</button>' +
      '<button type="button" class="detail-mark-done" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Mark done</button>' +
      '<button type="button" class="detail-delete" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">Delete</button>' +
      "</div>"
    );
  }

  function projectDetailHtml(p, relatedTasks, today, vaultName) {
    var pill = p.review_overdue
      ? '<span class="pill overdue">review overdue</span>'
      : (p.review ? '<span class="pill">review ' + escapeHtml(p.review) + "</span>" : "");
    var outcome = p.outcome ? escapeHtml(p.outcome) : '<span class="empty">No outcome set yet.</span>';
    var tasksHtml = relatedTasks.length
      ? '<ul class="task-list">' + relatedTasks.map(function (t) { return taskLine(t, today); }).join("") + "</ul>"
      : '<p class="empty">No open tasks.</p>';
    return (
      '<div class="detail-row"><span class="detail-label">Project</span><span>' +
      escapeHtml(p.name) + pill + "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Outcome</span><span>' + outcome + "</span></div>" +
      '<div class="detail-label" style="margin-top:6px;">Open tasks</div>' + tasksHtml +
      '<div class="detail-actions"><a class="detail-open-link" href="' +
      escapeHtml(obsidianUrl(vaultName, p.file)) + '">Open full note in Obsidian</a></div>'
    );
  }

  function renderNeedsTriage(state, today, pending) {
    var items = (state.tasks_by_context || {})["#unknown"] || [];
    if (!items.length) return '<p class="empty">Nothing to triage.</p>';
    return '<ul class="task-list">' + items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>";
  }

  function renderMeetings(meetings, vaultName) {
    if (!meetings || !meetings.length) return '<p class="empty">No meetings yet.</p>';
    return "<ul>" + meetings.map(function (m) {
      var tPill = m.transcription_status === "done"
        ? '<span class="pill">transcribed</span>'
        : (m.transcription_status === "failed"
            ? '<span class="pill overdue">transcription failed</span>'
            : '<span class="pill overdue">pending transcription</span>');
      var sPill = m.transcription_status === "done"
        ? (m.summary_status === "done"
            ? '<span class="pill">summarized</span>'
            : '<span class="pill overdue">pending summary</span>')
        : "";
      return '<li><a href="' + escapeHtml(obsidianUrl(vaultName, m.file)) + '">' +
        escapeHtml(m.name) + "</a>" + tPill + sPill + "</li>";
    }).join("") + "</ul>";
  }

  function render(state, query, today, pending) {
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
      tasksHtml: renderTasksByContext(state.tasks_by_context || {}, query, today, pending),
      dueSoonHtml: renderSimpleList(state.due_soon || [], today, query, pending),
      waitingHtml: renderSimpleList(state.waiting || [], today, query, pending),
      projectsHtml: renderProjects(state.active_projects || []),
      somedayHtml: renderProjects(state.someday_projects || []),
      needsTriageHtml: renderNeedsTriage(state, today, pending),
      meetingsHtml: renderMeetings(state.meetings || [], state.vault_name),
    };
  }

  var api = {
    escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render,
    taskKey: taskKey, obsidianUrl: obsidianUrl,
    tasksForProject: tasksForProject, taskDetailHtml: taskDetailHtml, projectDetailHtml: projectDetailHtml,
    renderNeedsTriage: renderNeedsTriage, renderMeetings: renderMeetings,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DashboardLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
