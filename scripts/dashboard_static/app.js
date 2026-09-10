// scripts/dashboard_static/app.js
(function () {
  var POLL_MS = 4000;
  var state = null;
  var query = "";

  function today() {
    var d = new Date();
    var mm = String(d.getMonth() + 1).padStart(2, "0");
    var dd = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + mm + "-" + dd;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("dashboard-theme", theme);
  }

  function renderAll() {
    if (!state) return;
    var out = DashboardLogic.render(state, query, today());
    document.getElementById("kpis").innerHTML =
      ["inbox", "tasks", "waiting", "due"].map(function (k) {
        return '<div class="kpi"><b>' + out.kpis[k] + "</b><div>" + k + "</div></div>";
      }).join("");
    document.getElementById("tasks").innerHTML = out.tasksHtml;
    document.getElementById("due-soon").innerHTML = out.dueSoonHtml;
    document.getElementById("waiting").innerHTML = out.waitingHtml;
    document.getElementById("projects").innerHTML = out.projectsHtml;
    document.getElementById("someday").innerHTML = out.somedayHtml;
  }

  function refresh() {
    fetch("/api/state").then(function (r) { return r.json(); }).then(function (data) {
      state = data;
      renderAll();
    });
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error("request failed: " + r.status);
      return r.json();
    });
  }

  function findTaskInState(file, line) {
    var ctxKeys = Object.keys(state.tasks_by_context || {});
    for (var i = 0; i < ctxKeys.length; i++) {
      var arr = state.tasks_by_context[ctxKeys[i]];
      for (var j = 0; j < arr.length; j++) {
        if (arr[j].file === file && arr[j].line_text === line) return arr[j];
      }
    }
    var lists = [state.waiting, state.due_soon];
    for (var l = 0; l < lists.length; l++) {
      for (var k = 0; k < lists[l].length; k++) {
        if (lists[l][k].file === file && lists[l][k].line_text === line) return lists[l][k];
      }
    }
    return null;
  }

  var detailModal = document.getElementById("detail-modal");
  var detailTitle = document.getElementById("detail-title");
  var detailBody = document.getElementById("detail-body");

  function openDetailModal(title, bodyHtml) {
    detailTitle.textContent = title;
    detailBody.innerHTML = bodyHtml;
    detailModal.classList.remove("hidden");
  }

  function closeDetailModal() {
    detailModal.classList.add("hidden");
  }

  function openTaskDetail(file, line) {
    var t = findTaskInState(file, line);
    if (!t) return;
    openDetailModal("Task", DashboardLogic.taskDetailHtml(t, today()));
  }

  function openProjectDetail(name) {
    var all = (state.active_projects || []).concat(state.someday_projects || []);
    var p = all.filter(function (x) { return x.name === name; })[0];
    if (!p) return;
    var related = DashboardLogic.tasksForProject(state, name);
    openDetailModal("Project", DashboardLogic.projectDetailHtml(p, related, today()));
  }

  document.getElementById("detail-modal-close").addEventListener("click", closeDetailModal);
  detailModal.addEventListener("click", function (e) {
    if (e.target === detailModal) closeDetailModal();
  });

  document.addEventListener("click", function (e) {
    var projTrigger = e.target.closest(".proj-open");
    if (projTrigger) {
      e.preventDefault();
      openProjectDetail(projTrigger.getAttribute("data-name"));
      return;
    }

    var saveBtn = e.target.closest(".detail-save");
    if (saveBtn) {
      var newText = document.getElementById("detail-text").value.trim();
      var newDue = document.getElementById("detail-due").value;
      var editBody = { file: saveBtn.getAttribute("data-file"), line_text: saveBtn.getAttribute("data-line"), new_text: newText };
      if (newDue) editBody.new_due = newDue;
      post("/api/edit-task", editBody).then(function () { closeDetailModal(); refresh(); })
        .catch(function () { closeDetailModal(); refresh(); });
      return;
    }
    var doneBtn = e.target.closest(".detail-mark-done");
    if (doneBtn) {
      post("/api/complete-task", { file: doneBtn.getAttribute("data-file"), line_text: doneBtn.getAttribute("data-line") })
        .then(function () { closeDetailModal(); refresh(); }).catch(function () { closeDetailModal(); refresh(); });
      return;
    }
    var detailDelBtn = e.target.closest(".detail-delete");
    if (detailDelBtn) {
      post("/api/delete-task", { file: detailDelBtn.getAttribute("data-file"), line_text: detailDelBtn.getAttribute("data-line") })
        .then(function () { closeDetailModal(); refresh(); }).catch(function () { closeDetailModal(); refresh(); });
      return;
    }

    var li = e.target.closest(".task");
    if (!li) return;
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    if (e.target.classList.contains("task-check")) {
      post("/api/complete-task", { file: file, line_text: line }).then(refresh).catch(refresh);
    } else if (e.target.classList.contains("task-delete")) {
      post("/api/delete-task", { file: file, line_text: line }).then(refresh).catch(refresh);
    } else {
      openTaskDetail(file, line);
    }
  });

  document.getElementById("search").addEventListener("input", function (e) {
    query = e.target.value;
    renderAll();
  });

  document.getElementById("theme-toggle").addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "light" ? "dark" : "light");
  });

  var modal = document.getElementById("quick-add");

  function openQuickAdd() {
    modal.classList.remove("hidden");
    document.getElementById("quick-add-text").focus();
  }

  function closeQuickAdd() {
    modal.classList.add("hidden");
  }

  document.getElementById("new-task-btn").addEventListener("click", openQuickAdd);
  document.getElementById("quick-add-close").addEventListener("click", closeQuickAdd);
  modal.addEventListener("click", function (e) {
    if (e.target === modal) closeQuickAdd(); // click on the backdrop, not the form
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeQuickAdd();
      closeDetailModal();
      return;
    }
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    if (e.key === "/") {
      e.preventDefault();
      document.getElementById("search").focus();
    } else if (e.key === "n") {
      e.preventDefault();
      openQuickAdd();
    }
  });

  document.getElementById("quick-add-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var text = document.getElementById("quick-add-text").value.trim();
    if (!text) return;
    var context = document.getElementById("quick-add-context").value;
    var project = document.getElementById("quick-add-project").value.trim() || undefined;
    post("/api/new-task", { text: text, context: context, project: project }).then(function () {
      document.getElementById("quick-add-text").value = "";
      document.getElementById("quick-add-project").value = "";
      closeQuickAdd();
      refresh();
    }).catch(function () {
      refresh();
    });
  });

  applyTheme(localStorage.getItem("dashboard-theme") || "light");
  refresh();
  setInterval(refresh, POLL_MS);
})();
