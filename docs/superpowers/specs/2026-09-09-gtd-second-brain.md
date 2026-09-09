# GTD Second Brain — Spec

**Status:** Approved (design decisions from 2026-09-09 session)
**Owner:** adamkopelman (single user)

## Problem

The repo `second-brain` is meant to be a working [GTD](https://gettingthingsdone.com/)
"second brain": a personal system for capturing, clarifying, organizing, reflecting on, and
engaging with everything the user has to do and know. It should be usable both in **Obsidian**
(as a vault) and through **Claude Code** (conversationally), with plain-markdown data that
outlives any single tool.

## Goals

1. A GTD-structured Obsidian vault the user can open and use immediately.
2. Conversational GTD workflows via Claude Code skills (the five GTD steps).
3. Zero-friction capture and a fast "what do I do now" answer.
4. Two dashboards: a live one inside Obsidian, and a shareable HTML snapshot.
5. A terminal CLI for capture/query without opening Claude or Obsidian.
6. Clear docs so the user (and future-them) can run the system.

## Non-goals (v1)

- Multi-user / shared-team features.
- Two-way sync with external task managers (Todoist, Notion) — deferred.
- Mobile-specific tooling beyond what Obsidian mobile already provides.

## Decisions (locked)

- **Vault = repo root.** Built fresh.
- **Structure:** PARA-style folders `00 Inbox`, `10 Projects`, `20 Areas`, `30 Resources`,
  `40 Archive`, plus dedicated `Journal`, `People`, `Meetings`, `_templates`.
- **GTD state in metadata, not folders.** Tasks are markdown checkboxes with:
  - Context tags: `#computer #phone #errands #home #office #anywhere #agenda`
  - Status tags: `#next` (do now), `#waiting` (delegated/blocked), `#someday`
  - Inline fields: `[due:: YYYY-MM-DD]`, `[scheduled:: YYYY-MM-DD]`, `[since:: YYYY-MM-DD]`
  - Project link: `[[Project Name]]`
- **Project frontmatter:** `type: project`, `status: active|someday|done`, `area`, `created`, `review`.
- **Dashboards:** live `Dashboard.md` via the **Dataview** plugin; plus `/gtd-dashboard` publishes
  an HTML **Artifact** snapshot (no plugin needed).
- **Skills:** live in `.claude/skills/`, prefixed `gtd-`, alongside the already-installed
  Superpowers library.
- **SessionStart hook:** read-only bash brief on session open.
- **CLI:** Python 3, standard-library only, `pytest` tests; operates on the vault markdown.
- **External plugins:** Dataview required; Tasks, Calendar, Templater documented as optional.

## Acceptance criteria

- Opening the repo as an Obsidian vault shows populated folders, working templates, and a
  `Dashboard.md` that renders once Dataview is installed.
- Running Claude Code in the repo triggers the SessionStart brief.
- Each of `/gtd-capture`, `/gtd-process-inbox`, `/gtd-next-actions`, `/gtd-weekly-review`,
  `/gtd-dashboard` works end to end against the conventions.
- `brain capture`, `brain next`, `brain inbox`, `brain review` run from the terminal and pass tests.
- README explains setup; `30 Resources/GTD System.md` documents conventions.
