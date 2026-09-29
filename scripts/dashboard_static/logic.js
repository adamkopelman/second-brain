// scripts/dashboard_static/logic.js
// Pure list/rendering logic for the local dashboard, modelled on Things 3: Inbox, Today (+ This
// Evening), Upcoming, Anytime, Someday, Logbook — plus GTD's Waiting — and Areas holding Projects.
// No DOM, no fetch: runs identically under Node's test runner and in the browser.
(function (root) {
  var LISTS = ["inbox", "today", "upcoming", "anytime", "someday", "waiting", "logbook"];
  var LIST_META = {
    inbox: { label: "Inbox", icon: "inbox" },
    today: { label: "Today", icon: "star" },
    upcoming: { label: "Upcoming", icon: "calendar" },
    anytime: { label: "Anytime", icon: "layers" },
    someday: { label: "Someday", icon: "box" },
    waiting: { label: "Waiting", icon: "hourglass" },
    logbook: { label: "Logbook", icon: "logbook" },
  };
  var CONTEXTS = ["computer", "phone", "errands", "home", "office", "anywhere", "agenda", "unknown"];
  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December"];
  var ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
  var UPCOMING_DAYS = 7;

  // ---- icons: 20×20, drawn with currentColor so each list tints its own ----

  var ICON_PATHS = {
    inbox: '<path d="M2.5 11.5 4.8 4h10.4l2.3 7.5V16a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1z"/><path d="M2.5 11.5H7a3 3 0 0 0 6 0h4.5"/>',
    star: '<path class="fill" d="M10 2.2l2.4 5 5.4.6-4 3.8 1.1 5.4L10 14.3 5.1 17l1.1-5.4-4-3.8 5.4-.6z"/>',
    moon: '<path class="fill" d="M16.8 12.3A7.2 7.2 0 0 1 7.7 3.2a7.2 7.2 0 1 0 9.1 9.1z"/>',
    calendar: '<rect x="2.5" y="4" width="15" height="13.5" rx="2.5"/><path d="M2.5 8.5h15M6.5 2.5v3M13.5 2.5v3"/>' +
      '<path class="fill" d="M6 11h2v2H6zM9 11h2v2H9zM12 11h2v2h-2z"/>',
    layers: '<path class="fill" d="M10 2.5 18 6.5 10 10.5 2 6.5z"/><path d="M2 10.2l8 4 8-4M2 13.7l8 4 8-4"/>',
    box: '<rect x="2" y="3" width="16" height="4.5" rx="1.2"/><path d="M3.5 7.5V16a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7.5M8 11h4"/>',
    hourglass: '<path d="M5 2.5h10M5 17.5h10M6.2 2.5c0 4.2 3.8 4.8 3.8 7.5s-3.8 3.3-3.8 7.5M13.8 2.5c0 4.2-3.8 4.8-3.8 7.5s3.8 3.3 3.8 7.5"/>',
    logbook: '<rect x="2.5" y="2.5" width="15" height="15" rx="3.5"/><path d="M6.5 10.2l2.4 2.4 4.6-5"/>',
    area: '<path d="M10 2 17 5.8v8.4L10 18l-7-3.8V5.8z"/><path d="M3 5.8 10 9.6l7-3.8M10 9.6V18"/>',
    flag: '<path d="M4.5 18V3"/><path class="fill" d="M4.5 3.3h10.2l-2.3 3.6 2.3 3.6H4.5z"/>',
    tag: '<path d="M10.6 2.5h6.9v6.9l-8.3 8.3a1 1 0 0 1-1.4 0l-5.5-5.5a1 1 0 0 1 0-1.4z"/><circle class="fill" cx="14" cy="6" r="1.3"/>',
    move: '<path d="M3 10h12.5M11.5 5.5 16 10l-4.5 4.5"/>',
    search: '<circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.7 12.7 17 17"/>',
    plus: '<path d="M10 4v12M4 10h12"/>',
    trash: '<path d="M3.5 5.5h13M8 5.5v-2h4v2M5 5.5l.8 11a1 1 0 0 0 1 1h6.4a1 1 0 0 0 1-1l.8-11"/>',
    mic: '<rect x="7" y="2.5" width="6" height="10" rx="3"/><path d="M4.5 10a5.5 5.5 0 0 0 11 0M10 15.5V18"/>',
    open: '<path d="M11 3h6v6M17 3l-8 8M15 12v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4"/>',
    menu: '<path d="M3 5.5h14M3 10h14M3 14.5h14"/>',
    note: '<path d="M5 2.5h7l3.5 3.5v11H4.5v-14.5z"/><path d="M7.5 10h5M7.5 13h5"/>',
    more: '<circle class="fill" cx="4.5" cy="10" r="1.5"/><circle class="fill" cx="10" cy="10" r="1.5"/><circle class="fill" cx="15.5" cy="10" r="1.5"/>',
    check: '<path d="M5 10.5l3.2 3.2L15 6.5"/>',
    alert: '<circle cx="10" cy="10" r="7.5"/><path d="M10 6v4.5M10 13.5v.3"/>',
    person: '<circle cx="10" cy="6.5" r="3.5"/><path d="M3.5 17.5a6.5 6.5 0 0 1 13 0"/>',
    theme: '<circle cx="10" cy="10" r="7.5"/><path class="fill" d="M10 2.5a7.5 7.5 0 0 1 0 15z"/>',
    help: '<circle cx="10" cy="10" r="7.5"/><path d="M7.8 7.8a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.5v.4M10 14.3v.2"/>',
    close: '<path d="M5 5l10 10M15 5 5 15"/>',
    chevronLeft: '<path d="M12.5 4.5 7 10l5.5 5.5"/>',
    chevronRight: '<path d="M7.5 4.5 13 10l-5.5 5.5"/>',
    heading: '<path d="M3 5h14M3 10h9M3 15h11"/>',
  };

  function icon(name, cls) {
    return '<svg class="icon' + (cls ? " " + cls : "") + '" viewBox="0 0 20 20" aria-hidden="true">' +
      (ICON_PATHS[name] || "") + "</svg>";
  }

  // Things' project icon: a ring whose wedge fills as its to-dos get done.
  function pie(project) {
    var total = (project.open || 0) + (project.done || 0);
    var pct = total ? Math.round((project.done || 0) / total * 100) : 0;
    return '<span class="pie" style="--p:' + pct + '" title="' + pct + '% done"></span>';
  }

  // ---- basics ----

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function taskKey(file, lineText) {
    return file + "|" + lineText;
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function isoDate(d) {
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }

  function localDateTime(d) {
    return isoDate(d) + "T" + pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
  }

  function parseIso(iso) {
    return new Date(iso + "T00:00:00");
  }

  function addDays(iso, n) {
    var d = parseIso(iso);
    d.setDate(d.getDate() + n);
    return isoDate(d);
  }

  function daysBetween(a, b) {
    return Math.round((parseIso(b) - parseIso(a)) / 86400000);
  }

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  // "Fri" within the coming week, "Oct 3" this year, "Oct 3, 2027" otherwise.
  function shortDate(iso, today) {
    if (!iso || !ISO_DATE.test(iso)) return iso || "";
    var d = parseIso(iso);
    var diff = daysBetween(today, iso);
    if (diff > 0 && diff < 7) return WEEKDAYS[d.getDay()].slice(0, 3);
    var s = MONTHS[d.getMonth()].slice(0, 3) + " " + d.getDate();
    return iso.slice(0, 4) === today.slice(0, 4) ? s : s + ", " + iso.slice(0, 4);
  }

  // Things' deadline wording: "2 days ago", "today", "tomorrow", "3 days left", then the date.
  function deadlineLabel(iso, today) {
    if (!iso || !ISO_DATE.test(iso)) return iso || "";
    var diff = daysBetween(today, iso);
    if (diff < 0) return plural(-diff, "day") + " ago";
    if (diff === 0) return "today";
    if (diff === 1) return "tomorrow";
    if (diff < 7) return diff + " days left";
    return shortDate(iso, today);
  }

  function obsidianUrl(vaultName, file) {
    return "obsidian://open?vault=" + encodeURIComponent(vaultName || "") + "&file=" + encodeURIComponent(file);
  }

  // ---- natural-language When ("Jump Start") ----

  // "fri", "frid", "friday" -> 5; at least three letters of the name, so "m" or "ma" aren't guesses.
  function nameIndex(word, names) {
    if (!word || word.length < 3) return -1;
    for (var i = 0; i < names.length; i++) {
      if (names[i].toLowerCase().indexOf(word) === 0) return i;
    }
    return -1;
  }

  // Returns "today" | "evening" | "someday" | "anytime" | an ISO date, or null if not understood.
  function parseWhen(text, today) {
    var s = String(text || "").trim().toLowerCase().replace(/\s+/g, " ");
    if (!s) return null;
    if (/^(today|tod|now)$/.test(s)) return "today";
    if (/^(tonight|evening|this evening|eve)$/.test(s)) return "evening";
    if (/^(someday|some ?day|later|some)$/.test(s)) return "someday";
    if (/^(anytime|any|no date|none|clear)$/.test(s)) return "anytime";
    if (/^(tomorrow|tmrw?|tom|tmr)$/.test(s)) return addDays(today, 1);
    if (ISO_DATE.test(s)) return s <= today ? "today" : s;
    var t = parseIso(today);
    var m;
    if ((m = /^(?:in )?(\d+) ?(d|days?|w|wks?|weeks?|m|mos?|months?)$/.exec(s))) {
      var n = parseInt(m[1], 10);
      if (m[2][0] === "d") return n === 0 ? "today" : addDays(today, n);
      if (m[2][0] === "w") return addDays(today, 7 * n);
      var d = new Date(t.getFullYear(), t.getMonth() + n, t.getDate());
      return isoDate(d);
    }
    if (s === "next week") return addDays(today, ((8 - t.getDay()) % 7) || 7); // next Monday
    if (s === "next month") return isoDate(new Date(t.getFullYear(), t.getMonth() + 1, 1));
    if (/^(this )?weekend$/.test(s)) return t.getDay() === 6 ? "today" : addDays(today, (6 - t.getDay()) || 7);
    if ((m = /^(next |this )?([a-z]+)$/.exec(s)) && nameIndex(m[2], WEEKDAYS) >= 0) {
      var ahead = ((nameIndex(m[2], WEEKDAYS) - t.getDay()) + 7) % 7 || 7;
      return addDays(today, ahead + (m[1] === "next " ? 7 : 0));
    }
    if ((m = /^([a-z]+) (\d{1,2})(?:,? (\d{4}))?$/.exec(s)) || (m = /^(\d{1,2}) ([a-z]+)(?:,? (\d{4}))?$/.exec(s))) {
      var numFirst = /^\d/.test(m[1]);
      var mi = nameIndex(numFirst ? m[2] : m[1], MONTHS);
      var day = parseInt(numFirst ? m[1] : m[2], 10);
      if (mi < 0) return null;
      var year = m[3] ? parseInt(m[3], 10) : t.getFullYear();
      var cand = new Date(year, mi, day);
      if (cand.getMonth() !== mi) return null; // "feb 31"
      var iso = isoDate(cand);
      if (!m[3] && iso < today) iso = isoDate(new Date(year + 1, mi, day));
      return iso <= today ? "today" : iso;
    }
    return null;
  }

  // Label for a to-do's When button / pill.
  function whenLabel(t, today) {
    if (t.status === "someday") return "Someday";
    if (!t.when) return "";
    if (t.when <= today) return t.evening ? "This Evening" : "Today";
    if (t.when === addDays(today, 1)) return "Tomorrow";
    var d = parseIso(t.when);
    return WEEKDAYS[d.getDay()].slice(0, 3) + ", " + MONTHS[d.getMonth()].slice(0, 3) + " " + d.getDate() +
      (t.when.slice(0, 4) !== today.slice(0, 4) ? ", " + t.when.slice(0, 4) : "");
  }

  // ---- which list a to-do is on ----

  function projectIndex(state) {
    var idx = {};
    (state.projects || []).forEach(function (p) { idx[p.name] = p; });
    return idx;
  }

  function inSomedayProject(t, projects) {
    return !!(t.project && projects[t.project] && projects[t.project].status === "someday");
  }

  function isToday(t, today) {
    if (t.done || t.status === "someday") return false;
    return !!((t.when && t.when <= today) || (t.deadline && t.deadline <= today));
  }

  function openTodos(state, pending) {
    return (state.todos || []).filter(function (t) {
      return !t.done && !(pending && pending[taskKey(t.file, t.line_text)]);
    });
  }

  function listToday(state, today, pending) {
    var projects = projectIndex(state);
    var items = openTodos(state, pending).filter(function (t) {
      return isToday(t, today) && !inSomedayProject(t, projects);
    });
    // what's overdue floats to the top; otherwise keep the notes' own order
    var overdue = function (t) { return t.deadline && t.deadline < today ? 0 : 1; };
    items = items.map(function (t, i) { return [t, i]; }).sort(function (a, b) {
      return overdue(a[0]) - overdue(b[0]) || a[1] - b[1];
    }).map(function (x) { return x[0]; });
    return {
      day: items.filter(function (t) { return !t.evening; }),
      evening: items.filter(function (t) { return t.evening; }),
    };
  }

  function isAnytime(t, today, projects) {
    if (t.inbox || t.status === "waiting" || t.status === "someday" || inSomedayProject(t, projects)) return false;
    if (!(t.status === "next" || t.project || t.area)) return false;
    return !t.when || t.when <= today;
  }

  function listAnytime(state, today, pending) {
    var projects = projectIndex(state);
    return openTodos(state, pending).filter(function (t) { return isAnytime(t, today, projects); });
  }

  function listSomeday(state, pending) {
    var projects = projectIndex(state);
    return {
      todos: openTodos(state, pending).filter(function (t) {
        return t.status === "someday" && !inSomedayProject(t, projects);
      }),
      projects: (state.projects || []).filter(function (p) { return p.status === "someday"; }),
    };
  }

  function listWaiting(state, pending) {
    return openTodos(state, pending).filter(function (t) { return t.status === "waiting"; })
      .sort(function (a, b) { return (a.since || "9999") < (b.since || "9999") ? -1 : (a.since || "9999") > (b.since || "9999") ? 1 : 0; });
  }

  function listInbox(state, pending) {
    return {
      todos: openTodos(state, pending).filter(function (t) { return t.inbox; }),
      notes: state.inbox_notes || [],
    };
  }

  // The date a to-do sits on in Upcoming: its When if that's still ahead, else its Deadline.
  function upcomingDate(t, today) {
    if (t.when && t.when > today) return t.when;
    if (!t.when && t.deadline && t.deadline > today) return t.deadline;
    return null;
  }

  // Things' Upcoming: the next seven days one by one, then the months after that.
  function listUpcoming(state, today, pending) {
    var projects = projectIndex(state);
    var days = [];
    for (var i = 1; i <= UPCOMING_DAYS; i++) days.push({ date: addDays(today, i), todos: [], events: [] });
    var months = [];
    var monthIdx = {};
    openTodos(state, pending).forEach(function (t) {
      if (t.status === "someday" || inSomedayProject(t, projects)) return;
      var date = upcomingDate(t, today);
      if (!date) return;
      var n = daysBetween(today, date);
      if (n <= UPCOMING_DAYS) { days[n - 1].todos.push(t); return; }
      var key = date.slice(0, 7);
      if (!monthIdx[key]) { monthIdx[key] = { month: key, todos: [] }; months.push(monthIdx[key]); }
      monthIdx[key].todos.push(t);
    });
    ((state.calendar && state.calendar.events) || []).forEach(function (ev) {
      var n = daysBetween(today, ev.date);
      if (n >= 1 && n <= UPCOMING_DAYS) days[n - 1].events.push(ev);
    });
    days.forEach(function (d) {
      d.todos.sort(function (a, b) { return upcomingDate(a, today) < upcomingDate(b, today) ? -1 : 0; });
    });
    months.sort(function (a, b) { return a.month < b.month ? -1 : 1; });
    months.forEach(function (m) {
      m.todos.sort(function (a, b) { return upcomingDate(a, today) < upcomingDate(b, today) ? -1 : upcomingDate(a, today) > upcomingDate(b, today) ? 1 : 0; });
    });
    return { days: days, months: months };
  }

  // Completed to-dos, newest first: one group per day for the last week, then one per month.
  function listLogbook(state, today) {
    var groups = [];
    var idx = {};
    (state.todos || []).filter(function (t) { return t.done; }).forEach(function (t) {
      var c = t.completed;
      var key, label;
      if (!c || !ISO_DATE.test(c)) { key = "~"; label = "Earlier"; }
      else {
        var ago = daysBetween(c, today);
        if (ago <= 0) { key = c; label = "Today"; }
        else if (ago === 1) { key = c; label = "Yesterday"; }
        else if (ago < 7) { key = c; label = WEEKDAYS[parseIso(c).getDay()]; }
        else { key = c.slice(0, 7); label = MONTHS[parseInt(c.slice(5, 7), 10) - 1] + (c.slice(0, 4) !== today.slice(0, 4) ? " " + c.slice(0, 4) : ""); }
      }
      if (!idx[key]) { idx[key] = { key: key, label: label, todos: [] }; groups.push(idx[key]); }
      idx[key].todos.push(t);
    });
    return groups;
  }

  function projectTodos(state, name, pending) {
    return (state.todos || []).filter(function (t) {
      return t.project === name && !(pending && pending[taskKey(t.file, t.line_text)]);
    });
  }

  // ---- tags (GTD contexts are Things' tags) ----

  function todoTags(t) {
    return (t.context ? [t.context] : []).concat(t.tags || []);
  }

  function tagCounts(todos) {
    var counts = {};
    var order = [];
    todos.forEach(function (t) {
      todoTags(t).forEach(function (g) {
        if (!counts[g]) { counts[g] = 0; order.push(g); }
        counts[g]++;
      });
    });
    order.sort(function (a, b) {
      var ia = CONTEXTS.indexOf(a), ib = CONTEXTS.indexOf(b);
      if (ia < 0) ia = 100;
      if (ib < 0) ib = 100;
      return ia - ib || (a < b ? -1 : 1);
    });
    return order.map(function (g) { return { tag: g, count: counts[g] }; });
  }

  function byTag(todos, tag) {
    if (!tag) return todos;
    return todos.filter(function (t) { return todoTags(t).indexOf(tag) >= 0; });
  }

  // ---- routes ----

  function parseRoute(hash) {
    var h = decodeURIComponent(String(hash || "").replace(/^#/, ""));
    if (LISTS.indexOf(h) >= 0) return { view: h };
    var m = /^(project|area)\/(.+)$/.exec(h);
    if (m) return { view: m[1], name: m[2] };
    return { view: "today" };
  }

  function routeHash(route) {
    if (route.view === "project" || route.view === "area") return "#" + route.view + "/" + encodeURIComponent(route.name);
    return "#" + route.view;
  }

  function sameRoute(a, b) {
    return a.view === b.view && (a.name || "") === (b.name || "");
  }

  // Where a to-do "lives" — Quick Find jumps there.
  function homeRoute(t, state, today) {
    var projects = projectIndex(state);
    if (t.done) return { view: "logbook" };
    if (t.project && projects[t.project]) return { view: "project", name: t.project };
    if (t.inbox) return { view: "inbox" };
    if (t.status === "waiting") return { view: "waiting" };
    if (t.area) return { view: "area", name: t.area };
    if (t.status === "someday") return { view: "someday" };
    if (isToday(t, today)) return { view: "today" };
    if (upcomingDate(t, today)) return { view: "upcoming" };
    return { view: "anytime" };
  }

  // Defaults for a to-do created while looking at a list — Things files it where you are.
  function newTodoDefaults(route, today, tag) {
    var d = { when: null, status: "next", project: null, area: null, context: tag && CONTEXTS.indexOf(tag) >= 0 ? tag : null };
    if (route.view === "today") d.when = "today";
    else if (route.view === "upcoming") d.when = addDays(today, 1);
    else if (route.view === "someday") d.status = "someday";
    else if (route.view === "waiting") d.status = "waiting";
    else if (route.view === "project") d.project = route.name;
    else if (route.view === "area") d.area = route.name;
    return d;
  }

  // ---- meetings & other things needing attention ----

  function meetingStatus(m) {
    if (m.transcription_status === "failed") return "failed";
    if (m.transcription_status && m.transcription_status !== "done") return "transcribe";
    if (m.transcription_status === "done" && m.summary_status !== "done") return "summarize";
    return null;
  }

  // Quiet reminders for the top of Today (Things has none of these; GTD needs them).
  function attentionItems(state, today) {
    var items = [];
    var triage = openTodos(state).filter(function (t) { return t.context === "unknown"; }).length;
    if (triage) {
      items.push({ key: "triage", text: plural(triage, "to-do") + " from meetings need" + (triage === 1 ? "s" : "") + " a tag",
        route: { view: "anytime" }, tag: "unknown" });
    }
    var reviews = (state.projects || []).filter(function (p) { return p.review_overdue; });
    if (reviews.length === 1) {
      items.push({ key: "review", text: reviews[0].name + " is due for review", route: { view: "project", name: reviews[0].name } });
    } else if (reviews.length > 1) {
      items.push({ key: "review", text: plural(reviews.length, "project") + " due for review",
        route: { view: "project", name: reviews[0].name } });
    }
    var counts = { failed: 0, transcribe: 0, summarize: 0 };
    (state.meetings || []).forEach(function (m) {
      var s = meetingStatus(m);
      if (s) counts[s]++;
    });
    if (counts.transcribe) items.push({ key: "mtg-transcribe", action: "transcribe", text: plural(counts.transcribe, "meeting") + " to transcribe" });
    if (counts.summarize) items.push({ key: "mtg-summarize", text: plural(counts.summarize, "meeting") + " to summarize", hint: "run /gtd-summarize-meetings" });
    if (counts.failed) items.push({ key: "mtg-failed", text: plural(counts.failed, "meeting") + " failed to transcribe", hint: "see the note in Obsidian" });
    return items;
  }

  // ---- calendar events ----

  function eventsOn(calendar, date) {
    return ((calendar && calendar.events) || []).filter(function (ev) { return ev.date === date; });
  }

  function eventTime(ev) {
    if (ev.all_day) return "all day";
    var sameDay = ev.end && ev.end.slice(0, 10) === ev.date;
    return ev.start.slice(11, 16) + (sameDay ? " – " + ev.end.slice(11, 16) : "");
  }

  function eventLine(ev, now) {
    var past = now && !ev.all_day && ev.end && ev.end.slice(0, 16) <= now;
    return '<li class="event nav-item' + (past ? " event-past" : "") + '" data-key="' +
      escapeHtml("ev|" + ev.start + "|" + ev.subject) + '" data-subject="' + escapeHtml(ev.subject) +
      '" data-attendees="' + escapeHtml(ev.attendees || "") + '" title="Enter records this meeting">' +
      '<span class="ev-time">' + escapeHtml(eventTime(ev)) + "</span>" +
      '<span class="ev-subject" dir="auto">' + escapeHtml(ev.subject) + "</span>" +
      (ev.location ? '<span class="ev-loc" dir="auto">' + escapeHtml(ev.location) + "</span>" : "") + "</li>";
  }

  function eventList(events, now) {
    if (!events.length) return "";
    return '<ul class="events">' + events.map(function (ev) { return eventLine(ev, now); }).join("") + "</ul>";
  }

  // The timed meeting under way now, or starting within 10 minutes — used to name a recording.
  function currentEvent(calendar, now) {
    var d = new Date(now + ":00");
    d.setMinutes(d.getMinutes() + 10);
    var soon = localDateTime(d).slice(0, 16);
    var hits = ((calendar && calendar.events) || []).filter(function (ev) {
      return !ev.all_day && ev.start.slice(0, 16) <= soon && (ev.end || "").slice(0, 16) > now;
    });
    return hits[0] || null;
  }

  function recordingUrl(meta) {
    var q = "started=" + encodeURIComponent(meta.started);
    if (meta.title) q += "&title=" + encodeURIComponent(meta.title);
    if (meta.attendees) q += "&attendees=" + encodeURIComponent(meta.attendees);
    return "/api/record-meeting?" + q;
  }

  function calendarNote(calendar) {
    var status = calendar && calendar.status;
    if (status === "loading") return '<p class="cal-note">Loading your Outlook calendar…</p>';
    if (status === "unavailable") {
      return '<p class="cal-note">Outlook calendar unavailable' + (calendar.error ? " — " + escapeHtml(calendar.error) : "") + "</p>";
    }
    return "";
  }

  // ---- to-do rows ----

  // opts: today, list (the view it's drawn in), checking/pending maps, expanded key, draft.
  function todoRow(t, o) {
    var key = taskKey(t.file, t.line_text);
    if (o.expanded === key) return todoCard(t, o);
    var today = o.today;
    var checking = o.checking && o.checking[key];
    var done = t.done || checking;
    var before = "";
    if (o.list !== "today" && !t.done && isToday(t, today)) {
      before = t.evening ? icon("moon", "i-evening") : icon("star", "i-today");
    } else if (o.list !== "upcoming" && !t.done && t.when && t.when > today) {
      before = '<span class="when-pill">' + escapeHtml(shortDate(t.when, today)) + "</span>";
    } else if (o.list !== "someday" && !t.done && t.status === "someday") {
      before = '<span class="when-pill">Someday</span>';
    }
    var tags = todoTags(t).map(function (g) {
      return '<span class="tag' + (g === "unknown" ? " tag-warn" : "") + '">' + escapeHtml(g) + "</span>";
    }).join("");
    var links = (t.links || []).map(function (l) {
      return '<span class="chip">' + icon("person") + escapeHtml(l) + "</span>";
    }).join("");
    var right = "";
    if (t.deadline && !t.done) {
      var urgent = t.deadline <= today;
      right += '<span class="deadline' + (urgent ? " urgent" : "") + '" title="Deadline ' + escapeHtml(t.deadline) + '">' +
        icon("flag") + escapeHtml(deadlineLabel(t.deadline, today)) + "</span>";
    }
    if (o.list === "waiting" && t.since && ISO_DATE.test(t.since)) {
      var age = daysBetween(t.since, today);
      right += '<span class="since' + (age >= 7 ? " stale" : "") + '" title="waiting since ' + escapeHtml(t.since) + '">' +
        (age <= 0 ? "today" : age + "d") + "</span>";
    }
    if (o.list === "logbook" && t.completed) right += '<span class="since">' + escapeHtml(shortDate(t.completed, today)) + "</span>";
    var sub = "";
    // under a project/area group header (or on the project's own page) the name would repeat
    if (o.list !== "project" && !o.grouped && (t.project || t.area || t.meeting)) {
      sub = '<span class="where" dir="auto">' + escapeHtml(t.project || t.area || t.meeting) + "</span>";
    } else if (o.grouped && !t.project && !t.area && t.meeting) {
      sub = '<span class="where" dir="auto">' + escapeHtml(t.meeting) + "</span>";
    }
    return '<li class="todo nav-item' + (done ? " is-done" : "") + (checking ? " checking" : "") + '" data-key="' + escapeHtml(key) +
      '" data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '">' +
      '<button type="button" class="check" aria-label="' + (t.done ? "Mark as open" : "Complete") + '"' +
      (done ? ' aria-pressed="true"' : "") + ">" + icon("check") + "</button>" +
      '<div class="todo-main"><div class="todo-line">' + before +
      '<span class="todo-title" dir="auto">' + escapeHtml(t.text) + "</span>" + links + tags + "</div>" + sub + "</div>" +
      right + "</li>";
  }

  // Things' open to-do: the row grows into a card you edit in place.
  function todoCard(t, o) {
    var isNew = !t.file;
    var key = isNew ? "new" : taskKey(t.file, t.line_text);
    var today = o.today;
    var title = o.draft != null ? o.draft : (t.text || "");
    var wl = whenLabel(t, today);
    var whenIcon = t.status === "someday" ? icon("box", "i-someday")
      : (t.when && t.when <= today ? icon(t.evening ? "moon" : "star", t.evening ? "i-evening" : "i-today") : icon("calendar", "i-upcoming"));
    var pills = "";
    if (wl) {
      pills += '<button type="button" class="pill pill-when" data-act="when">' + whenIcon + escapeHtml(wl) +
        '<span class="pill-x" data-act="clear-when" title="Clear">' + icon("close") + "</span></button>";
    }
    if (t.deadline) {
      pills += '<label class="pill pill-deadline' + (t.deadline <= today ? " urgent" : "") + '">' + icon("flag") +
        "Deadline: " + escapeHtml(shortDate(t.deadline, today)) +
        '<input type="date" class="card-deadline" value="' + escapeHtml(t.deadline) + '" aria-label="Deadline">' +
        '<span class="pill-x" data-act="clear-deadline" title="Clear">' + icon("close") + "</span></label>";
    }
    // a context can be changed but not removed (every GTD action has one), so "No tag" only while unset
    var ctxOptions = (t.context ? [] : ['<option value="" selected>No tag</option>']).concat(CONTEXTS.map(function (c) {
      return '<option value="' + c + '"' + (c === t.context ? " selected" : "") + ">" + c + "</option>";
    })).join("");
    var where = t.project || t.area || (isNew ? "" : (t.inbox ? "Inbox" : t.meeting || ""));
    if ((o.list === "project" || o.list === "area") && !isNew) where = ""; // the page already says so
    return '<li class="todo todo-card nav-item" data-key="' + escapeHtml(key) + '"' +
      (isNew ? ' data-new="1"' : ' data-file="' + escapeHtml(t.file) + '" data-line="' + escapeHtml(t.line_text) + '"') + ">" +
      '<div class="card-top"><span class="check check-static">' + icon("check") + "</span>" +
      '<input class="card-title" type="text" value="' + escapeHtml(title) + '" placeholder="New To-Do" dir="auto" autocomplete="off" aria-label="Title">' +
      "</div>" +
      ((t.links || []).length ? '<div class="card-links">' + t.links.map(function (l) {
        return '<span class="chip">' + icon("person") + escapeHtml(l) + "</span>";
      }).join("") + "</div>" : "") +
      '<div class="card-foot">' +
      '<div class="card-pills">' + pills +
      (where ? '<span class="card-where">' + icon(t.project ? "layers" : t.area ? "area" : "inbox") + escapeHtml(where) + "</span>" : "") +
      "</div>" +
      '<div class="card-tools">' +
      '<label class="tool tool-tag" title="Tag">' + icon("tag") + '<select class="card-context" aria-label="Tag">' + ctxOptions + "</select>" +
      (t.context ? '<span class="tool-text">' + escapeHtml(t.context) + "</span>" : "") + "</label>" +
      '<button type="button" class="tool" data-act="when" title="When (w)">' + icon("calendar") + "</button>" +
      (t.deadline ? "" : '<label class="tool" title="Deadline">' + icon("flag") + '<input type="date" class="card-deadline" aria-label="Deadline"></label>') +
      '<button type="button" class="tool" data-act="move" title="Move (m)">' + icon("move") + "</button>" +
      (isNew ? "" : '<button type="button" class="tool" data-act="obsidian" title="Open the note in Obsidian (o)">' + icon("open") + "</button>" +
        '<button type="button" class="tool tool-danger" data-act="delete" title="Delete (d)">' + icon("trash") + "</button>") +
      "</div></div></li>";
  }

  function todoList(todos, o) {
    if (!todos.length) return "";
    return '<ul class="todos">' + todos.map(function (t) { return todoRow(t, o); }).join("") + "</ul>";
  }

  // The card for a to-do being created, placed at the top of the list.
  function newCard(o) {
    if (!o.creating) return "";
    var c = o.creating;
    var t = { text: "", when: c.when === "today" || c.when === "evening" ? o.today : c.when,
      evening: c.when === "evening", deadline: c.deadline, status: c.status, context: c.context,
      project: c.project, area: c.area, links: [] };
    return '<ul class="todos">' + todoCard(t, o) + "</ul>";
  }

  // Groups like Things' Anytime: loose to-dos first, then each project, areas gathering theirs.
  function groupByProject(todos, state) {
    var projects = projectIndex(state);
    var groups = [];
    var idx = {};
    function group(key, make) {
      if (!idx[key]) { idx[key] = make(); groups.push(idx[key]); }
      return idx[key];
    }
    var loose = { kind: "loose", todos: [] };
    todos.forEach(function (t) {
      if (t.project) {
        group("p|" + t.project, function () {
          return { kind: "project", name: t.project, area: t.area, project: projects[t.project] || { name: t.project }, todos: [] };
        }).todos.push(t);
      } else if (t.area) {
        group("a|" + t.area, function () { return { kind: "area", name: t.area, area: t.area, todos: [] }; }).todos.push(t);
      } else {
        loose.todos.push(t);
      }
    });
    // an area's own to-dos, then its projects, areas alphabetically after area-less projects
    groups.sort(function (a, b) {
      var aa = a.area || "", ba = b.area || "";
      if (aa !== ba) return aa === "" ? -1 : ba === "" ? 1 : aa.toLowerCase() < ba.toLowerCase() ? -1 : 1;
      if (a.kind !== b.kind) return a.kind === "area" ? -1 : 1;
      return 0;
    });
    return (loose.todos.length ? [loose] : []).concat(groups);
  }

  function groupHeader(g) {
    if (g.kind === "project") {
      return '<h3 class="group-h"><a href="' + escapeHtml(routeHash({ view: "project", name: g.name })) + '">' +
        pie(g.project) + '<span dir="auto">' + escapeHtml(g.name) + "</span></a>" +
        (g.area ? '<span class="group-area">' + escapeHtml(g.area) + "</span>" : "") + "</h3>";
    }
    if (g.kind === "area") {
      return '<h3 class="group-h"><a href="' + escapeHtml(routeHash({ view: "area", name: g.name })) + '">' +
        icon("area", "i-area") + '<span dir="auto">' + escapeHtml(g.name) + "</span></a></h3>";
    }
    return "";
  }

  function groupedList(todos, state, o) {
    var inGroup = Object.assign({}, o, { grouped: true });
    return groupByProject(todos, state).map(function (g) {
      return '<section class="group">' + groupHeader(g) + todoList(g.todos, g.kind === "loose" ? o : inGroup) + "</section>";
    }).join("");
  }

  function tagBar(todos, current) {
    var tags = tagCounts(todos);
    if (tags.length < 2 && !current) return "";
    return '<div class="tagbar" role="toolbar" aria-label="Filter by tag">' +
      '<button type="button" class="tagbtn' + (current ? "" : " on") + '" data-tag="">All</button>' +
      tags.map(function (g) {
        return '<button type="button" class="tagbtn' + (g.tag === current ? " on" : "") + (g.tag === "unknown" ? " tag-warn" : "") +
          '" data-tag="' + escapeHtml(g.tag) + '">' + escapeHtml(g.tag) + "</button>";
      }).join("") + "</div>";
  }

  function emptyState(iconName, text) {
    return '<div class="empty">' + icon(iconName, "empty-icon") + "<p>" + escapeHtml(text) + "</p></div>";
  }

  function viewHeader(iconName, title, cls, extra) {
    return '<header class="view-h ' + (cls || "") + '">' +
      '<h1>' + (iconName ? icon(iconName, "view-icon") : "") + '<span dir="auto">' + escapeHtml(title) + "</span></h1>" +
      (extra || "") + "</header>";
  }

  // ---- views ----

  function renderInbox(state, o) {
    var l = listInbox(state, o.pending);
    var html = viewHeader("inbox", "Inbox", "c-inbox") + newCard(o);
    if (!l.todos.length && !l.notes.length) return html + (o.creating ? "" : emptyState("inbox", "Inbox Zero. Nothing left to process."));
    html += todoList(l.todos, o);
    if (l.notes.length) {
      html += '<ul class="todos notes">' + l.notes.map(function (n) {
        return '<li class="note nav-item" data-key="' + escapeHtml("note|" + n.file) + '" data-file="' + escapeHtml(n.file) + '">' +
          icon("note", "i-note") + '<a class="todo-title" dir="auto" href="' + escapeHtml(obsidianUrl(state.vault_name, n.file)) + '">' +
          escapeHtml(n.text) + "</a>" + (n.captured ? '<span class="since">' + escapeHtml(shortDate(n.captured, o.today)) + "</span>" : "") + "</li>";
      }).join("") + "</ul>";
    }
    return html + '<p class="foot-note">Clarify these with <code>/gtd-process-inbox</code>, or open a to-do and give it a When, a tag or a project.</p>';
  }

  function renderAttention(items) {
    if (!items.length) return "";
    return '<ul class="attention">' + items.map(function (a) {
      var attrs = ' data-key="' + escapeHtml("att|" + a.key) + '"';
      if (a.route) attrs += ' data-route="' + escapeHtml(routeHash(a.route)) + '"';
      if (a.tag) attrs += ' data-tag="' + escapeHtml(a.tag) + '"';
      if (a.action) attrs += ' data-action="' + escapeHtml(a.action) + '"';
      var nav = a.route || a.action;
      return '<li class="att' + (nav ? " nav-item att-link" : "") + '"' + attrs + ">" + icon("alert") +
        '<span class="att-text">' + escapeHtml(a.text) + "</span>" +
        (a.hint ? '<span class="att-hint">' + escapeHtml(a.hint) + "</span>" : "") + "</li>";
    }).join("") + "</ul>";
  }

  function renderToday(state, o) {
    var l = listToday(state, o.today, o.pending);
    var all = l.day.concat(l.evening);
    var day = byTag(l.day, o.tag), evening = byTag(l.evening, o.tag);
    var events = eventsOn(state.calendar, o.today);
    var html = viewHeader("star", "Today", "c-today") + calendarNote(state.calendar);
    if (!o.tag) html += eventList(events, o.now) + renderAttention(attentionItems(state, o.today));
    html += tagBar(all, o.tag) + newCard(o);
    if (!day.length && !evening.length && !o.creating) {
      return html + (all.length ? emptyState("tag", "Nothing tagged " + o.tag + " today.") : emptyState("star", "Nothing planned for today. Enjoy the calm, or pull something in from Anytime."));
    }
    html += todoList(day, o);
    if (evening.length) {
      html += '<section class="evening"><h2 class="section-h">' + icon("moon", "i-evening") + "This Evening</h2>" + todoList(evening, o) + "</section>";
    }
    return html;
  }

  function dayHeader(date, today) {
    var d = parseIso(date);
    var name = date === addDays(today, 1) ? "Tomorrow" : WEEKDAYS[d.getDay()];
    return '<h2 class="day-h"><span class="day-n">' + d.getDate() + '</span><span class="day-name">' + name + "</span></h2>";
  }

  function renderUpcoming(state, o) {
    var u = listUpcoming(state, o.today, o.pending);
    var every = [];
    u.days.forEach(function (d) { every = every.concat(d.todos); });
    u.months.forEach(function (m) { every = every.concat(m.todos); });
    var html = viewHeader("calendar", "Upcoming", "c-upcoming") + calendarNote(state.calendar) + tagBar(every, o.tag) + newCard(o);
    u.days.forEach(function (d) {
      var todos = byTag(d.todos, o.tag);
      var body = (o.tag ? "" : eventList(d.events, o.now)) + todoList(todos, o);
      html += '<section class="day' + (body ? "" : " day-empty") + '">' + dayHeader(d.date, o.today) + body + "</section>";
    });
    u.months.forEach(function (m) {
      var todos = byTag(m.todos, o.tag);
      if (!todos.length) return;
      var mi = parseInt(m.month.slice(5, 7), 10) - 1;
      html += '<section class="day"><h2 class="day-h month-h">' + MONTHS[mi] +
        (m.month.slice(0, 4) !== o.today.slice(0, 4) ? " " + m.month.slice(0, 4) : "") + "</h2>" + todoList(todos, o) + "</section>";
    });
    return html;
  }

  function renderAnytime(state, o) {
    var all = listAnytime(state, o.today, o.pending);
    var todos = byTag(all, o.tag);
    var html = viewHeader("layers", "Anytime", "c-anytime") + tagBar(all, o.tag) + newCard(o);
    if (!todos.length && !o.creating) return html + emptyState("layers", "No next actions. Add one, or run your weekly review.");
    return html + groupedList(todos, state, o);
  }

  function projectRow(p, o) {
    return '<li class="proj-row nav-item" data-key="' + escapeHtml("proj|" + p.name) + '" data-route="' +
      escapeHtml(routeHash({ view: "project", name: p.name })) + '">' + pie(p) +
      '<span class="todo-title" dir="auto">' + escapeHtml(p.name) + "</span>" +
      (p.review_overdue ? '<span class="dot" title="due for review"></span>' : "") +
      '<span class="since">' + (p.open ? p.open : "") + "</span></li>";
  }

  function renderSomeday(state, o) {
    var l = listSomeday(state, o.pending);
    var todos = byTag(l.todos, o.tag);
    var html = viewHeader("box", "Someday", "c-someday") + tagBar(l.todos, o.tag) + newCard(o);
    if (!todos.length && !l.projects.length && !o.creating) return html + emptyState("box", "Nothing on hold. Ideas you're not committing to yet go here.");
    if (l.projects.length && !o.tag) {
      html += '<section class="group"><h3 class="group-h plain">Projects</h3><ul class="todos">' +
        l.projects.map(function (p) { return projectRow(p, o); }).join("") + "</ul></section>";
    }
    return html + groupedList(todos, state, o);
  }

  function renderWaiting(state, o) {
    var all = listWaiting(state, o.pending);
    var todos = byTag(all, o.tag);
    var html = viewHeader("hourglass", "Waiting", "c-waiting") + tagBar(all, o.tag) + newCard(o);
    if (!todos.length && !o.creating) return html + emptyState("hourglass", "Not waiting on anyone.");
    return html + todoList(todos, o);
  }

  function renderLogbook(state, o) {
    var groups = listLogbook(state, o.today);
    var html = viewHeader("logbook", "Logbook", "c-logbook");
    if (!groups.length) return html + emptyState("logbook", "Completed to-dos will be logged here.");
    return html + groups.map(function (g) {
      return '<section class="group"><h2 class="section-h">' + escapeHtml(g.label) + "</h2>" + todoList(g.todos, o) + "</section>";
    }).join("");
  }

  function renderProject(state, name, o) {
    var p = projectIndex(state)[name];
    if (!p) return viewHeader("layers", name) + emptyState("layers", "This project is finished, or no longer exists.");
    var all = projectTodos(state, name, o.pending);
    var open = all.filter(function (t) { return !t.done; });
    var done = all.filter(function (t) { return t.done; });
    var shown = byTag(open, o.tag);
    var more = '<button type="button" class="icon-btn" data-act="project-menu" title="Project actions" aria-label="Project actions">' + icon("more") + "</button>";
    var html = '<header class="view-h c-project"><h1>' + pie(p) + '<span dir="auto">' + escapeHtml(p.name) + "</span></h1>" + more + "</header>";
    if (p.area) html += '<a class="crumb" href="' + escapeHtml(routeHash({ view: "area", name: p.area })) + '">' + icon("area") + escapeHtml(p.area) + "</a>";
    if (p.outcome) html += '<p class="notes" dir="auto">' + escapeHtml(p.outcome) + "</p>";
    if (p.status === "someday") html += '<p class="banner">' + icon("box") + 'This project is in Someday. <button type="button" class="link" data-act="project-active">Make it active</button></p>';
    if (p.review_overdue) {
      html += '<p class="banner banner-warn">' + icon("alert") + "Due for review" + (p.review ? " since " + escapeHtml(shortDate(p.review, o.today)) : "") +
        ' · <button type="button" class="link" data-act="project-reviewed">Mark as reviewed</button></p>';
    }
    html += tagBar(open, o.tag) + newCard(o);
    // headings in the note's own order; to-dos above the first heading lead
    var order = [null].concat(p.headings || []);
    var byHeading = {};
    shown.forEach(function (t) {
      var h = order.indexOf(t.heading) >= 0 ? t.heading : null;
      (byHeading[h] = byHeading[h] || []).push(t);
    });
    var body = order.filter(function (h, i) { return order.indexOf(h) === i; }).map(function (h) {
      var items = byHeading[h];
      if (!items || !items.length) return "";
      return '<section class="group">' + (h ? '<h2 class="heading" dir="auto">' + escapeHtml(h) + "</h2>" : "") + todoList(items, o) + "</section>";
    }).join("");
    if (!body && !o.creating) body = emptyState("layers", open.length ? "Nothing with that tag here." : "No open to-dos. Add the next action, or complete the project.");
    html += body;
    if (done.length) {
      html += '<button type="button" class="link logged-toggle" data-act="toggle-logged">' +
        (o.showLogged ? "Hide logged items" : "Show " + plural(done.length, "logged item")) + "</button>";
      if (o.showLogged) html += todoList(done, o);
    }
    return html;
  }

  function renderArea(state, name, o) {
    var area = (state.areas || []).filter(function (a) { return a.name === name; })[0];
    var projects = (state.projects || []).filter(function (p) { return p.area === name && p.status === "active"; });
    var own = openTodos(state, o.pending).filter(function (t) { return t.area === name && !t.project; });
    var tools = area && area.file ? '<a class="icon-btn" href="' + escapeHtml(obsidianUrl(state.vault_name, area.file)) +
      '" title="Open in Obsidian" aria-label="Open in Obsidian">' + icon("open") + "</a>" : "";
    var html = viewHeader("area", name, "c-area", tools) + tagBar(own, o.tag) + newCard(o);
    if (projects.length && !o.tag) {
      html += '<ul class="todos">' + projects.map(function (p) { return projectRow(p, o); }).join("") + "</ul>";
    }
    html += todoList(byTag(own, o.tag), o);
    if (!projects.length && !own.length && !o.creating) html += emptyState("area", "No projects or to-dos in this area yet.");
    return html;
  }

  function renderView(state, route, o) {
    switch (route.view) {
      case "inbox": return renderInbox(state, o);
      case "upcoming": return renderUpcoming(state, o);
      case "anytime": return renderAnytime(state, o);
      case "someday": return renderSomeday(state, o);
      case "waiting": return renderWaiting(state, o);
      case "logbook": return renderLogbook(state, o);
      case "project": return renderProject(state, route.name, o);
      case "area": return renderArea(state, route.name, o);
      default: return renderToday(state, o);
    }
  }

  // ---- sidebar ----

  function sidebarCounts(state, today) {
    var inbox = listInbox(state);
    var t = listToday(state, today);
    var todayAll = t.day.concat(t.evening);
    return {
      inbox: inbox.todos.length + inbox.notes.length,
      today: todayAll.length,
      todayDue: todayAll.filter(function (x) { return x.deadline && x.deadline <= today; }).length,
      waiting: listWaiting(state).length,
    };
  }

  function sidebarHtml(state, route, today) {
    var c = sidebarCounts(state, today);
    function item(view, count, badge) {
      var m = LIST_META[view];
      var cur = route.view === view;
      var n = LISTS.indexOf(view) + 1;
      return '<a href="#' + view + '" class="sb-item c-' + view + (cur ? " current" : "") + '"' + (cur ? ' aria-current="page"' : "") +
        ' title="' + m.label + " (" + n + ')">' + icon(m.icon, "sb-icon") + '<span class="sb-label">' + m.label + "</span>" +
        (badge ? '<span class="badge">' + badge + "</span>" : "") +
        (count ? '<span class="sb-count">' + count + "</span>" : "") + "</a>";
    }
    function projItem(p) {
      var cur = route.view === "project" && route.name === p.name;
      return '<a href="' + escapeHtml(routeHash({ view: "project", name: p.name })) + '" class="sb-item sb-project' + (cur ? " current" : "") + '"' +
        (cur ? ' aria-current="page"' : "") + ">" + pie(p) + '<span class="sb-label" dir="auto">' + escapeHtml(p.name) + "</span>" +
        (p.review_overdue ? '<span class="dot" title="due for review"></span>' : "") + "</a>";
    }
    var active = (state.projects || []).filter(function (p) { return p.status === "active"; });
    var html = '<div class="sb-group">' + item("inbox", c.inbox) + "</div>" +
      '<div class="sb-group">' + item("today", c.today - c.todayDue, c.todayDue) + item("upcoming") + item("anytime") + item("someday") +
      item("waiting", c.waiting) + "</div>" +
      '<div class="sb-group">' + item("logbook") + "</div>";
    var loose = active.filter(function (p) { return !p.area; });
    if (loose.length) html += '<div class="sb-group">' + loose.map(projItem).join("") + "</div>";
    (state.areas || []).forEach(function (a) {
      var cur = route.view === "area" && route.name === a.name;
      html += '<div class="sb-group"><a href="' + escapeHtml(routeHash({ view: "area", name: a.name })) + '" class="sb-item sb-area' +
        (cur ? " current" : "") + '"' + (cur ? ' aria-current="page"' : "") + ">" + icon("area", "sb-icon") +
        '<span class="sb-label" dir="auto">' + escapeHtml(a.name) + "</span></a>" +
        active.filter(function (p) { return p.area === a.name; }).map(projItem).join("") + "</div>";
    });
    return html;
  }

  function viewTitle(route) {
    if (route.view === "project" || route.view === "area") return route.name;
    return (LIST_META[route.view] || LIST_META.today).label;
  }

  // ---- popovers: When, Move, Quick Find ----

  // A month grid for the When popover; today shows as a star, like Things.
  function calendarGrid(month, today, selected) {
    var first = parseIso(month + "-01");
    var start = new Date(first);
    start.setDate(1 - first.getDay());
    var html = '<div class="cal"><div class="cal-head"><button type="button" class="icon-btn" data-cal="-1" aria-label="Previous month">' +
      icon("chevronLeft") + '</button><span>' + MONTHS[first.getMonth()] + " " + first.getFullYear() +
      '</span><button type="button" class="icon-btn" data-cal="1" aria-label="Next month">' + icon("chevronRight") + "</button></div>" +
      '<div class="cal-grid">' + WEEKDAYS.map(function (w) { return '<span class="cal-wd">' + w.slice(0, 2) + "</span>"; }).join("");
    for (var i = 0; i < 42; i++) {
      var d = new Date(start);
      d.setDate(start.getDate() + i);
      var iso = isoDate(d);
      var cls = "cal-day" + (iso.slice(0, 7) !== month ? " other" : "") + (iso === selected ? " sel" : "");
      if (iso < today) {
        html += '<span class="' + cls + ' past">' + d.getDate() + "</span>";
      } else {
        html += '<button type="button" class="' + cls + '" data-date="' + iso + '">' +
          (iso === today ? icon("star", "i-today") : d.getDate()) + "</button>";
      }
    }
    return html + "</div></div>";
  }

  function whenPopoverHtml(month, today, selected) {
    return '<input type="text" class="pop-input" id="when-input" placeholder="When — try “fri”, “in 3 days”, “oct 3”" autocomplete="off">' +
      '<p class="pop-hint" id="when-hint"></p>' +
      '<button type="button" class="pop-item" data-when="today">' + icon("star", "i-today") + "Today</button>" +
      '<button type="button" class="pop-item" data-when="evening">' + icon("moon", "i-evening") + "This Evening</button>" +
      calendarGrid(month, today, selected) +
      '<button type="button" class="pop-item" data-when="someday">' + icon("box", "i-someday") + "Someday</button>" +
      '<button type="button" class="pop-item muted" data-when="anytime">' + icon("close") + "Clear</button>";
  }

  function moveTargets(state) {
    var out = [{ kind: "inbox", name: "Inbox", label: "Inbox" }];
    var active = (state.projects || []).filter(function (p) { return p.status !== "done"; });
    active.filter(function (p) { return !p.area; }).forEach(function (p) {
      out.push({ kind: "project", name: p.name, label: p.name, project: p });
    });
    (state.areas || []).forEach(function (a) {
      if (a.file) out.push({ kind: "area", name: a.name, label: a.name });
      active.filter(function (p) { return p.area === a.name; }).forEach(function (p) {
        out.push({ kind: "project", name: p.name, label: p.name, project: p, area: a.name });
      });
    });
    return out;
  }

  function movePopoverHtml(state, filter) {
    var q = (filter || "").toLowerCase();
    var targets = moveTargets(state).filter(function (m) { return !q || m.label.toLowerCase().indexOf(q) >= 0; });
    return targets.map(function (m, i) {
      var ic = m.kind === "inbox" ? icon("inbox", "i-inbox") : m.kind === "area" ? icon("area", "i-area") : pie(m.project);
      return '<button type="button" class="pop-item' + (i === 0 ? " active" : "") + (m.area ? " indent" : "") +
        '" data-move-kind="' + m.kind + '" data-move-name="' + escapeHtml(m.name) + '">' + ic +
        '<span dir="auto">' + escapeHtml(m.label) + "</span></button>";
    }).join("") || '<p class="pop-hint">No project matches.</p>';
  }

  // Quick Find: lists, areas and projects by name, then to-dos by text, tag or linked name.
  function quickFind(state, query, today) {
    var q = String(query || "").trim().toLowerCase();
    if (!q) return [];
    var hit = function (s) { return String(s || "").toLowerCase().indexOf(q) >= 0; };
    var out = [];
    LISTS.forEach(function (v) {
      if (hit(LIST_META[v].label)) out.push({ kind: "list", label: LIST_META[v].label, icon: LIST_META[v].icon, route: { view: v }, key: "list|" + v });
    });
    (state.areas || []).forEach(function (a) {
      if (hit(a.name)) out.push({ kind: "area", label: a.name, route: { view: "area", name: a.name }, key: "area|" + a.name });
    });
    (state.projects || []).forEach(function (p) {
      if (hit(p.name)) out.push({ kind: "project", label: p.name, project: p, route: { view: "project", name: p.name }, key: "proj|" + p.name });
    });
    var tags = {};
    (state.todos || []).forEach(function (t) {
      if (!t.done) todoTags(t).forEach(function (g) { if (hit(g)) tags[g] = true; });
    });
    Object.keys(tags).sort().forEach(function (g) {
      out.push({ kind: "tag", label: g, route: { view: "anytime" }, tag: g, key: "tag|" + g });
    });
    var todos = (state.todos || []).filter(function (t) {
      return hit(t.text) || (t.links || []).some(hit) || hit(t.project) || hit(t.area);
    }).sort(function (a, b) { return (a.done ? 1 : 0) - (b.done ? 1 : 0); }).slice(0, 40);
    todos.forEach(function (t) {
      out.push({ kind: "todo", label: t.text, todo: t, route: homeRoute(t, state, today), key: taskKey(t.file, t.line_text) });
    });
    (state.inbox_notes || []).forEach(function (n) {
      if (hit(n.text)) out.push({ kind: "note", label: n.text, route: { view: "inbox" }, key: "note|" + n.file });
    });
    return out;
  }

  function quickFindHtml(results, active) {
    if (!results.length) return "";
    return results.map(function (r, i) {
      var ic = r.kind === "list" ? icon(r.icon, "i-" + r.route.view) : r.kind === "area" ? icon("area", "i-area")
        : r.kind === "project" ? pie(r.project) : r.kind === "tag" ? icon("tag") : r.kind === "note" ? icon("note", "i-note")
        : (r.todo.done ? icon("logbook", "i-logbook") : '<span class="check mini">' + icon("check") + "</span>");
      var sub = r.kind === "todo" ? (r.todo.project || r.todo.area || (r.todo.inbox ? "Inbox" : r.todo.meeting || "")) : r.kind === "tag" ? "tag" : "";
      return '<li class="qf-item' + (i === active ? " active" : "") + '" data-i="' + i + '">' + ic +
        '<span class="qf-label" dir="auto">' + escapeHtml(r.label) + "</span>" +
        (sub ? '<span class="qf-sub" dir="auto">' + escapeHtml(sub) + "</span>" : "") + "</li>";
    }).join("");
  }

  // ---- keyboard ----

  var SHORTCUTS = [
    ["1 – 7", "Inbox, Today, Upcoming, Anytime, Someday, Waiting, Logbook"],
    ["j / ↓ · k / ↑", "Next / previous item"],
    ["Enter", "Open the selected to-do (on a meeting: record it)"],
    ["Esc", "Close the open to-do or popover"],
    ["n or Space", "New To-Do here"],
    ["x", "Complete the selected to-do"],
    ["t · e · s · a", "When: Today · This Evening · Someday · Anytime"],
    ["w", "When… (pick a date, or type “fri”)"],
    ["m", "Move to a project"],
    ["d or Delete", "Delete (5 s to undo)"],
    ["u", "Undo the last delete"],
    ["o", "Open the note in Obsidian"],
    ["/ or f", "Quick Find"],
    ["r", "Record a meeting / stop"],
    ["?", "Show this list"],
  ];

  function shortcutsHtml() {
    return '<table class="shortcuts">' + SHORTCUTS.map(function (s) {
      return "<tr><td><kbd>" + escapeHtml(s[0]) + "</kbd></td><td>" + escapeHtml(s[1]) + "</td></tr>";
    }).join("") + "</table>";
  }

  // Matched on the physical key (e.code), not the typed character, so shortcuts keep working
  // with the keyboard switched to Hebrew (where "j" types "ח").
  var CODE_ACTIONS = {
    KeyJ: "down", KeyK: "up", KeyX: "complete", KeyD: "delete", KeyU: "undo", KeyN: "new", KeyR: "record",
    KeyT: "when:today", KeyE: "when:evening", KeyS: "when:someday", KeyA: "when:anytime", KeyW: "when",
    KeyM: "move", KeyO: "obsidian", KeyF: "search", Space: "new",
  };
  var KEY_ACTIONS = { ArrowDown: "down", ArrowUp: "up", Enter: "open", Delete: "delete", Backspace: "delete" };

  function keyAction(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return null;
    var code = ev.code || "";
    if (code === "Slash") return ev.shiftKey ? "help" : "search";
    if (ev.key === "?") return "help";
    var digit = /^(?:Digit|Numpad)([1-9])$/.exec(code);
    if (digit && !ev.shiftKey) return "list:" + digit[1];
    if (KEY_ACTIONS[ev.key]) return KEY_ACTIONS[ev.key];
    if (!ev.shiftKey && CODE_ACTIONS[code]) return CODE_ACTIONS[code];
    return null;
  }

  function findTodo(state, file, line) {
    return (state.todos || []).filter(function (t) { return t.file === file && t.line_text === line; })[0] || null;
  }

  var api = {
    LISTS: LISTS, LIST_META: LIST_META, CONTEXTS: CONTEXTS,
    escapeHtml: escapeHtml, taskKey: taskKey, isoDate: isoDate, localDateTime: localDateTime, addDays: addDays,
    shortDate: shortDate, deadlineLabel: deadlineLabel, whenLabel: whenLabel, parseWhen: parseWhen, obsidianUrl: obsidianUrl,
    isToday: isToday, listToday: listToday, listUpcoming: listUpcoming, listAnytime: listAnytime, listSomeday: listSomeday,
    listWaiting: listWaiting, listInbox: listInbox, listLogbook: listLogbook, projectTodos: projectTodos,
    groupByProject: groupByProject, tagCounts: tagCounts, byTag: byTag, todoTags: todoTags,
    parseRoute: parseRoute, routeHash: routeHash, sameRoute: sameRoute, homeRoute: homeRoute, newTodoDefaults: newTodoDefaults,
    attentionItems: attentionItems, meetingStatus: meetingStatus, currentEvent: currentEvent, recordingUrl: recordingUrl, eventTime: eventTime,
    todoRow: todoRow, renderView: renderView, sidebarHtml: sidebarHtml, sidebarCounts: sidebarCounts, viewTitle: viewTitle,
    calendarGrid: calendarGrid, whenPopoverHtml: whenPopoverHtml, moveTargets: moveTargets, movePopoverHtml: movePopoverHtml,
    quickFind: quickFind, quickFindHtml: quickFindHtml, shortcutsHtml: shortcutsHtml, keyAction: keyAction, findTodo: findTodo,
    icon: icon, pie: pie,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DashboardLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
