# GTD Second Brain — Spec

**Status:** Approved (design decisions from 2026-09-09 session, revised after review)
**Owner:** adamkopelman (single user)

## Problem

The repo `second-brain` is a working [GTD](https://gettingthingsdone.com/) "second brain": a
personal system for capturing, clarifying, organizing, reflecting on, and engaging with everything
the user has to do and know. It must be usable in **Obsidian** (as a vault) and through **any
skills+MCP agent harness** — Claude Code, opencode, and others — with plain-markdown data that
outlives any single tool.

## Goals

1. A GTD-structured Obsidian vault the user can open and use immediately.
2. Conversational GTD workflows as **portable skills** (the five GTD steps).
3. A single **setup skill** that can scaffold or repair the whole vault from nothing.
4. Zero-friction capture and a fast "what do I do now" answer.
5. Two dashboards: a live one inside Obsidian, and a portable self-contained HTML snapshot.
6. Integration with the user's **`outlook-mcp-rs`** MCP server for email/calendar GTD flows.
7. Clear docs so the user (and future-them) can run the system in any supported harness.

## Cross-harness portability (hard requirement)

- **Skills are the primary interface.** Skills live in `.claude/skills/` — discovered natively by
  Claude Code, opencode, and **Claudian** (the Obsidian community plugin that hosts Claude Code /
  opencode / Codex in a side panel, vault as working directory). No skill may depend on a
  Claude-Code-only capability to function.
- **Anything a harness does "by default" must also exist as a skill.** Example: the session-open
  status brief is the `gtd-status` skill; the Claude Code `SessionStart` hook is only an optional
  auto-trigger that calls the same logic.
- **No Claude-only runtime in core flows.** The portable dashboard is a static `dashboard.html`
  produced by a stdlib script — not a Claude Artifact. (Publishing an Artifact is an optional
  Claude-Code-only enhancement, never the only path.)
- **MCP configured for each harness:** `.mcp.json` (Claude Code) and `opencode.json` (opencode).
- **`AGENTS.md`** at the repo root gives harness-neutral operating instructions.

## Non-goals (v1)

- Multi-user / shared-team features.
- Two-way sync with non-Outlook task managers (Todoist, Notion).
- A standalone CLI (dropped — skills cover terminal-free operation portably).
- Making the Outlook MCP work on non-Windows / without classic Outlook (it degrades gracefully).

## Decisions (locked)

- **Vault = repo root.** Built fresh; the committed vault is the output of running `gtd-setup`.
- **Shipping model = hybrid:** repo ships pre-scaffolded AND `gtd-setup` idempotently creates
  anything missing (canonical source of the scaffold; never overwrites existing files).
- **Structure:** PARA-style folders `00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`,
  `40 Archive`, plus dedicated `Journal`, `People`, `Meetings`, `_templates`.
- **GTD state in metadata, not folders.** Tasks are markdown checkboxes with:
  - Context tags: `#computer #phone #errands #home #office #anywhere #agenda`
  - Status tags: `#next` (do now), `#waiting` (delegated/blocked), `#someday`
  - Inline fields: `[due:: YYYY-MM-DD]`, `[scheduled:: YYYY-MM-DD]`, `[since:: YYYY-MM-DD]`
  - Project link: `[[Project Name]]`
- **Project frontmatter:** `type: project`, `status: active|someday|done`, `area`, `created`, `review`.
- **Skills (all in `.claude/skills/`, prefixed `gtd-`):** `gtd-setup`, `gtd-capture`,
  `gtd-process-inbox`, `gtd-next-actions`, `gtd-weekly-review`, `gtd-status`, `gtd-dashboard`,
  `gtd-outlook`. Alongside the already-installed Superpowers library (untouched).
- **Dashboards:** live `Dashboard.md` via the Dataview plugin; portable `dashboard.html` via
  `scripts/build_dashboard.py`.
- **Outlook:** `outlook-mcp-rs` (Windows, stdio local mode, no auth, 26 tools) wired via env-var
  binary path in both harness MCP configs; `gtd-outlook` skill drives email→inbox and
  calendar→review flows.
- **SessionStart hook:** optional Claude-Code-only auto-trigger for `gtd-status`; read-only.
- **Supported external tools:** **Claudian** (recommended harness — run the vault's skills from
  inside Obsidian) and **Smart Second Brain** (optional plugin — semantic/RAG search over notes,
  complementing Dataview's structured queries). Both optional; documented, not required.
- **Borrowed enhancements (optional phase):** a `gtd-maintain` skill (flag projects with no next
  action, stale waiting-for, propose archives) that can be run on a schedule per harness — an idea
  adapted from existing second-brain skill-packs. We stay bespoke; we do not layer another
  second-brain skill-pack on top (competing conventions would cause skill mis-triggering).

## Acceptance criteria

- Running `gtd-setup` in an empty directory produces a complete, openable vault; running it again
  changes nothing (idempotent).
- Opening the repo as an Obsidian vault shows populated folders, working templates, and a
  `Dashboard.md` that renders once Dataview is installed.
- Every skill works in both Claude Code and opencode (skills contain no harness-only dependency).
- `/gtd-status` prints the brief in any harness; the Claude Code hook shows the same on session open.
- `scripts/build_dashboard.py` writes a valid self-contained `dashboard.html` from the vault.
- With `outlook-mcp-rs` configured on a Windows machine, `/gtd-outlook` can pull flagged email into
  `00 Inbox/` and surface calendar during the weekly review; with it absent, everything else works.
- README + `AGENTS.md` + `docs/gtd/*` explain setup for Claude Code and opencode.
