---
type: dashboard
cssclasses:
  - dashboard
---

# 🧠 Second Brain

> Visual command center. Needs the **Dataview** plugin with **JavaScript queries enabled**
> (already on in this vault's config). Prefer plain tables? See `Dashboard (lists).md`.
> Portable snapshot outside Obsidian: `/gtd-dashboard`.

```dataviewjs
try {
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const today = dv.date("today");
  const CTX = ["#computer","#phone","#errands","#home","#office","#anywhere","#agenda","#unknown"];
  const CTX_LABEL = {"#computer":"💻 Computer","#phone":"📞 Phone","#errands":"🚗 Errands","#home":"🏠 Home","#office":"🏢 Office","#anywhere":"🌐 Anywhere","#agenda":"👥 Agenda","#unknown":"❓ Unknown"};
  const has = (t, tag) => (t.tags ?? []).includes(tag);
  const dstr = d => { try { return d && d.toFormat ? d.toFormat("LLL d") : String(d).slice(0,10); } catch(e) { return esc(String(d)); } };

  // ---- collect ----
  const folders = ["00 Inbox","10 Projects","20 Areas","Journal","People","Meetings"];
  let tasks = [];
  for (const f of folders) {
    let pages; try { pages = dv.pages(`"${f}"`); } catch(e) { continue; }
    for (const p of pages) { if (p.file.name === "README") continue; for (const t of (p.file.tasks ?? [])) tasks.push(t); }
  }
  const open    = tasks.filter(t => !t.completed);
  const nexts   = open.filter(t => has(t,"#next") && !has(t,"#waiting") && (!t.scheduled || t.scheduled <= today));
  const waiting = open.filter(t => has(t,"#waiting"));
  const dueSoon = open.filter(t => t.due && t.due <= today.plus({days:7})).sort(t => t.due);

  const projects = dv.pages('"10 Projects"').where(p => p.type === "project");
  const active   = projects.where(p => p.status === "active");
  const someday  = projects.where(p => p.status === "someday");
  const inbox    = dv.pages('"00 Inbox"').where(p => p.file.name !== "README");
  const stuck    = active.where(p => !Array.from(p.file.tasks ?? []).some(t => !t.completed && has(t,"#next")));

  // ---- KPI tiles ----
  const tiles = [["📥",inbox.length,"Inbox","in"],["📋",active.length,"Projects","pr"],["⚡",nexts.length,"Next","nx"],["⏳",waiting.length,"Waiting","wa"],["🔥",dueSoon.length,"Due ≤7d","du"]];
  let html = `<div class="gtd-kpis">` + tiles.map(([e,n,l,c]) =>
    `<div class="gtd-kpi gtd-${c}"><div class="gtd-kpi-n">${n}</div><div class="gtd-kpi-l">${e} ${esc(l)}</div></div>`).join("") + `</div>`;

  // ---- Quick actions (QuickAdd) ----
  const vaultName = encodeURIComponent(dv.app.vault.getName());
  const qa = (choice) => `obsidian://quickadd?choice=${encodeURIComponent(choice)}&vault=${vaultName}`;
  html += `<div class="gtd-actions">` +
    `<a class="gtd-action-btn" href="${qa("Quick Capture")}">📥 Quick Capture</a>` +
    `<a class="gtd-action-btn" href="${qa("New Next Action")}">⚡ New Next Action</a>` +
    `<a class="gtd-action-btn" href="${qa("New Project")}">📋 New Project</a>` +
    `</div>`;

  html += `<div class="gtd-grid">`;

  // ---- Next actions by context (real interactive checkboxes, filled in after render) ----
  const taskListTargets = []; // [elementId, tasks][]
  const byCtx = {};
  for (const t of nexts) { const c = CTX.find(x => has(t,x)) || "#anywhere"; (byCtx[c] ??= []).push(t); }
  let cols = "";
  for (const c of CTX) {
    const items = byCtx[c]; if (!items || !items.length) continue;
    const id = `gtd-tl-${c.slice(1)}`;
    taskListTargets.push([id, items.slice(0,12)]);
    cols += `<div class="gtd-col"><div class="gtd-col-h">${esc(CTX_LABEL[c] || c)} · ${items.length}</div><div class="gtd-tasklist" id="${id}"></div></div>`;
  }
  html += `<div class="gtd-card gtd-span2"><h3>⚡ Next actions — by context</h3>${cols ? `<div class="gtd-cols">${cols}</div>` : `<div class="gtd-empty">No next actions queued. Run /gtd-process-inbox or /gtd-weekly-review.</div>`}</div>`;

  // ---- Due soon ----
  html += `<div class="gtd-card"><h3>🔥 Due soon (7 days)</h3>${dueSoon.length ? `<div class="gtd-tasklist" id="gtd-tl-due"></div>` : `<div class="gtd-empty">Nothing due.</div>`}</div>`;
  if (dueSoon.length) taskListTargets.push(["gtd-tl-due", dueSoon.slice(0,12)]);

  // ---- Waiting for ----
  html += `<div class="gtd-card"><h3>⏳ Waiting for</h3>${waiting.length ? `<div class="gtd-tasklist" id="gtd-tl-waiting"></div>` : `<div class="gtd-empty">Not waiting on anyone.</div>`}</div>`;
  if (waiting.length) taskListTargets.push(["gtd-tl-waiting", waiting.slice(0,12)]);

  // ---- Active projects ----
  let pRows = "";
  for (const p of active) {
    const rev = p.review ? dv.date(p.review) : null; const overdue = rev && rev <= today;
    const isStuck = !Array.from(p.file.tasks ?? []).some(t => !t.completed && has(t,"#next"));
    const badge = rev ? `<span class="gtd-pill ${overdue ? "due" : "ok"}">review ${dstr(rev)}</span>` : "";
    const warn = isStuck ? `<span class="gtd-pill due">no next action</span>` : "";
    pRows += `<div class="gtd-pcard"><span><a class="internal-link" href="${esc(p.file.name)}">${esc(p.file.name)}</a>${p.area ? ` <span class="gtd-since">${esc(String(p.area).replace(/\[\[|\]\]/g,""))}</span>` : ""}</span><span>${warn} ${badge}</span></div>`;
  }
  html += `<div class="gtd-card gtd-span2"><h3>📋 Active projects · ${active.length}${stuck.length ? ` <span class="gtd-warn">(${stuck.length} stuck)</span>` : ""}</h3>${pRows || `<div class="gtd-empty">No active projects.</div>`}</div>`;

  // ---- Someday ----
  const sLi = someday.slice(0,15).map(p => `<li><a class="internal-link" href="${esc(p.file.name)}">${esc(p.file.name)}</a></li>`).join("");
  html += `<div class="gtd-card"><h3>💤 Someday / Maybe · ${someday.length}</h3>${sLi ? `<ul class="gtd-list">${sLi}</ul>` : `<div class="gtd-empty">Nothing parked.</div>`}</div>`;

  // ---- Shortcuts (static reference — the repo's slash commands) ----
  const SHORTCUTS = [
    ["/gtd-capture", "Quickly capture a thought/task to the inbox"],
    ["/gtd-process-inbox", "Clarify and file everything in the inbox"],
    ["/gtd-next-actions", "What can I do right now, by context/energy"],
    ["/gtd-status", "Brief status: inbox size, projects, reviews due"],
    ["/gtd-weekly-review", "Run the full weekly review ritual"],
    ["/gtd-maintain", "Health check: stuck projects, stale waiting-for"],
    ["/gtd-outlook", "Pull flagged email / calendar into the system"],
    ["/gtd-dashboard", "Build a portable dashboard.html snapshot"],
    ["/gtd-setup", "Scaffold or repair the vault structure"],
  ];
  const shLi = SHORTCUTS.map(([cmd, desc]) => `<li><code>${esc(cmd)}</code> — ${esc(desc)}</li>`).join("");
  html += `<div class="gtd-card gtd-span2"><h3>⌨️ Shortcuts</h3><ul class="gtd-list">${shLi}` +
    `<li><code>Ctrl/Cmd+Shift+T</code> — New next action, from anywhere (QuickAdd hotkey)</li></ul></div>`;

  html += `</div>`;
  const root = dv.el("div", "", { cls: "gtd-root" });
  root.innerHTML = html;

  // Real interactive checkboxes (dv.api.taskList mounts Obsidian's own task
  // renderer — checking one actually toggles the source file, unlike plain
  // <li> text). Rendered after innerHTML so the placeholder divs exist to
  // render into.
  for (const [id, items] of taskListTargets) {
    const target = root.querySelector("#" + id);
    if (target) await dv.api.taskList(items, false, target, dv.component, dv.currentFilePath);
  }

  // Raw anchors injected via innerHTML never get Obsidian's own link-click
  // interception (that only runs on links produced by its markdown renderer),
  // so a plain href="obsidian://..." falls through to a same-window navigation
  // attempt that resolves to nothing. Firing window.open() from a real click
  // handler routes it through Electron's external-URL handling instead, which
  // Obsidian does intercept and dispatch to its registerObsidianProtocolHandler.
  root.querySelectorAll(".gtd-action-btn").forEach(a => {
    a.addEventListener("click", evt => {
      evt.preventDefault();
      window.open(a.getAttribute("href"));
    });
  });
} catch (e) {
  dv.el("div", "Dashboard error: " + (e && e.message ? e.message : e), { cls: "gtd-err" });
}
```
