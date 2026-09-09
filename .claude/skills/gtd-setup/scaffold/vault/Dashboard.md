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
  const CTX = ["#computer","#phone","#errands","#home","#office","#anywhere","#agenda"];
  const CTX_LABEL = {"#computer":"💻 Computer","#phone":"📞 Phone","#errands":"🚗 Errands","#home":"🏠 Home","#office":"🏢 Office","#anywhere":"🌐 Anywhere","#agenda":"👥 Agenda"};
  const has = (t, tag) => (t.tags ?? []).includes(tag);
  const clean = t => {
    let s = t.text || "";
    s = s.replace(/\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g, "$1");
    s = s.replace(/\[[a-z][a-z0-9_-]*::[^\]]*\]/gi, "");
    s = s.replace(/#[A-Za-z][\w-]*/g, "");
    return esc(s.replace(/\s+/g, " ").trim());
  };
  const dstr = d => { try { return d && d.toFormat ? d.toFormat("LLL d") : String(d).slice(0,10); } catch(e) { return esc(String(d)); } };
  const projOf = t => { try { const o = t.outlinks; if (o && o.length) return esc((o[0].path || String(o[0])).split("/").pop().replace(/\.md$/,"")); } catch(e){} return ""; };

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

  html += `<div class="gtd-grid">`;

  // ---- Next actions by context ----
  const byCtx = {};
  for (const t of nexts) { const c = CTX.find(x => has(t,x)) || "#anywhere"; (byCtx[c] ??= []).push(t); }
  let cols = "";
  for (const c of CTX) {
    const items = byCtx[c]; if (!items || !items.length) continue;
    const li = items.slice(0,12).map(t => {
      const pj = projOf(t); const du = t.due ? ` <span class="gtd-due">📅 ${dstr(t.due)}</span>` : "";
      return `<li>${clean(t)}${pj ? ` <span class="gtd-proj">${pj}</span>` : ""}${du}</li>`; }).join("");
    cols += `<div class="gtd-col"><div class="gtd-col-h">${esc(CTX_LABEL[c] || c)} · ${items.length}</div><ul class="gtd-list">${li}</ul></div>`;
  }
  html += `<div class="gtd-card gtd-span2"><h3>⚡ Next actions — by context</h3>${cols ? `<div class="gtd-cols">${cols}</div>` : `<div class="gtd-empty">No next actions queued. Run /gtd-process-inbox or /gtd-weekly-review.</div>`}</div>`;

  // ---- Due soon ----
  const dueLi = dueSoon.slice(0,12).map(t => {
    const overdue = t.due < today; const pj = projOf(t);
    return `<li>${clean(t)}${pj ? ` <span class="gtd-proj">${pj}</span>` : ""} <span class="${overdue ? "gtd-warn" : "gtd-due"}">${overdue ? "⚠ " : "📅 "}${dstr(t.due)}</span></li>`; }).join("");
  html += `<div class="gtd-card"><h3>🔥 Due soon (7 days)</h3>${dueLi ? `<ul class="gtd-list">${dueLi}</ul>` : `<div class="gtd-empty">Nothing due.</div>`}</div>`;

  // ---- Waiting for ----
  const wLi = waiting.slice(0,12).map(t => {
    const who = projOf(t); const since = t.since ? ` <span class="gtd-since">since ${dstr(t.since)}</span>` : "";
    return `<li>${clean(t)}${who ? ` <span class="gtd-proj">${who}</span>` : ""}${since}</li>`; }).join("");
  html += `<div class="gtd-card"><h3>⏳ Waiting for</h3>${wLi ? `<ul class="gtd-list">${wLi}</ul>` : `<div class="gtd-empty">Not waiting on anyone.</div>`}</div>`;

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

  html += `</div>`;
  const root = dv.el("div", "", { cls: "gtd-root" });
  root.innerHTML = html;
} catch (e) {
  dv.el("div", "Dashboard error: " + (e && e.message ? e.message : e), { cls: "gtd-err" });
}
```
