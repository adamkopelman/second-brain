# Dashboards

| | Live (`Dashboard.md`) | Portable (`dashboard.html`) |
| --- | --- | --- |
| Engine | Dataview plugin, in Obsidian | `scripts/build_dashboard.py` via `/gtd-dashboard` |
| Updates | live as you edit | point-in-time snapshot |
| Needs | Obsidian + Dataview | nothing (opens in a browser) |
| Use for | daily driving | sharing / any harness / no Obsidian |

Generate the snapshot: `/gtd-dashboard`, or `python3 scripts/build_dashboard.py . --out dashboard.html`.
It shows KPIs (inbox / active projects / next actions / waiting), next actions by context,
waiting-for, active projects, and items due within 7 days. Read-only.
