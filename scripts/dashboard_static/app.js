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
    var active = document.activeElement;
    if (active && active.classList && active.classList.contains("task-text")) return;
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

  document.addEventListener("click", function (e) {
    var li = e.target.closest(".task");
    if (!li) return;
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    if (e.target.classList.contains("task-check")) {
      post("/api/complete-task", { file: file, line_text: line }).then(refresh).catch(refresh);
    } else if (e.target.classList.contains("task-delete")) {
      post("/api/delete-task", { file: file, line_text: line }).then(refresh).catch(refresh);
    }
  });

  document.addEventListener("focusin", function (e) {
    if (e.target.classList && e.target.classList.contains("task-text")) {
      e.target.dataset.original = e.target.textContent.trim();
    }
  });

  document.addEventListener("focusout", function (e) {
    if (!e.target.classList || !e.target.classList.contains("task-text")) return;
    var newText = e.target.textContent.trim();
    if (!newText || newText === e.target.dataset.original) return;
    var li = e.target.closest(".task");
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    post("/api/edit-task", { file: file, line_text: line, new_text: newText }).then(refresh).catch(refresh);
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
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      modal.classList.add("hidden");
      return;
    }
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    if (e.key === "/") {
      e.preventDefault();
      document.getElementById("search").focus();
    } else if (e.key === "n") {
      e.preventDefault();
      modal.classList.remove("hidden");
      document.getElementById("quick-add-text").focus();
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
      modal.classList.add("hidden");
      refresh();
    }).catch(function () {
      refresh();
    });
  });

  applyTheme(localStorage.getItem("dashboard-theme") || "light");
  refresh();
  setInterval(refresh, POLL_MS);
})();
