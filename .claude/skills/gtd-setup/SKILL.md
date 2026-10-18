---
name: gtd-setup
description: Use when the user wants to set up, scaffold, initialize, or repair the GTD second-brain vault — creating the folder structure, templates, dashboards, and config. Triggers on "set up the vault", "scaffold", "initialize second brain", "repair the structure", "gtd setup".
---

# GTD Setup

Scaffolds or repairs the vault. Idempotent — it only creates what's missing and never overwrites
existing notes. This skill is the canonical source of the vault structure.

## Steps
1. Determine the vault root (the repo root, or a directory the user names).
2. If the vault is a clone of this repo, make sure the optional components (Obsidian plugins,
   whisper.cpp, outlook-mcp-rs, Quick Capture) are checked out — they are git submodules:
   ```
   git submodule update --init            # all of them
   git submodule update --init .obsidian/plugins/dataview .obsidian/plugins/quickadd   # or just some
   ```
   `git submodule status` shows a leading `-` for any that are not checked out. Every submodule is
   optional; skip the ones the user doesn't want (see `docs/gtd/portability.md`).
3. Run the bundled copier:
   ```
   python3 .claude/skills/gtd-setup/apply.py <vault-root>
   ```
   It prints `created …` / `skipped …` per file and a summary. Besides the vault scaffold, it
   installs the vault's plugin presets from `scaffold/plugin-data/<id>/data.json` (Dataview with
   JavaScript queries on; QuickAdd's three capture/project choices) into each plugin that is
   installed, and names any plugin that isn't (`plugin not installed, preset not applied: …`) —
   re-run it after checking out that submodule or installing the plugin from Obsidian.
4. Report what was created vs already present. If everything was skipped, the vault is intact.
5. Point the user at `30 Resources/GTD System.md` (conventions) and `docs/gtd/obsidian-plugins.md`
   (Dataview and QuickAdd power the live, clickable dashboard). For offline meeting transcription
   the Whisper model is a separate download: `vendor/whisper-cpp/download-model.ps1`.

## Notes
- To rebuild a NEW vault elsewhere, copy `.claude/skills/gtd-setup/` (skill + `scaffold/` + `apply.py`)
  into that repo and run the copier there.
- `--force` overwrites existing files (plugin presets included) — only use it when the user
  explicitly wants to reset to defaults, and confirm first.
- Python 3.9+ with no third-party packages is the only requirement.
