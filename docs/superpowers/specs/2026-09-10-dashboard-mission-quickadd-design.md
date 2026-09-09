# Dashboard Mission + QuickAdd Actions — Design

**Status:** Approved by user, ready for implementation plan.
**Date:** 2026-09-10

## Problem

`Dashboard.md` is currently read-only: a `dataviewjs` KPI/card grid that shows inbox size, next
actions, waiting-for, due-soon, active projects, and someday/maybe. It answers "what's going on"
but not "why" (no mission/purpose) and gives no way to *act* — adding a task or a new project
still requires leaving Obsidian for a Claude Code slash command. The user wants the dashboard to
be "the frontend of the repo": one screen showing the mission behind the system, and clickable
actions that actually create tasks and projects.

## Goals

1. Show a **Mission** (free-text, user-maintained) and **Pillars** (Areas of Responsibility with
   a one-line purpose each) at the top of the dashboard.
2. Make the dashboard **actionable**: clickable links that capture a task, add a next action to a
   project, or create a new project — without leaving Obsidian.
3. Keep the existing KPI/card-grid behavior intact — this is additive, not a rewrite.
4. Keep the vault self-contained (vendor the one new plugin needed, same as Dataview/Claudian
   today) and keep the `gtd-setup` scaffold in sync with the live vault, per existing repo
   convention (see commit `97a33d9`, "scaffold == root").

## Non-goals

- No new plugin for button styling (Buttons plugin) — plain `obsidian://quickadd` URI links
  suffice and keep plugin count minimal.
- No changes to `Dashboard (lists).md` (plain-table fallback) or the portable
  `/gtd-dashboard` HTML snapshot — both stay read-only summaries; out of scope for this pass.
- No "New Area" capture flow — areas are created rarely; the existing core Templates plugin
  (already enabled) is sufficient for that.

## Design

### 1. Mission & Pillars

- **`Mission.md`** (vault root) — a new, mostly-empty note with a `# Mission` heading and a
  placeholder line, meant for the user to edit directly. No frontmatter needed; it's prose.
- **`_templates/Area.md`** — first template for `20 Areas/`. Frontmatter:
  ```yaml
  ---
  type: area
  purpose: 
  review: {{date:YYYY-MM-DD}}
  ---

  # {{title}}

  **Purpose:** _Why this area matters._
  ```
- **`30 Resources/GTD System.md`** — add an "Area frontmatter" section (mirroring the existing
  "Project frontmatter" section) documenting `type: area` / `purpose:` / `review:`.

### 2. QuickAdd capture flows

Vendor the QuickAdd plugin the same way Dataview and Claudian are vendored today
(`.obsidian/plugins/quickadd/{manifest.json,main.js,styles.css}`, release build, unmodified,
added to `.obsidian/community-plugins.json` in both the live vault and the `gtd-setup` scaffold).

Three QuickAdd choices, configured in `.obsidian/plugins/quickadd/data.json`:

| Choice | Type | Behavior |
|---|---|---|
| **Quick Capture** | Capture | Prompts for text. Appends `- [ ] {text}` to `00 Inbox/README.md`, matching the raw/unprocessed style of `/gtd-capture` — no tags added, stays for `/gtd-process-inbox` to clarify. |
| **New Next Action** | Capture | Prompts for text, then a context suggester (`#computer #phone #errands #home #office #anywhere #agenda`), then a suggester listing files in `10 Projects/` (with a "— none, use inbox —" option). Inserts `- [ ] {text} #next #{context}` under the target project's `## Next actions` heading (or appends to `00 Inbox/README.md` if no project chosen). |
| **New Project** | Template | Prompts for title, then an area suggester listing files in `20 Areas/`. Creates `10 Projects/{title}.md` from `_templates/Project.md`, filling `created` = today, `review` = today + 7 days, `area` = the chosen area (wikilinked). |

Each choice is triggered from inside `Dashboard.md` via a plain markdown link using QuickAdd's
URI scheme: `obsidian://quickadd?choice=<Choice Name>&vault=<Vault Name>` — no second plugin
needed for clickability.

### 3. `Dashboard.md` layout changes

Additive only — the existing `dataviewjs` KPI/card-grid block is untouched. New content, top of
file, before the existing block:

1. `![[Mission]]` transclusion.
2. A "🎯 Pillars" card: `dataviewjs` over `dv.pages('"20 Areas"').where(p => p.type === "area")`,
   rendering each area's `purpose` field plus a count of active projects whose `area` links to it.
3. An "➕ Actions" row directly under the KPI tiles, before the "Next actions by context" card:
   three markdown links (Quick Capture / New Next Action / New Project) using the URI scheme
   above.

`Home.canvas` — the "⚡ Capture & Engage" text node gains a line: `- [[Mission]] — why this exists`
and a mention of the new dashboard actions.

### 4. Mirroring & docs

- `Mission.md`, `_templates/Area.md`, updated `Dashboard.md`, updated `Home.canvas`, updated
  `30 Resources/GTD System.md` all get copied into
  `.claude/skills/gtd-setup/scaffold/vault/...` at the matching relative path, so `/gtd-setup`
  reproduces them for new vaults (matching the existing scaffold==root pattern).
- `.obsidian/community-plugins.json` gains `"quickadd"` in both the live vault and the scaffold
  (scaffold already lists plugin IDs without vendoring binaries — same pattern continues; the
  actual `main.js`/`manifest.json`/`styles.css` are vendored only at the live-vault root, not
  inside the scaffold, matching how Dataview/Claudian/Smart Second Brain are handled today).
- `docs/gtd/obsidian-plugins.md` — QuickAdd moves from absent to a documented, required entry
  (dashboard actions depend on it), with the URI-link mechanism explained.

## Testing approach

This is Obsidian-plugin configuration, not application code — there is no automated test runner
for QuickAdd `data.json` correctness or URI-link behavior. Each capture-flow task in the
implementation plan ends with a **manual verification step**: open the vault in Obsidian, reload
QuickAdd (or restart Obsidian) after editing `data.json`, click the corresponding link on
`Dashboard.md`, and confirm the resulting file/line matches the spec exactly (right file, right
heading, right tags, right frontmatter). Existing automated coverage that *is* testable — the
`gtd-setup` `apply.py` idempotency tests (`tests/test_apply.py`) and the portable dashboard
generator — must still pass after the scaffold mirroring changes.

## Open risk

QuickAdd's `data.json` schema must be hand-authored (no running Obsidian instance to configure it
interactively during planning). The plan should write it directly against QuickAdd's documented
choice schema (Capture / Template choice types) and rely on the manual verification steps above
to catch any mismatch, fixing forward if the shape is wrong.
