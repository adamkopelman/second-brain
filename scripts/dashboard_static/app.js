// scripts/dashboard_static/app.js
(function () {
  var POLL_MS = 4000;
  var UNDO_MS = 5000;
  var PAGES = DashboardLogic.PAGES;
  var state = null;
  var query = "";
  var page = pageFromHash();
  var pendingDeletes = {}; // taskKey -> timeout id; the file is only touched once the undo window closes
  var deleteOrder = [];    // [{file, line}] oldest first, so `u` undoes the most recent delete
  var sel = { key: null, index: -1 }; // keyboard selection on the current page; -1 = none
  var transcribing = null; // null | "running" | "failed" — shown on Today's transcribe item

  function today() {
    var d = new Date();
    var mm = String(d.getMonth() + 1).padStart(2, "0");
    var dd = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + mm + "-" + dd;
  }

  function pageFromHash() {
    var h = location.hash.replace(/^#/, "");
    return PAGES.indexOf(h) >= 0 ? h : "today";
  }

  function showPage(p) {
    page = p;
    sel = { key: null, index: -1 };
    renderAll();
    window.scrollTo(0, 0);
  }

  // Switch synchronously (hashchange fires later, which would drop a j/k typed right after the
  // number key); the hash still updates so reload and Back keep you on the page.
  function goTo(p) {
    if (p === page) return;
    showPage(p);
    location.hash = p;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("dashboard-theme", theme);
  }

  // Rows scroll clear of the sticky header (see .nav-item scroll-margin in style.css).
  function syncTopbarHeight() {
    document.documentElement.style.setProperty("--topbar-h", document.querySelector(".topbar").offsetHeight + "px");
  }

  function renderAll() {
    if (!state) return;
    var out = DashboardLogic.render(state, query, today(), pendingDeletes, DashboardLogic.localDateTime(new Date()).slice(0, 16));
    document.getElementById("tabs").innerHTML = DashboardLogic.renderTabs(out.tabs, page);
    document.getElementById("today").innerHTML = out.todayHtml;
    document.getElementById("week").innerHTML = out.weekHtml;
    document.getElementById("tasks").innerHTML = out.tasksHtml;
    document.getElementById("waiting").innerHTML = out.waitingHtml;
    document.getElementById("projects").innerHTML = out.projectsHtml;
    document.getElementById("inbox").innerHTML = out.inboxHtml;
    PAGES.forEach(function (p) {
      document.getElementById("page-" + p).hidden = p !== page;
    });
    var banner = document.getElementById("filter-banner");
    banner.innerHTML = DashboardLogic.filterBannerHtml(query);
    banner.hidden = !query;
    var run = transcribing && document.querySelector('.att-run[data-action="transcribe"]');
    if (run) run.textContent = transcribing === "running" ? "Transcribing…" : "Transcription failed — Enter to retry";
    restoreSelection();
  }

  function setQuery(q) {
    query = q;
    searchEl.value = q;
    renderAll();
  }

  // ---- keyboard selection ----

  function navItems() {
    return Array.prototype.slice.call(document.querySelectorAll("#page-" + page + " .nav-item"));
  }

  function select(i, scroll) {
    var items = navItems();
    items.forEach(function (el) { el.classList.remove("selected"); });
    if (!items.length || i < 0) { sel = { key: null, index: -1 }; return; }
    i = Math.min(i, items.length - 1);
    var el = items[i];
    el.classList.add("selected");
    sel = { key: el.getAttribute("data-key"), index: i };
    if (scroll) {
      // the first row means "top of the page": show the section titles above it too
      if (i === 0) window.scrollTo(0, 0);
      else el.scrollIntoView({ block: "nearest" });
    }
  }

  // After a re-render, keep the same row selected; if it's gone (completed, deleted elsewhere),
  // land on whatever now sits at its old position.
  function restoreSelection() {
    if (sel.index < 0) return;
    var keys = navItems().map(function (el) { return el.getAttribute("data-key"); });
    var i = keys.indexOf(sel.key);
    select(i >= 0 ? i : sel.index, false);
  }

  function selectedEl() {
    return sel.index < 0 ? null : navItems()[sel.index] || null;
  }

  function move(delta) {
    var items = navItems();
    if (!items.length) return false;
    select(sel.index < 0 ? (delta > 0 ? 0 : items.length - 1) : Math.max(0, sel.index + delta), true);
    return true;
  }

  function moveHorizontal(dir) {
    var items = navItems();
    if (!items.length) return false;
    if (sel.index < 0) { select(0, true); return true; }
    var rects = items.map(function (el) { return el.getBoundingClientRect(); });
    var i = DashboardLogic.pickHorizontal(rects, sel.index, dir);
    if (i >= 0) select(i, true);
    return true;
  }

  function activate(el) {
    if (el.classList.contains("task-pending")) {
      undoDelete(el.getAttribute("data-file"), el.getAttribute("data-line"));
    } else if (el.classList.contains("task")) {
      openTaskDetail(el.getAttribute("data-file"), el.getAttribute("data-line"));
    } else {
      var target = el.querySelector(".proj-open, a[href]");
      if (target) target.click();
    }
  }

  // ---- data ----

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

  function completeTask(file, line) {
    post("/api/complete-task", { file: file, line_text: line }).then(refresh).catch(refresh);
  }

  function forgetDelete(key) {
    delete pendingDeletes[key];
    deleteOrder = deleteOrder.filter(function (d) { return DashboardLogic.taskKey(d.file, d.line) !== key; });
  }

  function scheduleDelete(file, line) {
    var key = DashboardLogic.taskKey(file, line);
    if (pendingDeletes[key]) return;
    deleteOrder.push({ file: file, line: line });
    pendingDeletes[key] = setTimeout(function () {
      post("/api/delete-task", { file: file, line_text: line })
        .then(function () { forgetDelete(key); refresh(); })
        .catch(function () { forgetDelete(key); refresh(); });
    }, UNDO_MS);
    renderAll();
  }

  function undoDelete(file, line) {
    var key = DashboardLogic.taskKey(file, line);
    clearTimeout(pendingDeletes[key]);
    forgetDelete(key);
    renderAll();
  }

  function undoLastDelete() {
    var last = deleteOrder[deleteOrder.length - 1];
    if (last) undoDelete(last.file, last.line);
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

  // ---- modals ----

  var detailModal = document.getElementById("detail-modal");
  var detailTitle = document.getElementById("detail-title");
  var detailBody = document.getElementById("detail-body");
  var modal = document.getElementById("quick-add");

  function anyModalOpen() {
    return !detailModal.classList.contains("hidden") || !modal.classList.contains("hidden");
  }

  function openDetailModal(title, bodyHtml) {
    detailTitle.textContent = title;
    detailBody.innerHTML = bodyHtml;
    detailModal.classList.remove("hidden");
    // put keyboard focus inside the overlay: the task's text field, or the close button
    // (never a task checkbox in a project's list, where Space would complete it)
    var first = detailBody.querySelector("#detail-text") || document.getElementById("detail-modal-close");
    first.focus();
  }

  // hand focus back to the page so j/k work straight away after closing
  function hideModal(m) {
    m.classList.add("hidden");
    if (m.contains(document.activeElement)) document.activeElement.blur();
  }

  function closeDetailModal() {
    hideModal(detailModal);
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
    openDetailModal("Project", DashboardLogic.projectDetailHtml(p, related, today(), state.vault_name));
  }

  function openHelp() {
    openDetailModal("Keyboard shortcuts", DashboardLogic.shortcutsHtml());
  }

  function openQuickAdd() {
    modal.classList.remove("hidden");
    document.getElementById("quick-add-text").focus();
  }

  function closeQuickAdd() {
    hideModal(modal);
  }

  document.getElementById("detail-modal-close").addEventListener("click", closeDetailModal);
  detailModal.addEventListener("click", function (e) {
    if (e.target === detailModal) closeDetailModal();
  });
  document.getElementById("new-task-btn").addEventListener("click", openQuickAdd);
  document.getElementById("help-btn").addEventListener("click", openHelp);
  document.getElementById("quick-add-close").addEventListener("click", closeQuickAdd);
  modal.addEventListener("click", function (e) {
    if (e.target === modal) closeQuickAdd(); // click on the backdrop, not the form
  });

  // ---- clicks ----

  document.addEventListener("click", function (e) {
    if (e.target.closest(".filter-clear")) { setQuery(""); return; }

    var runLink = e.target.closest(".att-run");
    if (runLink) {
      e.preventDefault();
      if (runLink.getAttribute("data-action") === "transcribe" && transcribing !== "running") {
        transcribing = "running";
        renderAll();
        post("/api/transcribe", {})
          .then(function () { transcribing = null; }, function () { transcribing = "failed"; })
          .then(refresh);
      }
      return;
    }

    var projTrigger = e.target.closest(".proj-open");
    if (projTrigger) {
      e.preventDefault();
      openProjectDetail(projTrigger.getAttribute("data-name"));
      return;
    }

    var meetingTrigger = e.target.closest(".meeting-open");
    if (meetingTrigger) {
      e.preventDefault();
      var meetingFile = meetingTrigger.getAttribute("data-file");
      if (meetingFile) window.open(DashboardLogic.obsidianUrl(state.vault_name, meetingFile));
      return;
    }

    var undoBtn = e.target.closest(".task-undo");
    if (undoBtn) {
      undoDelete(undoBtn.getAttribute("data-file"), undoBtn.getAttribute("data-line"));
      return;
    }

    var saveBtn = e.target.closest(".detail-save");
    if (saveBtn) {
      var newText = document.getElementById("detail-text").value.trim();
      var newDue = document.getElementById("detail-due").value;
      var ctxEl = document.getElementById("detail-context");
      var editBody = { file: saveBtn.getAttribute("data-file"), line_text: saveBtn.getAttribute("data-line"), new_text: newText };
      if (newDue) editBody.new_due = newDue;
      if (ctxEl) editBody.new_context = ctxEl.value;
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
      closeDetailModal();
      scheduleDelete(detailDelBtn.getAttribute("data-file"), detailDelBtn.getAttribute("data-line"));
      return;
    }

    // clicking a row on the page also makes it the keyboard selection
    var navEl = e.target.closest("#page-" + page + " .nav-item");
    if (navEl) select(navItems().indexOf(navEl), false);

    var li = e.target.closest(".task");
    if (!li) return;
    var file = li.getAttribute("data-file");
    var line = li.getAttribute("data-line");
    if (e.target.classList.contains("task-check")) {
      completeTask(file, line);
    } else if (e.target.classList.contains("task-delete")) {
      scheduleDelete(file, line);
    } else {
      openTaskDetail(file, line);
    }
  });

  // ---- keyboard ----

  var searchEl = document.getElementById("search");

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (anyModalOpen()) { closeQuickAdd(); closeDetailModal(); return; }
      // Esc in the box, or anywhere while a filter is active, clears the search
      if (e.target === searchEl) searchEl.blur();
      if (query) setQuery("");
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target.tagName || "").toLowerCase();

    // Enter in the search box drops you onto the first result, ready for j/k
    if (e.target === searchEl) {
      if (e.key === "Enter" || e.key === "ArrowDown") {
        e.preventDefault();
        searchEl.blur();
        select(0, true);
      }
      return;
    }
    // Enter in a task's detail fields saves it
    if (e.key === "Enter" && tag === "input" && detailBody.contains(e.target)) {
      var save = detailBody.querySelector(".detail-save");
      if (save) { e.preventDefault(); save.click(); }
      return;
    }
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    if (anyModalOpen()) return;
    // a focused button/link handles its own Enter/Space
    if ((e.key === "Enter" || e.key === " ") && (tag === "button" || tag === "a")) return;

    var action = DashboardLogic.keyAction(e);
    if (action && runAction(action)) e.preventDefault();
  });

  // Returns true when the key was used, so the browser's default (scrolling, typing) is skipped.
  function runAction(action) {
    var el = selectedEl();
    var isTask = el && el.classList.contains("task");
    if (action.indexOf("page:") === 0) {
      var n = parseInt(action.slice(5), 10);
      if (n > PAGES.length) return false;
      goTo(PAGES[n - 1]);
      return true;
    }
    switch (action) {
      case "down": return move(1);
      case "up": return move(-1);
      case "left": return moveHorizontal(-1);
      case "right": return moveHorizontal(1);
      case "open":
        if (!el) return false;
        activate(el);
        return true;
      case "complete":
        if (isTask) completeTask(el.getAttribute("data-file"), el.getAttribute("data-line"));
        return true;
      case "delete":
        if (isTask) scheduleDelete(el.getAttribute("data-file"), el.getAttribute("data-line"));
        return true;
      case "undo": undoLastDelete(); return true;
      case "search": searchEl.focus(); return true;
      case "new": openQuickAdd(); return true;
      case "help": openHelp(); return true;
    }
    return false;
  }

  // tab clicks, attention links and Back/Forward arrive here
  window.addEventListener("hashchange", function () {
    var p = pageFromHash();
    if (p !== page) showPage(p);
  });

  searchEl.addEventListener("input", function () {
    query = searchEl.value;
    renderAll();
  });

  document.getElementById("theme-toggle").addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "light" ? "dark" : "light");
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

  syncTopbarHeight();
  window.addEventListener("resize", syncTopbarHeight);
  applyTheme(localStorage.getItem("dashboard-theme") || "light");
  refresh();
  setInterval(refresh, POLL_MS);
})();
