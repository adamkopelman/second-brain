// scripts/dashboard_static/logic.js
// Pure rendering/filtering logic for the local dashboard. No DOM, no fetch —
// runs identically under Node's test runner and in the browser.
(function (root) {
  var PAGES = ["today", "tasks", "waiting", "projects", "meetings"];
  var PAGE_LABELS = { today: "Today", tasks: "Tasks", waiting: "Waiting", projects: "Projects", meetings: "Meetings" };
  var CTX_ORDER = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda"];
  var WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

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

  function isoDate(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function addDays(iso, n) {
    var d = new Date(iso + "T00:00:00");
    d.setDate(d.getDate() + n);
    return isoDate(d);
  }

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  // Friendly due text: "today", "tomorrow", a weekday within the next 6 days, otherwise the ISO date
  // (past dates stay ISO so an overdue item always shows exactly when it was due).
  function dueLabel(due, today) {
    if (!due || !ISO_DATE.test(due)) return due || "";
    today = today || isoDate(new Date());
    if (due < today) return due;
    if (due === today) return "today";
    if (due === addDays(today, 1)) return "tomorrow";
    if (due <= addDays(today, 6)) return WEEKDAYS[new Date(due + "T00:00:00").getDay()];
    return due;
  }

  // Splits the due-soon list (overdue + next 7 days) into the Today page's three groups.
  function bucketDue(items, today) {
    var out = { overdue: [], today: [], week: [] };
    (items || []).forEach(function (t) {
      if (!t.due) return;
      if (t.due < today) out.overdue.push(t);
      else if (t.due === today) out.today.push(t);
      else out.week.push(t);
    });
    function byDue(a, b) { return a.due < b.due ? -1 : (a.due > b.due ? 1 : 0); }
    out.overdue.sort(byDue); out.today.sort(byDue); out.week.sort(byDue);
    return out;
  }

  function meetingStatus(m) {
    if (m.transcription_status === "failed") return "failed";
    if (m.transcription_status && m.transcription_status !== "done") return "transcribe";
    if (m.transcription_status === "done" && m.summary_status !== "done") return "summarize";
    return null;
  }

  // What the Today page lists besides due tasks. `alert` items need doing; the rest are reminders.
  // Each item carries `page` (a tab to jump to) or `project` (opens its detail), or neither.
  function attentionItems(state, today) {
    var items = [];
    var inbox = state.inbox_count || 0;
    if (inbox) {
      items.push({ key: "inbox", alert: true, text: plural(inbox, "inbox item") + " to process",
        hint: "run /gtd-process-inbox" });
    }
    var triage = ((state.tasks_by_context || {})["#unknown"] || []).length;
    if (triage) {
      items.push({ key: "triage", alert: true, page: "tasks",
        text: plural(triage, "task") + " from meetings need" + (triage === 1 ? "s" : "") + " a context" });
    }
    var weekEnd = addDays(today, 7);
    (state.active_projects || []).forEach(function (p) {
      if (p.review_overdue) {
        items.push({ key: "review|" + p.name, alert: true, project: p.name, text: p.name + ": review overdue" });
      } else if (p.review && ISO_DATE.test(p.review) && p.review <= weekEnd) {
        items.push({ key: "review|" + p.name, alert: false, project: p.name,
          text: p.name + ": review due " + dueLabel(p.review, today) });
      }
    });
    var counts = { failed: 0, transcribe: 0, summarize: 0 };
    (state.meetings || []).forEach(function (m) {
      var s = meetingStatus(m);
      if (s) counts[s]++;
    });
    if (counts.failed) items.push({ key: "mtg-failed", alert: true, page: "meetings", text: plural(counts.failed, "meeting") + " failed to transcribe" });
    if (counts.transcribe) items.push({ key: "mtg-transcribe", alert: true, page: "meetings", text: plural(counts.transcribe, "meeting") + " to transcribe" });
    if (counts.summarize) items.push({ key: "mtg-summarize", alert: true, page: "meetings", text: plural(counts.summarize, "meeting") + " to summarize" });

    var waiting = (state.waiting || []).length;
    if (waiting) items.push({ key: "waiting", alert: false, page: "waiting", text: plural(waiting, "waiting-for item") + " to follow up" });

    var dueKeys = {};
    (state.due_soon || []).forEach(function (t) { dueKeys[taskKey(t.file, t.line_text)] = true; });
    var perCtx = [];
    var others = 0;
    CTX_ORDER.forEach(function (ctx) {
      var n = ((state.tasks_by_context || {})[ctx] || []).filter(function (t) {
        return !dueKeys[taskKey(t.file, t.line_text)];
      }).length;
      if (n) { others += n; perCtx.push(ctx.slice(1) + " " + n); }
    });
    if (others) {
      items.push({ key: "next", alert: false, page: "tasks",
        text: plural(others, "other next action") + " — " + perCtx.join(" · ") });
    }
    return items;
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

  // Every row that j/k can land on is a `.nav-item` with a stable `data-key`, so the keyboard
  // selection survives the 4-second re-render.
  function taskLine(t, today, pending) {
    var key = escapeHtml(taskKey(t.file, t.line_text));
    var loc = 'data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '"';
    if (pending && pending[taskKey(t.file, t.line_text)]) {
      return '<li class="task-pending nav-item" data-key="' + key + '" ' + loc + '>' +
        '<span class="task-text">Deleted: <s>' + escapeHtml(t.text) + "</s></span>" +
        '<button type="button" class="task-undo" ' + loc + ">Undo</button></li>";
    }
    var due = t.due
      ? '<span class="due' + (isOverdue(t.due, today) ? " overdue" : "") + '" title="' + escapeHtml(t.due) + '">' +
        escapeHtml(dueLabel(t.due, today)) + "</span>"
      : "";
    var proj = t.project
      ? '<span class="proj proj-open" data-name="' + escapeHtml(t.project) + '">' + escapeHtml(t.project) + "</span>"
      : (t.meeting
          ? '<span class="meeting meeting-open" data-file="' + escapeHtml(t.file) + '">' + escapeHtml(t.meeting) + "</span>"
          : "");
    var links = (t.links || []).map(function (l) {
      return '<span class="link-chip">' + escapeHtml(l) + "</span>";
    }).join("");
    return '<li class="task nav-item" data-key="' + key + '" ' + loc + ">" +
      '<input type="checkbox" class="task-check">' +
      '<span class="task-text" dir="auto">' + escapeHtml(t.text) + links + "</span>" +
      proj + due +
      '<button class="task-delete" title="Delete">×</button>' +
      "</li>";
  }

  function renderTasksByContext(tasksByContext, query, today, pending) {
    var html = "";
    CTX_ORDER.forEach(function (ctx) {
      var items = filterTasks(tasksByContext[ctx] || [], query);
      if (!items.length) return;
      html += '<div class="ctx-col"><div class="ctx-h">' + escapeHtml(ctx.slice(1)) +
        ' <span class="ctx-n">' + items.length + '</span></div><ul class="task-list">' +
        items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul></div>";
    });
    return html || '<p class="empty">No tasks.</p>';
  }

  function renderSimpleList(items, today, query, pending, emptyText) {
    items = filterTasks(items, query);
    if (!items.length) return '<p class="empty">' + escapeHtml(emptyText || "Nothing here.") + "</p>";
    return '<ul class="task-list">' +
      items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>";
  }

  function filterByName(items, query) {
    if (!query) return items;
    var q = query.toLowerCase();
    return items.filter(function (x) { return (x.name || "").toLowerCase().indexOf(q) !== -1; });
  }

  function renderProjects(projects) {
    if (!projects.length) return '<p class="empty">None.</p>';
    return "<ul>" + projects.map(function (p) {
      var pill = p.review_overdue
        ? '<span class="pill overdue">review overdue</span>'
        : (p.review ? '<span class="pill">review ' + escapeHtml(p.review) + "</span>" : "");
      return '<li class="nav-item" data-key="' + escapeHtml("proj|" + p.name) + '">' +
        '<a href="#" class="proj-open" data-name="' + escapeHtml(p.name) + '">' +
        escapeHtml(p.name) + "</a>" + pill + "</li>";
    }).join("") + "</ul>";
  }

  function section(title, bodyHtml, cls) {
    return '<section class="section' + (cls ? " " + cls : "") + '"><h2 class="section-h">' + title + "</h2>" + bodyHtml + "</section>";
  }

  function renderTasksPage(state, query, today, pending) {
    var triage = filterTasks((state.tasks_by_context || {})["#unknown"] || [], query);
    var html = "";
    if (triage.length) {
      html += section("Needs triage <span class=\"section-note\">open a task and pick a context</span>",
        renderNeedsTriage({ tasks_by_context: { "#unknown": triage } }, today, pending), "section-attn");
    }
    return html + '<div class="ctx-grid">' + renderTasksByContext(state.tasks_by_context || {}, query, today, pending) + "</div>";
  }

  function renderProjectsPage(state, query) {
    return section("Active", renderProjects(filterByName(state.active_projects || [], query))) +
      section("Someday / Maybe", renderProjects(filterByName(state.someday_projects || [], query)));
  }

  function renderAttention(items) {
    return '<ul class="att-list">' + items.map(function (a) {
      var text = escapeHtml(a.text);
      var body = a.project
        ? '<a href="#" class="proj-open" data-name="' + escapeHtml(a.project) + '">' + text + "</a>"
        : (a.page ? '<a href="#' + a.page + '">' + text + "</a>" : "<span>" + text + "</span>");
      var hint = a.hint ? ' <span class="att-hint">' + escapeHtml(a.hint) + "</span>" : "";
      var navAttrs = (a.project || a.page) ? ' nav-item" data-key="' + escapeHtml("att|" + a.key) + '"' : '"';
      return '<li class="att' + (a.alert ? " att-alert" : "") + navAttrs + ">" + body + hint + "</li>";
    }).join("") + "</ul>";
  }

  function renderToday(state, query, today, pending) {
    var b = bucketDue(filterTasks(state.due_soon || [], query), today);
    var att = attentionItems(state, today);
    var alerts = att.filter(function (a) { return a.alert; });
    var reminders = att.filter(function (a) { return !a.alert; });
    function list(items) {
      return '<ul class="task-list">' + items.map(function (t) { return taskLine(t, today, pending); }).join("") + "</ul>";
    }
    var html = "";
    if (b.overdue.length) html += section("Overdue", list(b.overdue), "section-alert");
    if (b.today.length) html += section("Due today", list(b.today));
    if (b.week.length) html += section("This week", list(b.week));
    if (!html) {
      html = '<p class="empty today-clear">' + (query ? "No due tasks match your search." : "Nothing due this week.") + "</p>";
    }
    if (alerts.length) html += section("Needs attention", renderAttention(alerts));
    if (reminders.length) html += section("On your lists", renderAttention(reminders));
    return html;
  }

  // Per-tab counts (respecting the search query) and whether the tab should show a red dot.
  function tabInfo(state, query, today) {
    var ctxs = state.tasks_by_context || {};
    var dueSoon = filterTasks(state.due_soon || [], query);
    var b = bucketDue(dueSoon, today);
    var taskCount = CTX_ORDER.concat(["#unknown"]).reduce(function (n, ctx) {
      return n + filterTasks(ctxs[ctx] || [], query).length;
    }, 0);
    var anyTaskOverdue = Object.keys(ctxs).some(function (ctx) {
      return ctxs[ctx].some(function (t) { return t.due && isOverdue(t.due, today); });
    });
    var att = attentionItems(state, today);
    return {
      today: { count: dueSoon.length, alert: b.overdue.length > 0 || att.some(function (a) { return a.alert; }) },
      tasks: { count: taskCount, alert: anyTaskOverdue || (ctxs["#unknown"] || []).length > 0 },
      waiting: { count: filterTasks(state.waiting || [], query).length, alert: false },
      projects: {
        count: filterByName(state.active_projects || [], query).length + filterByName(state.someday_projects || [], query).length,
        alert: (state.active_projects || []).some(function (p) { return p.review_overdue; }),
      },
      meetings: {
        count: filterByName(state.meetings || [], query).length,
        alert: (state.meetings || []).some(function (m) { return meetingStatus(m) !== null; }),
      },
    };
  }

  function renderTabs(info, current) {
    return PAGES.map(function (p, i) {
      var t = info[p] || { count: 0, alert: false };
      return '<a href="#' + p + '" class="tab' + (p === current ? " current" : "") + '"' +
        (p === current ? ' aria-current="page"' : "") + ">" +
        "<kbd>" + (i + 1) + "</kbd>" + PAGE_LABELS[p] +
        ' <span class="tab-n">' + t.count + "</span>" +
        (t.alert ? '<span class="dot" title="needs attention"></span>' : "") + "</a>";
    }).join("");
  }

  var SHORTCUTS = [
    ["1 – 5", "Switch page"], ["j / ↓", "Next item"], ["k / ↑", "Previous item"],
    ["Enter", "Open the selected item"], ["x", "Complete the selected task"],
    ["d", "Delete the selected task (5 s to undo)"], ["u", "Undo the last delete"],
    ["/", "Search"], ["n", "New task"], ["Esc", "Close / leave search"], ["?", "Show this list"],
  ];

  function shortcutsHtml() {
    return '<table class="shortcuts">' + SHORTCUTS.map(function (s) {
      return "<tr><td><kbd>" + escapeHtml(s[0]) + "</kbd></td><td>" + escapeHtml(s[1]) + "</td></tr>";
    }).join("") + "</table>";
  }

  function filterBannerHtml(query) {
    if (!query) return "";
    return 'Showing matches for “<b dir="auto">' + escapeHtml(query) + '</b>” · ' +
      '<button type="button" class="filter-clear">Clear</button> or press <kbd>Esc</kbd>';
  }

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
      '<input type="text" id="detail-text" value="' + escapeHtml(t.text) + '" dir="auto"></div>' +
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
      // no status at all = a note written by hand, with no recording to transcribe
      var tPill = !m.transcription_status ? ""
        : m.transcription_status === "done"
          ? '<span class="pill">transcribed</span>'
          : (m.transcription_status === "failed"
              ? '<span class="pill overdue">transcription failed</span>'
              : '<span class="pill overdue">pending transcription</span>');
      var sPill = m.transcription_status === "done"
        ? (m.summary_status === "done"
            ? '<span class="pill">summarized</span>'
            : '<span class="pill overdue">pending summary</span>')
        : "";
      return '<li class="nav-item" data-key="' + escapeHtml("mtg|" + m.file) + '">' +
        '<a href="' + escapeHtml(obsidianUrl(vaultName, m.file)) + '">' +
        escapeHtml(m.name) + "</a>" + tPill + sPill + "</li>";
    }).join("") + "</ul>";
  }

  // One HTML string per page plus the tab-bar data; the search query filters every page.
  function render(state, query, today, pending) {
    var meetings = filterByName(state.meetings || [], query);
    return {
      tabs: tabInfo(state, query, today),
      todayHtml: renderToday(state, query, today, pending),
      tasksHtml: renderTasksPage(state, query, today, pending),
      waitingHtml: renderSimpleList(state.waiting || [], today, query, pending, "Not waiting on anything."),
      projectsHtml: renderProjectsPage(state, query),
      meetingsHtml: query && !meetings.length ? '<p class="empty">No meetings match your search.</p>'
        : renderMeetings(meetings, state.vault_name),
    };
  }

  var api = {
    PAGES: PAGES,
    escapeHtml: escapeHtml, isOverdue: isOverdue, filterTasks: filterTasks, render: render,
    taskKey: taskKey, obsidianUrl: obsidianUrl, dueLabel: dueLabel, bucketDue: bucketDue,
    attentionItems: attentionItems, tabInfo: tabInfo, renderTabs: renderTabs, shortcutsHtml: shortcutsHtml,
    keyAction: keyAction, filterBannerHtml: filterBannerHtml,
    tasksForProject: tasksForProject, taskDetailHtml: taskDetailHtml, projectDetailHtml: projectDetailHtml,
    renderNeedsTriage: renderNeedsTriage, renderMeetings: renderMeetings,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DashboardLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
