# Superpowers Skills

This directory vendors the **Superpowers** core skills library for Claude Code —
a collection of workflow skills for TDD, systematic debugging, planning, code
review, and collaboration patterns.

Each subdirectory is a skill with a `SKILL.md` (name + description frontmatter)
that Claude Code auto-discovers. They become available via the `Skill` tool and
as `/<skill-name>` slash commands.

## Skills included

| Skill | Purpose |
| --- | --- |
| `brainstorming` | Turn ideas into designs/specs through collaborative dialogue before building |
| `writing-plans` | Write implementation plans |
| `executing-plans` | Execute an approved plan |
| `test-driven-development` | Red/green/refactor TDD workflow |
| `systematic-debugging` | Root-cause debugging instead of guess-and-check |
| `verification-before-completion` | Verify work is actually done before claiming completion |
| `requesting-code-review` | Request a structured code review |
| `receiving-code-review` | Act on code review feedback |
| `subagent-driven-development` | Drive development through dispatched subagents |
| `dispatching-parallel-agents` | Fan out work across parallel agents |
| `using-git-worktrees` | Use git worktrees for isolated work |
| `finishing-a-development-branch` | Wrap up and land a development branch |
| `writing-skills` | Author new skills |
| `using-superpowers` | Meta-skill for using this library |

## Source & license

- Upstream: <https://github.com/obra/superpowers>
- Version: `6.3.0`
- Vendored from commit `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`
- License: MIT (Copyright (c) 2025 Jesse Vincent) — see `LICENSE` in this directory.

Only the `skills/` portion of the upstream project is vendored here (not the
plugin manifests, hooks, or tests). To update, re-copy the `skills/` directory
from a newer upstream tag and bump the version/commit recorded above.
