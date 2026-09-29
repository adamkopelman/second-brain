// scripts/dashboard_static/app.js — the page's behaviour; what to draw comes from logic.js.
(function () {
  var L = DashboardLogic;
  var POLL_MS = 4000;
  var UNDO_MS = 5000;
  var CHECK_MS = 900; // a ticked box lingers this long (and can be unticked) before it's logged

  var state = null;
  var route = L.parseRoute(location.hash);
  var sel = { key: null, index: -1 };
  var expanded = null;   // taskKey of the open to-do card, or "new" while creating one
  var draft = null;      // the open card's title as typed, until it's saved
  var creating = null;   // the new to-do's fields while its card is open
  var tagFilter = null;
  var showLogged = false;
  var pending = {};      // taskKey -> timer: deleted, but the file is only touched once Undo expires
  var deleteOrder = [];  // [{key, file, line, text}] oldest first
  var checking = {};     // taskKey -> timer: ticked, about to be completed
  var transcribing = null;
  var pop = null;        // open popover: {kind, target, month}

  var touchOnly = !!(window.matchMedia && matchMedia("(hover: none)").matches);

  var $ = function (id) { return document.getElementById(id); };
  var viewEl = $("view"), navEl = $("sb-nav"), popEl = $("popover"), toastEl = $("toast");

  function today() { return L.isoDate(new Date()); }
  function nowMinute() { return L.localDateTime(new Date()).slice(0, 16); }

  // ---- storage (a private window may refuse it; the page works the same without) ----

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { /* ignore */ }
    return null;
  }

  // Follows the system until you pick one with the ◐ button; only a pick is remembered.
  function applyTheme(theme, remember) {
    document.documentElement.setAttribute("data-theme", theme);
    if (remember) store("dashboard-theme", theme);
  }

  // ---- rendering ----

  function viewOpts() {
    return {
      today: today(), now: nowMinute(), pending: pending, checking: checking, expanded: expanded,
      draft: draft, creating: expanded === "new" ? creating : null, tag: tagFilter, showLogged: showLogged,
      list: route.view,
    };
  }

  // A native date picker or <select> closes if its element is redrawn, so wait until it's done.
  function busyInput() {
    var a = document.activeElement;
    return a && viewEl.contains(a) && (a.tagName === "SELECT" || a.type === "date");
  }

  function renderAll() {
    if (!state) return;
    if (expanded && expanded !== "new" && !findByKey(expanded)) { expanded = null; draft = null; }
    navEl.innerHTML = L.sidebarHtml(state, route, today());
    document.title = L.viewTitle(route) + " · Second Brain";
    if (busyInput()) return;
    var focus = document.activeElement && document.activeElement.classList.contains("card-title");
    var caret = focus ? document.activeElement.selectionStart : null;
    viewEl.innerHTML = L.renderView(state, route, viewOpts());
    var run = document.querySelector('.att[data-action="transcribe"] .att-text');
    if (run && transcribing) run.textContent = transcribing === "running" ? "Transcribing…" : "Transcription failed — Enter to retry";
    if (focus) {
      var t = viewEl.querySelector(".card-title");
      if (t) { t.focus(); t.setSelectionRange(caret, caret); }
    }
    // the open to-do left this list (given a new When, say): it's closed, and its title was saved
    if (expanded && !viewEl.querySelector(".todo-card")) { expanded = null; draft = null; }
    restoreSelection();
    syncBar();
  }

  function findByKey(key) {
    var i = key.indexOf("|");
    return L.findTodo(state, key.slice(0, i), key.slice(i + 1));
  }

  // ---- routes ----

  function navigate(r) {
    closeCard();
    closePop();
    $("finder").hidden = true;
    document.querySelector(".app").classList.remove("nav-open");
    if (!L.sameRoute(r, route)) {
      route = r;
      tagFilter = null;
      showLogged = false;
      sel = { key: null, index: -1 };
      var h = L.routeHash(r);
      if (location.hash !== h) history.pushState(null, "", h);
      $("scroll").scrollTop = 0;
    }
    renderAll();
  }

  window.addEventListener("hashchange", function () { navigate(L.parseRoute(location.hash)); });
  window.addEventListener("popstate", function () { navigate(L.parseRoute(location.hash)); });

  // ---- selection ----

  function navItems() {
    return Array.prototype.slice.call(viewEl.querySelectorAll(".nav-item"));
  }

  function select(i, scroll) {
    var items = navItems();
    items.forEach(function (el) { el.classList.remove("selected"); });
    if (!items.length || i < 0) { sel = { key: null, index: -1 }; syncBar(); return; }
    i = Math.min(i, items.length - 1);
    var el = items[i];
    el.classList.add("selected");
    sel = { key: el.getAttribute("data-key"), index: i };
    if (scroll) el.scrollIntoView({ block: "nearest" });
    syncBar();
  }

  function selectKey(key, scroll) {
    var keys = navItems().map(function (el) { return el.getAttribute("data-key"); });
    if (keys.indexOf(key) >= 0) select(keys.indexOf(key), scroll);
  }

  // After a redraw keep the same row selected; if it left the list, land where it was.
  function restoreSelection() {
    if (sel.index < 0) return;
    var keys = navItems().map(function (el) { return el.getAttribute("data-key"); });
    var i = keys.indexOf(sel.key);
    select(i >= 0 ? i : sel.index, false);
  }

  function selectedEl() {
    return sel.index < 0 ? null : navItems()[sel.index] || null;
  }

  function selectedTodo() {
    var el = selectedEl();
    if (!el || !el.classList.contains("todo") || el.hasAttribute("data-new")) return null;
    return L.findTodo(state, el.getAttribute("data-file"), el.getAttribute("data-line"));
  }

  // the to-do an action applies to: the open card's, else the selected row's
  function targetTodo() {
    if (expanded === "new") return { isNew: true };
    if (expanded) return findByKey(expanded);
    return selectedTodo();
  }

  function move(delta) {
    var items = navItems();
    if (!items.length) return;
    select(sel.index < 0 ? (delta > 0 ? 0 : items.length - 1) : Math.max(0, Math.min(items.length - 1, sel.index + delta)), true);
  }

  function syncBar() {
    var t = expanded || (selectedEl() && selectedEl().classList.contains("todo"));
    $("when-btn").disabled = !t;
    $("move-btn").disabled = !t;
  }

  // ---- server ----

  var lastRaw = null, lastMinute = null;

  function refresh() {
    return fetch("/api/state").then(function (r) { return r.text(); }).then(function (raw) {
      var minute = nowMinute();
      if (raw === lastRaw && minute === lastMinute) return;
      lastRaw = raw;
      lastMinute = minute;
      state = JSON.parse(raw);
      renderAll();
    }).catch(function () { /* server restarting; the next poll catches up */ });
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || "request failed: " + r.status);
        return data;
      });
    });
  }

  function fail(err) {
    showToast("Couldn't save — " + (err && err.message ? err.message : "the note changed; try again"));
    refresh();
  }

  // Edit a to-do; the open card and the selection follow it to its new line text.
  function edit(t, fields) {
    var oldKey = L.taskKey(t.file, t.line_text);
    var body = { file: t.file, line_text: t.line_text };
    Object.keys(fields).forEach(function (k) { body[k] = fields[k]; });
    // a title typed into the open card rides along, in case this edit moves it off the list
    if (expanded === oldKey && draft != null && draft.trim() && draft.trim() !== t.text && !body.new_text) {
      body.new_text = draft.trim();
      draft = null;
    }
    return post("/api/edit-task", body).then(function (res) {
      var newKey = L.taskKey(t.file, res.line_text);
      if (expanded === oldKey) expanded = newKey;
      if (sel.key === oldKey) sel.key = newKey;
      return refresh();
    }).catch(fail);
  }

  // ---- the open to-do card ----

  function openCard(t) {
    closePop();
    commitCard();
    expanded = L.taskKey(t.file, t.line_text);
    draft = null;
    renderAll();
    selectKey(expanded, true);
    focusTitle();
  }

  function focusTitle() {
    var input = viewEl.querySelector(".card-title");
    if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
  }

  // Save the open card's title (Things saves as you close), then close it.
  function commitCard() {
    if (!expanded) return;
    if (expanded === "new") {
      var text = (draft || "").trim();
      var c = creating;
      expanded = null; draft = null; creating = null;
      if (text) createTodo(text, c);
      return;
    }
    var t = findByKey(expanded);
    var text2 = draft;
    expanded = null; draft = null;
    if (t && text2 != null && text2.trim() && text2.trim() !== t.text) edit(t, { new_text: text2.trim() });
  }

  function closeCard() {
    var key = expanded;
    if (!key) return;
    commitCard();
    renderAll();
    if (key !== "new") selectKey(key, false);
    if (document.activeElement && viewEl.contains(document.activeElement)) document.activeElement.blur();
  }

  function startCreate() {
    closePop();
    commitCard();
    creating = L.newTodoDefaults(route, today(), tagFilter);
    expanded = "new";
    draft = "";
    sel = { key: null, index: -1 };
    renderAll();
    $("scroll").scrollTop = 0;
    focusTitle();
  }

  function createTodo(text, c) {
    var body = { text: text, context: c.context || "anywhere", project: c.project, area: c.area, deadline: c.deadline, status: c.status };
    if (c.when) body.when = c.when;
    post("/api/new-task", body).then(function (res) {
      sel = { key: L.taskKey(res.file, res.line_text), index: 0 };
      return refresh();
    }).catch(fail);
  }

  // ---- complete / delete ----

  function toggleCheck(file, line) {
    var t = L.findTodo(state, file, line);
    if (!t) return;
    var key = L.taskKey(file, line);
    if (t.done) {
      post("/api/uncomplete-task", { file: file, line_text: line }).then(refresh).catch(fail);
      return;
    }
    if (checking[key]) {
      clearTimeout(checking[key]);
      delete checking[key];
    } else {
      if (expanded === key) commitCard();
      checking[key] = setTimeout(function () {
        post("/api/complete-task", { file: file, line_text: line })
          .then(function () { delete checking[key]; return refresh(); })
          .catch(function (e) { delete checking[key]; fail(e); });
      }, CHECK_MS);
    }
    renderAll();
  }

  function scheduleDelete(t) {
    var key = L.taskKey(t.file, t.line_text);
    if (pending[key]) return;
    if (expanded === key) { expanded = null; draft = null; }
    deleteOrder.push({ key: key, file: t.file, line: t.line_text, text: t.text });
    pending[key] = setTimeout(function () {
      post("/api/delete-task", { file: t.file, line_text: t.line_text })
        .then(function () { forgetDelete(key); return refresh(); })
        .catch(function (e) { forgetDelete(key); fail(e); });
    }, UNDO_MS);
    renderAll();
    showUndo();
  }

  function forgetDelete(key) {
    delete pending[key];
    deleteOrder = deleteOrder.filter(function (d) { return d.key !== key; });
    showUndo();
  }

  function undoDelete() {
    var last = deleteOrder[deleteOrder.length - 1];
    if (!last) return;
    clearTimeout(pending[last.key]);
    forgetDelete(last.key);
    renderAll();
    selectKey(last.key, true);
  }

  // ---- toast ----

  var toastTimer = null;

  function showToast(html) {
    toastEl.innerHTML = "<span>" + L.escapeHtml(html) + "</span>";
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.hidden = true; }, 4000);
  }

  function showUndo() {
    var last = deleteOrder[deleteOrder.length - 1];
    clearTimeout(toastTimer);
    if (!last) { toastEl.hidden = true; return; }
    toastEl.innerHTML = '<span dir="auto">Deleted “' + L.escapeHtml(last.text) + '”</span><button type="button" id="undo-btn">Undo</button>';
    toastEl.hidden = false;
  }

  // ---- When / Move ----

  function setWhen(value) {
    var t = targetTodo();
    if (!t) return;
    closePop();
    if (t.isNew) {
      if (value === "someday") { creating.status = "someday"; creating.when = null; }
      else {
        if (creating.status === "someday") creating.status = "next";
        creating.when = value === "anytime" ? null : value;
      }
      renderAll();
      focusTitle();
      return;
    }
    edit(t, { new_when: value });
  }

  function moveTo(kind, name) {
    var t = targetTodo();
    if (!t) return;
    closePop();
    if (t.isNew) {
      creating.project = kind === "project" ? name : null;
      creating.area = kind === "area" ? name : null;
      renderAll();
      focusTitle();
      return;
    }
    var oldKey = L.taskKey(t.file, t.line_text);
    var body = { file: t.file, line_text: t.line_text };
    if (kind === "project") body.project = name;
    if (kind === "area") body.area = name;
    post("/api/move-task", body).then(function (res) {
      var newKey = L.taskKey(res.file, res.line_text);
      if (expanded === oldKey) expanded = newKey;
      if (sel.key === oldKey) sel.key = newKey;
      showToast("Moved to " + (kind === "inbox" ? "Inbox" : name));
      return refresh();
    }).catch(fail);
  }

  function place(anchor) {
    var r = anchor.getBoundingClientRect();
    popEl.style.left = "0px"; popEl.style.top = "0px";
    var w = popEl.offsetWidth, h = popEl.offsetHeight;
    var left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    popEl.style.left = left + "px";
    popEl.style.top = top + "px";
  }

  function anchorFor(act) {
    return viewEl.querySelector('.todo-card [data-act="' + act + '"]') ||
      (selectedEl() && selectedEl().querySelector(".todo-title")) || $(act + "-btn");
  }

  function openWhen(anchor) {
    var t = targetTodo();
    if (!t) return;
    var sel0 = t.isNew ? (creating.when && /^\d/.test(creating.when) ? creating.when : null) : (t.when || null);
    pop = { kind: "when", month: (sel0 && sel0 > today() ? sel0 : today()).slice(0, 7), selected: sel0 };
    popEl.innerHTML = L.whenPopoverHtml(pop.month, today(), sel0);
    popEl.hidden = false;
    place(anchor || anchorFor("when"));
    $("when-input").focus();
  }

  function redrawWhen() {
    popEl.querySelector(".cal").outerHTML = L.calendarGrid(pop.month, today(), pop.selected);
  }

  function openMove(anchor) {
    if (!targetTodo()) return;
    pop = { kind: "move" };
    popEl.innerHTML = '<input type="text" class="pop-input" id="move-input" placeholder="Move to…" autocomplete="off" dir="auto">' +
      '<div id="move-list">' + L.movePopoverHtml(state, "") + "</div>";
    popEl.hidden = false;
    place(anchor || anchorFor("move"));
    $("move-input").focus();
  }

  function openProjectMenu(anchor) {
    var p = (state.projects || []).filter(function (x) { return x.name === route.name; })[0];
    if (!p) return;
    pop = { kind: "project" };
    popEl.innerHTML =
      '<button type="button" class="pop-item" data-proj="reviewed">' + L.icon("logbook", "i-logbook") + "Mark as Reviewed</button>" +
      (p.status === "someday"
        ? '<button type="button" class="pop-item" data-proj="active">' + L.icon("layers") + "Make Active</button>"
        : '<button type="button" class="pop-item" data-proj="someday">' + L.icon("box", "i-someday") + "Move to Someday</button>") +
      '<button type="button" class="pop-item" data-proj="done">' + L.icon("check") + "Complete Project</button>" +
      '<div class="pop-sep"></div>' +
      '<a class="pop-item" href="' + L.escapeHtml(L.obsidianUrl(state.vault_name, p.file)) + '">' + L.icon("open") + "Open in Obsidian</a>";
    popEl.hidden = false;
    place(anchor);
  }

  function projectAction(what) {
    var name = route.name;
    closePop();
    if (what === "reviewed") {
      post("/api/review-project", { project: name }).then(function (r) {
        showToast("Reviewed — next review " + L.shortDate(r.review, today()));
        return refresh();
      }).catch(fail);
    } else {
      post("/api/project-status", { project: name, status: what }).then(function () {
        if (what === "done") { showToast("Completed “" + name + "”"); navigate({ view: "logbook" }); }
        return refresh();
      }).catch(fail);
    }
  }

  function closePop() {
    if (!pop) return;
    pop = null;
    popEl.hidden = true;
    popEl.innerHTML = "";
    if (expanded) focusTitle();
  }

  popEl.addEventListener("click", function (e) {
    var b;
    if ((b = e.target.closest("[data-when]"))) setWhen(b.getAttribute("data-when"));
    else if ((b = e.target.closest("[data-date]"))) setWhen(b.getAttribute("data-date") === today() ? "today" : b.getAttribute("data-date"));
    else if ((b = e.target.closest("[data-cal]"))) {
      var d = new Date(pop.month + "-01T00:00:00");
      d.setMonth(d.getMonth() + parseInt(b.getAttribute("data-cal"), 10));
      pop.month = L.isoDate(d).slice(0, 7);
      redrawWhen();
    } else if ((b = e.target.closest("[data-move-kind]"))) moveTo(b.getAttribute("data-move-kind"), b.getAttribute("data-move-name"));
    else if ((b = e.target.closest("[data-proj]"))) projectAction(b.getAttribute("data-proj"));
  });

  popEl.addEventListener("input", function (e) {
    if (e.target.id === "when-input") {
      var v = L.parseWhen(e.target.value, today());
      $("when-hint").textContent = !e.target.value.trim() ? "" : v === null ? "Not a date I know — try “fri” or “oct 3”"
        : "→ " + (v === "today" ? "Today" : v === "evening" ? "This Evening" : v === "someday" ? "Someday" : v === "anytime" ? "No date"
          : L.whenLabel({ when: v }, today()));
    } else if (e.target.id === "move-input") {
      $("move-list").innerHTML = L.movePopoverHtml(state, e.target.value);
    }
  });

  popEl.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { e.stopPropagation(); closePop(); return; }
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (e.target.id === "when-input") {
      var v = L.parseWhen(e.target.value, today());
      if (v) setWhen(v);
    } else if (e.target.id === "move-input") {
      var first = popEl.querySelector("[data-move-kind]");
      if (first) first.click();
    }
  });

  // ---- Quick Find ----

  var finder = { results: [], active: 0 };
  var finderInput = $("finder-input");

  function openFinder() {
    closePop();
    closeCard();
    $("finder").hidden = false;
    finderInput.value = "";
    finder = { results: [], active: 0 };
    $("finder-results").innerHTML = "";
    finderInput.focus();
  }

  function closeFinder() {
    $("finder").hidden = true;
    finderInput.blur();
  }

  function drawFinder() {
    $("finder-results").innerHTML = L.quickFindHtml(finder.results, finder.active);
    var a = $("finder-results").querySelector(".active");
    if (a) a.scrollIntoView({ block: "nearest" });
  }

  function goFound(r) {
    closeFinder();
    if (!r) return;
    navigate(r.route);
    if (r.tag) { tagFilter = r.tag; renderAll(); }
    if (r.kind === "todo") {
      if (!r.todo.done) { expanded = r.key; draft = null; renderAll(); }
      selectKey(r.key, true);
      if (!r.todo.done) focusTitle();
    }
  }

  finderInput.addEventListener("input", function () {
    finder = { results: L.quickFind(state, finderInput.value, today()), active: 0 };
    drawFinder();
  });
  finderInput.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      var n = finder.results.length;
      if (n) finder.active = (finder.active + (e.key === "ArrowDown" ? 1 : n - 1)) % n;
      drawFinder();
    } else if (e.key === "Enter") {
      e.preventDefault();
      goFound(finder.results[finder.active]);
    } else if (e.key === "Escape") {
      e.stopPropagation();
      closeFinder();
    }
  });
  $("finder-results").addEventListener("click", function (e) {
    var li = e.target.closest(".qf-item");
    if (li) goFound(finder.results[parseInt(li.getAttribute("data-i"), 10)]);
  });
  $("finder").addEventListener("click", function (e) { if (e.target === $("finder")) closeFinder(); });

  // ---- dialog (shortcuts) ----

  function openHelp() {
    $("dialog-title").textContent = "Keyboard shortcuts";
    $("dialog-body").innerHTML = L.shortcutsHtml();
    $("dialog").hidden = false;
    $("dialog-close").focus();
  }

  function closeDialog() { $("dialog").hidden = true; }
  $("dialog-close").addEventListener("click", closeDialog);
  $("dialog").addEventListener("click", function (e) { if (e.target === $("dialog")) closeDialog(); });

  // ---- clicks ----

  function openRow(el) {
    if (el.classList.contains("todo") && !el.classList.contains("todo-card")) {
      var t = L.findTodo(state, el.getAttribute("data-file"), el.getAttribute("data-line"));
      if (t && !t.done) openCard(t);
    } else if (el.classList.contains("event")) {
      toggleRecording({ subject: el.getAttribute("data-subject"), attendees: el.getAttribute("data-attendees") || "" });
    } else if (el.getAttribute("data-action") === "transcribe") {
      runTranscription();
    } else if (el.hasAttribute("data-route")) {
      var tag = el.getAttribute("data-tag");
      navigate(L.parseRoute(el.getAttribute("data-route")));
      if (tag) { tagFilter = tag; renderAll(); }
    } else if (el.classList.contains("note")) {
      window.location.href = L.obsidianUrl(state.vault_name, el.getAttribute("data-file"));
    }
  }

  function runTranscription() {
    if (transcribing === "running") return;
    transcribing = "running";
    renderAll();
    post("/api/transcribe", {}).then(function () { transcribing = null; }, function () { transcribing = "failed"; }).then(refresh);
  }

  viewEl.addEventListener("click", function (e) {
    var el = e.target;
    var card = el.closest(".todo-card");
    var act = el.closest("[data-act]");
    if (act) {
      var a = act.getAttribute("data-act");
      var t = card && !card.hasAttribute("data-new") ? L.findTodo(state, card.getAttribute("data-file"), card.getAttribute("data-line")) : null;
      e.preventDefault();
      e.stopPropagation();
      if (a === "when") openWhen(act);
      else if (a === "clear-when") setWhen("anytime");
      else if (a === "clear-deadline") {
        if (card.hasAttribute("data-new")) { creating.deadline = null; renderAll(); focusTitle(); }
        else if (t) edit(t, { new_due: "" });
      } else if (a === "move") openMove(act);
      else if (a === "obsidian" && t) window.location.href = L.obsidianUrl(state.vault_name, t.file);
      else if (a === "delete" && t) scheduleDelete(t);
      else if (a === "project-menu") openProjectMenu(act);
      else if (a === "project-reviewed") projectAction("reviewed");
      else if (a === "project-active") projectAction("active");
      else if (a === "toggle-logged") { showLogged = !showLogged; renderAll(); }
      return;
    }
    if (card) return; // clicks inside the card edit it
    if (expanded) { closeCard(); }

    var tagBtn = el.closest(".tagbtn");
    if (tagBtn) { tagFilter = tagBtn.getAttribute("data-tag") || null; sel = { key: null, index: -1 }; renderAll(); return; }

    var check = el.closest(".check");
    var row = el.closest(".nav-item");
    if (check && row) { toggleCheck(row.getAttribute("data-file"), row.getAttribute("data-line")); return; }
    if (el.closest("a[href]")) return; // group headers, notes and crumbs are real links
    if (!row) { select(-1); return; }
    var i = navItems().indexOf(row);
    var wasSelected = i === sel.index;
    select(i, false);
    // Things: click selects, a second click (or a double-click) opens — a tap on a touch screen
    // opens straight away; links act at once
    if (row.hasAttribute("data-route") || row.getAttribute("data-action")) openRow(row);
    else if ((wasSelected || touchOnly) && row.classList.contains("todo")) openRow(row);
  });

  viewEl.addEventListener("dblclick", function (e) {
    var row = e.target.closest(".nav-item");
    if (row && !row.classList.contains("todo-card") && !e.target.closest(".check")) openRow(row);
  });

  viewEl.addEventListener("input", function (e) {
    if (e.target.classList.contains("card-title")) draft = e.target.value;
  });

  viewEl.addEventListener("change", function (e) {
    var card = e.target.closest(".todo-card");
    if (!card) return;
    var isNew = card.hasAttribute("data-new");
    var t = isNew ? null : L.findTodo(state, card.getAttribute("data-file"), card.getAttribute("data-line"));
    if (e.target.classList.contains("card-deadline")) {
      if (isNew) { creating.deadline = e.target.value || null; e.target.blur(); renderAll(); focusTitle(); }
      else if (t) { e.target.blur(); edit(t, { new_due: e.target.value }); }
    } else if (e.target.classList.contains("card-context")) {
      if (isNew) { creating.context = e.target.value || null; e.target.blur(); renderAll(); focusTitle(); }
      else if (t && e.target.value) { e.target.blur(); edit(t, { new_context: e.target.value }); }
    }
  });

  // clicking anywhere outside the open card (and outside a popover) closes it
  document.addEventListener("mousedown", function (e) {
    if (pop && !popEl.contains(e.target) && !e.target.closest("[data-act]") && !e.target.closest(".bar-btn")) closePop();
  });
  $("scroll").addEventListener("click", function (e) {
    // (a target no longer in the page is the row the card just replaced — not "outside")
    if (expanded && e.target.isConnected && !e.target.closest(".todo-card") && !viewEl.contains(e.target)) closeCard();
  });

  navEl.addEventListener("click", function (e) {
    var a = e.target.closest("a[href^='#']");
    if (!a) return;
    e.preventDefault();
    navigate(L.parseRoute(a.getAttribute("href")));
  });
  viewEl.addEventListener("click", function (e) {
    var a = e.target.closest("a[href^='#']");
    if (!a) return;
    e.preventDefault();
    navigate(L.parseRoute(a.getAttribute("href")));
  }, true);

  toastEl.addEventListener("click", function (e) { if (e.target.id === "undo-btn") undoDelete(); });

  // ---- keyboard ----

  document.addEventListener("keydown", function (e) {
    if (!$("dialog").hidden) { if (e.key === "Escape") closeDialog(); return; }
    if (!$("finder").hidden) return; // the finder's input handles its own keys
    if (pop && e.key === "Escape") { closePop(); return; }
    var target = e.target;
    var tag = (target.tagName || "").toLowerCase();

    if (target.classList && target.classList.contains("card-title")) {
      if (e.key === "Enter" || e.key === "Escape") {
        e.preventDefault();
        var wasNew = expanded === "new";
        var emptyNew = wasNew && !(draft || "").trim();
        closeCard();
        // Enter on a new to-do starts the next one, like Things' Quick Entry
        if (wasNew && !emptyNew && e.key === "Enter") setTimeout(startCreate, 0);
      }
      return;
    }
    if (e.key === "Escape") {
      if (expanded) { closeCard(); return; }
      if (document.querySelector(".app").classList.contains("nav-open")) { document.querySelector(".app").classList.remove("nav-open"); return; }
      if (tagFilter) { tagFilter = null; renderAll(); return; }
      select(-1);
      return;
    }
    if (tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable) return;
    if (pop) return;
    if ((e.key === "Enter" || e.key === " ") && (tag === "button" || tag === "a")) return;
    var action = L.keyAction(e);
    if (action && runAction(action)) e.preventDefault();
  });

  function runAction(action) {
    var el = selectedEl();
    var t = targetTodo();
    if (action.indexOf("list:") === 0) {
      var n = parseInt(action.slice(5), 10);
      if (n > L.LISTS.length) return false;
      navigate({ view: L.LISTS[n - 1] });
      return true;
    }
    if (action.indexOf("when:") === 0) {
      if (t) setWhen(action.slice(5));
      return true;
    }
    switch (action) {
      case "down": if (expanded) closeCard(); move(1); return true;
      case "up": if (expanded) closeCard(); move(-1); return true;
      case "open":
        if (!el) return false;
        openRow(el);
        return true;
      case "complete":
        if (t && !t.isNew) toggleCheck(t.file, t.line_text);
        return true;
      case "delete":
        if (t && !t.isNew) scheduleDelete(t);
        return true;
      case "undo": undoDelete(); return true;
      case "when": if (t) openWhen(); return true;
      case "move": if (t) openMove(); return true;
      case "obsidian":
        if (t && !t.isNew) window.location.href = L.obsidianUrl(state.vault_name, t.file);
        else if (el && el.classList.contains("note")) openRow(el);
        return true;
      case "search": openFinder(); return true;
      case "new": startCreate(); return true;
      case "help": openHelp(); return true;
      case "record": toggleRecording(); return true;
    }
    return false;
  }

  // ---- recording ----

  var recordBtn = $("record-btn");
  var rec = null;     // { handle, meta, timer } while recording
  var unsaved = null; // { pcm, meta } when an upload failed — kept so the audio isn't lost

  function setRecordButton(text, cls) {
    recordBtn.textContent = text;
    recordBtn.className = "bar-btn bar-record" + (cls ? " " + cls : "");
  }

  // ev: the calendar meeting being recorded ({subject, attendees}); by default whichever is on now
  function toggleRecording(ev) {
    if (unsaved) { upload(unsaved.pcm, unsaved.meta); return; }
    if (rec) stopRecording();
    else startRecording(ev);
  }

  function startRecording(ev) {
    recordBtn.disabled = true;
    MeetingRecorder.start().then(function (handle) {
      var e = ev || L.currentEvent(state && state.calendar, nowMinute());
      rec = { handle: handle, meta: {
        started: L.localDateTime(handle.startedAt), title: e ? e.subject : "", attendees: e ? e.attendees || "" : "",
      } };
      recordBtn.disabled = false;
      tick();
      rec.timer = setInterval(tick, 1000);
    }).catch(function () {
      recordBtn.disabled = false;
      flash("Mic unavailable");
    });
  }

  function tick() {
    var secs = Math.floor((Date.now() - rec.handle.startedAt.getTime()) / 1000);
    setRecordButton(Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0") +
      (rec.meta.title ? " · " + rec.meta.title : "") + " — stop", "recording");
  }

  function stopRecording() {
    var r = rec;
    rec = null;
    clearInterval(r.timer);
    recordBtn.disabled = true;
    setRecordButton("Saving…");
    r.handle.stop().then(function (pcm) { upload(pcm, r.meta); }, function () { flash("Recording failed"); });
  }

  function upload(pcm, meta) {
    recordBtn.disabled = true;
    setRecordButton("Saving…");
    fetch(L.recordingUrl(meta), {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm.buffer,
    }).then(function (res) {
      if (!res.ok) throw new Error("save failed: " + res.status);
      unsaved = null;
      flash("Saved ✓ transcribing…");
      refresh();
    }).catch(function () {
      unsaved = { pcm: pcm, meta: meta };
      recordBtn.disabled = false;
      setRecordButton("Save failed — retry", "recording");
    });
  }

  function flash(text) {
    recordBtn.disabled = false;
    setRecordButton(text);
    setTimeout(function () { if (!rec && !unsaved) setRecordButton("Record"); }, 4000);
  }

  recordBtn.addEventListener("click", function () { toggleRecording(); });
  window.addEventListener("beforeunload", function (e) {
    if (rec || unsaved) { e.preventDefault(); e.returnValue = ""; }
  });

  // ---- chrome: bottom bar, sidebar footer, mobile drawer ----

  $("new-btn").innerHTML = L.icon("plus");
  $("when-btn").innerHTML = L.icon("calendar");
  $("move-btn").innerHTML = L.icon("move");
  $("search-btn").innerHTML = L.icon("search");
  $("theme-toggle").innerHTML = L.icon("theme");
  $("help-btn").innerHTML = L.icon("help");
  $("dialog-close").innerHTML = L.icon("close");
  $("menu-btn").innerHTML = L.icon("menu");

  $("new-btn").addEventListener("click", startCreate);
  $("when-btn").addEventListener("click", function () { if (pop && pop.kind === "when") closePop(); else openWhen($("when-btn")); });
  $("move-btn").addEventListener("click", function () { if (pop && pop.kind === "move") closePop(); else openMove($("move-btn")); });
  $("search-btn").addEventListener("click", openFinder);
  $("find-btn").addEventListener("click", openFinder);
  $("help-btn").addEventListener("click", openHelp);
  $("theme-toggle").addEventListener("click", function () {
    applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
  });
  $("menu-btn").addEventListener("click", function () { document.querySelector(".app").classList.add("nav-open"); });
  $("scrim").addEventListener("click", function () { document.querySelector(".app").classList.remove("nav-open"); });

  var npForm = $("new-project-form"), npInput = $("new-project-title");
  $("new-project-btn").addEventListener("click", function () {
    npForm.hidden = false;
    npInput.value = "";
    npInput.focus();
  });
  npInput.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { e.stopPropagation(); npForm.hidden = true; }
  });
  npInput.addEventListener("blur", function () { setTimeout(function () { npForm.hidden = true; }, 150); });
  npForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var title = npInput.value.trim();
    if (!title) return;
    var area = route.view === "area" ? route.name : undefined;
    post("/api/new-project", { title: title, area: area }).then(function () {
      npForm.hidden = true;
      return refresh().then(function () { navigate({ view: "project", name: title }); });
    }).catch(fail);
  });

  var saved = store("dashboard-theme");
  applyTheme(saved || (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  setRecordButton("Record");
  refresh();
  setInterval(refresh, POLL_MS);
})();
