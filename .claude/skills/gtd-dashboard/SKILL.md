---
name: gtd-dashboard
description: Use when the user wants a visual dashboard of their GTD second brain as a shareable HTML page they can open in a browser. Triggers on "dashboard", "show me my system", "gtd overview", "build my dashboard".
---

# GTD Dashboard (portable HTML snapshot)

Generates a self-contained `dashboard.html` from the vault — opens in any browser, no plugin, works
in any harness. Complements the live `Dashboard.md` (Obsidian + Dataview).

## Steps
1. Run: `python3 scripts/build_dashboard.py . --out dashboard.html`
2. Tell the user the file is at `dashboard.html` and how to open it (double-click / `open`).
3. (Claude Code only, optional) If the user wants a shareable link, additionally load the
   `artifact-design` skill and publish the same HTML as an Artifact. Skip this in other harnesses.

## Rules
- Read-only; the generator never modifies notes.
- It's a point-in-time snapshot — the live view is `Dashboard.md`. Numbers come only from the files.
