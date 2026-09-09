# Dashboards

Three views, same data:

| | Live (`Dashboard.md`) | Board (`Home.canvas`) | Portable (`dashboard.html`) |
| --- | --- | --- | --- |
| Engine | Dataview JS (KPI tiles + card grid) | Obsidian Canvas (core) | `scripts/build_dashboard.py` via `/gtd-dashboard` |
| Updates | live as you edit | live embeds | point-in-time snapshot |
| Needs | Obsidian + Dataview (JS on) | Obsidian | nothing (opens in a browser) |
| Use for | daily driving | spatial launchpad | sharing / any harness / no Obsidian |

`Dashboard.md` is a visual command center: a KPI tile row (inbox / projects / next / waiting / due)
over a responsive grid of cards — next actions grouped by context, due-soon, waiting-for, active
projects (with status pills and a "no next action" flag), and someday. `Dashboard (lists).md` is a
plain-Dataview fallback (no JavaScript) if you prefer tables. `Home.canvas` embeds the live
dashboard next to link-cards for capture / organize / reflect.

Generate the snapshot: `/gtd-dashboard`, or `python3 scripts/build_dashboard.py . --out dashboard.html`.
It shows KPIs (inbox / active projects / next actions / waiting), next actions by context,
waiting-for, active projects, and items due within 7 days. Read-only.
