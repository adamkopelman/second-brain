#!/usr/bin/env python3
"""Generate a self-contained dashboard.html from the vault. Read-only, stdlib only."""
from __future__ import annotations
import argparse, datetime as _dt, html, re
from pathlib import Path

CONTENT = ["00 Inbox", "10 Projects", "20 Areas", "Journal", "People", "Meetings"]
CONTEXTS = ["#computer", "#phone", "#errands", "#home", "#office", "#anywhere", "#agenda", "#unknown"]
TASK_RE = re.compile(r"^\s*-\s*\[(?P<m>[ xX])\]\s*(?P<b>.*)$")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)")
FIELD_RE = re.compile(r"\[([a-z][a-z0-9_-]*)::\s*([^\]]*)\]")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

def _clean(body: str) -> str:
    t = FIELD_RE.sub("", body); t = LINK_RE.sub(r"\1", t); t = TAG_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip()

def _iter_task_lines(vault: Path):
    for d in CONTENT:
        base = vault / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                m = TASK_RE.match(line)
                if m:
                    yield m.group("m").lower() == "x", m.group("b")

def collect(vault: Path) -> dict:
    vault = Path(vault)
    inbox = 0
    ib = vault / "00 Inbox"
    if ib.is_dir():
        inbox = len([p for p in ib.glob("*.md") if p.name != "README.md"])
    active = []
    pj = vault / "10 Projects"
    if pj.is_dir():
        for p in sorted(pj.rglob("*.md")):
            if p.name != "README.md" and "status: active" in p.read_text(encoding="utf-8"):
                active.append(p.stem)
    next_by_ctx: dict[str, list[str]] = {}
    waiting, due_soon = [], []
    today = _dt.date.today()
    for done, body in _iter_task_lines(vault):
        if done:
            continue
        tags = ["#" + t for t in TAG_RE.findall(body)]
        fields = {k: v.strip() for k, v in FIELD_RE.findall(body)}
        text = _clean(body)
        if "#waiting" in tags:
            waiting.append(text); continue
        if "#next" in tags:
            sched = fields.get("scheduled")
            if sched:
                try:
                    if _dt.date.fromisoformat(sched) > today:
                        continue
                except ValueError:
                    pass
            ctx = next((c for c in CONTEXTS if c in tags), "#anywhere")
            label = text + (f"  📅 {fields['due']}" if "due" in fields else "")
            next_by_ctx.setdefault(ctx, []).append(label)
            due = fields.get("due")
            if due:
                try:
                    if _dt.date.fromisoformat(due) <= today + _dt.timedelta(days=7):
                        due_soon.append(f"{text} — {due}")
                except ValueError:
                    pass
    return {"inbox": inbox, "active_projects": active, "next_by_context": next_by_ctx,
            "waiting": waiting, "due_soon": due_soon}

def _ul(items):
    return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>" if items else "<p class=empty>None</p>"

def render(data: dict, generated: str) -> str:
    n_next = sum(len(v) for v in data["next_by_context"].values())
    cols = ""
    for ctx, items in sorted(data["next_by_context"].items()):
        cols += f"<h3>{html.escape(ctx)}</h3>{_ul(items)}"
    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>GTD Dashboard</title>
<style>
:root{{color-scheme:light dark}}
body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:1.5rem;background:#fafafa;color:#1a1a1a}}
@media(prefers-color-scheme:dark){{body{{background:#161616;color:#e8e8e8}}}}
h1{{margin:.2rem 0}} .kpis{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}}
.kpi{{flex:1;min-width:120px;border:1px solid #8883;border-radius:12px;padding:1rem;text-align:center}}
.kpi b{{display:block;font-size:1.8rem}} .grid{{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.card{{border:1px solid #8883;border-radius:12px;padding:1rem}} .empty{{color:#8888}}
small{{color:#8888}}
</style></head><body>
<h1>🧠 GTD Dashboard</h1><small>Snapshot generated {html.escape(generated)} · live view: Dashboard.md in Obsidian</small>
<div class=kpis>
<div class=kpi><b>{data['inbox']}</b>inbox</div>
<div class=kpi><b>{len(data['active_projects'])}</b>active projects</div>
<div class=kpi><b>{n_next}</b>next actions</div>
<div class=kpi><b>{len(data['waiting'])}</b>waiting</div>
</div>
<div class=grid>
<div class=card><h2>⚡ Next actions</h2>{cols or '<p class=empty>None</p>'}</div>
<div class=card><h2>⏳ Waiting for</h2>{_ul(data['waiting'])}</div>
<div class=card><h2>📋 Active projects</h2>{_ul(data['active_projects'])}</div>
<div class=card><h2>🔥 Due soon</h2>{_ul(data['due_soon'])}</div>
</div></body></html>"""

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=".")
    ap.add_argument("--out", default="dashboard.html")
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    html_str = render(collect(vault), generated=_dt.date.today().isoformat())
    (vault / a.out).write_text(html_str, encoding="utf-8")
    print(f"wrote {a.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
