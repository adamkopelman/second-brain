---
name: gtd-setup
description: Use when the user wants to set up, scaffold, initialize, or repair the GTD second-brain vault — creating the folder structure, templates, dashboards, and config. Triggers on "set up the vault", "scaffold", "initialize second brain", "repair the structure", "gtd setup".
---

# GTD Setup

Scaffolds or repairs the vault. Idempotent — it only creates what's missing and never overwrites
existing notes. This skill is the canonical source of the vault structure.

## Steps
1. Determine the vault root (the repo root, or a directory the user names).
2. Run the bundled copier:
   ```
   python3 .claude/skills/gtd-setup/apply.py <vault-root>
   ```
   It prints `created …` / `skipped …` per file and a summary.
3. Report what was created vs already present. If everything was skipped, the vault is intact.
4. Point the user at `30 Resources/GTD System.md` (conventions) and `docs/gtd/obsidian-plugins.md`
   (install Dataview for the live dashboard).

## Notes
- To rebuild a NEW vault elsewhere, copy `.claude/skills/gtd-setup/` (skill + `scaffold/` + `apply.py`)
  into that repo and run the copier there.
- `--force` overwrites existing files — only use it when the user explicitly wants to reset to
  defaults, and confirm first.
- Python 3.9+ with no third-party packages is the only requirement.
