# Obsidian community plugins (git submodules)

Each plugin folder here is an **optional git submodule**, so the vault repo stays small and you take
only the plugins you want. `git clone --recurse-submodules` checks them all out; in an existing clone
run `git submodule update --init` (all) or `git submodule update --init .obsidian/plugins/<id>` (one).
All of them are already enabled in `.obsidian/community-plugins.json`; Obsidian just skips one that
isn't checked out.

The third-party plugins are **unmodified upstream release builds** (byte-identical to the release
assets). Upstream repositories commit only sources and ship the built `main.js` as a release asset,
so they can't be used as the plugin folder directly; each `*-dist` repo holds exactly the release
files plus the upstream license, and its README credits and links the original project.

| Plugin | id (folder) | Version | Submodule repository | Upstream | License |
| --- | --- | --- | --- | --- | --- |
| Dataview | `dataview` | 0.5.70 | [obsidian-dataview-dist](https://github.com/adamkopelman/obsidian-dataview-dist) | https://github.com/blacksmithgu/obsidian-dataview | MIT |
| QuickAdd | `quickadd` | 2.25.0 | [obsidian-quickadd-dist](https://github.com/adamkopelman/obsidian-quickadd-dist) | https://github.com/chhoumann/quickadd | MIT |
| Claudian | `realclaudian` | 2.2.6 | [obsidian-claudian-dist](https://github.com/adamkopelman/obsidian-claudian-dist) | https://github.com/YishenTu/claudian | MIT |
| Smart Second Brain | `smart-second-brain` | 2.0.5 | [obsidian-smart-second-brain-dist](https://github.com/adamkopelman/obsidian-smart-second-brain-dist) | https://github.com/s2b-dev/smart-second-brain | MIT |
| Record Meeting | `record-meeting` | 1.0.0 | [obsidian-record-meeting](https://github.com/adamkopelman/obsidian-record-meeting) | — written for this vault | — |

(Dataview's 0.5.70 release ships a `manifest.json` that still reads 0.5.68.)

**Settings:** the vault's presets — Dataview with JavaScript queries on, QuickAdd's three choices —
live in `.claude/skills/gtd-setup/scaffold/plugin-data/` and are copied into the plugin folders by
`python .claude/skills/gtd-setup/apply.py .` (only into installed plugins, never over your settings).
Each plugin repo git-ignores `data.json`, so your settings and API keys stay local.

**Updating:** `git submodule update --remote .obsidian/plugins/<id>` picks up a newer commit of that
repo (see its README for how a new upstream release gets in), then commit the new pointer here. Only
Dataview and QuickAdd are needed by the dashboard; Claudian, Smart Second Brain and Record Meeting are
optional (see `docs/gtd/obsidian-plugins.md`). Instead of a submodule you can always install a plugin
from Settings → Community plugins.
