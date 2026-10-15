# Running this vault in different harnesses

The system is skills + MCP + plain markdown, so it runs anywhere skills are discovered.

## Claude Code
- Skills: auto-discovered from `.claude/skills/`.
- MCP: `.mcp.json` (server `outlook`, launched from `$OUTLOOK_MCP_BIN`).
- Session brief: auto via the `SessionStart` hook (`.claude/settings.json`).

## opencode
- Skills: opencode discovers `.claude/skills/` natively (also `.opencode/skills`).
- MCP: `opencode.json` (`mcp.outlook`, `command: ["{env:OUTLOOK_MCP_BIN}"]`).
- Session brief: run `/gtd-status` (no hook system needed).

## Claudian (inside Obsidian) — recommended
[Claudian](https://community.obsidian.md/plugins/realclaudian) is an Obsidian community plugin that
embeds a CLI agent (Claude Code / opencode / Codex) in a side panel with this vault as the working
directory — so you drive the whole GTD system without leaving Obsidian.
- Install: Community plugins → "Claudian"; it requires a CLI agent already installed on your machine.
- Skills: it runs the underlying agent, which discovers `.claude/skills/` — all `gtd-*` skills work.
- MCP/brief: inherited from whichever agent Claudian runs (Claude Code → `.mcp.json` + hook;
  opencode → `opencode.json` + `/gtd-status`).
- This is the recommended day-to-day setup: live `Dashboard.md` and skills in one window.

## Any other skills+MCP harness
- Place/point skills at `.claude/skills/`. Configure the Outlook server per that harness's MCP
  format using `$OUTLOOK_MCP_BIN`. Use `/gtd-status` for the brief.

## Air-gapped setup (no internet)

What works offline, what doesn't, and what to bring onto the machine before you cut the network.

### Works offline from a fresh clone
- **The vault** — plain markdown, templates, `Home.canvas`, Obsidian config.
- **Obsidian plugins** — all vendored under `.obsidian/plugins/`; no downloads. Dataview and
  QuickAdd (the two the vault needs) make no network calls in normal use.
- **Scripts** (`scripts/*.py`, `.claude/skills/gtd-setup/apply.py`) — Python standard library only,
  no `pip install`. The dashboard server binds to `127.0.0.1` only.
- **Local dashboard** (`scripts/dashboard_static/`) — no CDNs or web fonts.
- **Meeting transcription** — vendored `whisper.cpp` + `ggml-tiny.bin` (`vendor/whisper-cpp/`).
  Don't pass `--remote-url`. See `docs/gtd/meeting-recording.md`.
- **Outlook** — `vendor/outlook-mcp-rs/outlook-mcp-rs.exe` drives the local Outlook desktop app
  over COM; it reads whatever Outlook has cached.
- **Quick Capture** (`scripts/quick_capture/`) — PowerShell, no network; it only opens the local
  dashboard.

### Needs network unless you change it
- **The `gtd-*` skills and meeting summaries** run inside an AI agent. Claude Code calls the
  Anthropic API, so it won't work air-gapped. Use **opencode with a local model** instead (below).
- **Smart Second Brain** (optional) defaults to OpenAI or Ollama. Point it at a local Ollama, or
  leave it disabled.
- **Remote Whisper** (`--remote-url`) — opt-in only; just don't use it.

### Bring these onto the machine first
The vendored binaries are **Windows x64 only**; on macOS/Linux, offline transcription and Outlook
don't work.

| What | Why |
| --- | --- |
| Obsidian desktop installer | Opens the vault; runs the plugins and meeting recorder |
| Python 3 (python.org installer, "Add python.exe to PATH") | Scripts, dashboard, transcription |
| opencode | Runs the `gtd-*` skills against a local model |
| Ollama + model files | The local model (pull models while still online, e.g. `ollama pull <model>`) |
| Microsoft Outlook, signed in once | Optional — email/calendar via `outlook-mcp-rs` |

Check the clone has every vendored file (Git LFS is not used, so a normal clone or zip is enough);
the sha256 sums are in `vendor/README.md` and `vendor/whisper-cpp/README.md`.

### Run the skills on a local model (opencode + Ollama)
1. Start Ollama (`ollama serve`) and confirm the model is pulled: `ollama list`.
2. Add a local provider to `opencode.json` and select it — replace `<model>` with what you pulled:

   ```json
   {
     "$schema": "https://opencode.ai/config.json",
     "provider": {
       "ollama": {
         "npm": "@ai-sdk/openai-compatible",
         "options": { "baseURL": "http://localhost:11434/v1" },
         "models": { "<model>": {} }
       }
     },
     "model": "ollama/<model>",
     "mcp": {
       "outlook": { "type": "local", "command": ["{env:OUTLOOK_MCP_BIN}"], "enabled": true }
     }
   }
   ```

   opencode loads the `@ai-sdk/openai-compatible` provider package on first use, so run opencode
   once with this config **while still online** to cache it.
3. Run `opencode` in the vault (or Claudian set to opencode) and start with `/gtd-status`.

Expect a small local model to follow the skills less reliably than Claude, especially
`gtd-process-inbox`, `gtd-weekly-review` and `gtd-summarize-meetings`. Use the largest model your
machine runs comfortably and check its edits. Without any agent, everything is still plain
markdown: capture with Quick Capture or QuickAdd, and work the lists in `Dashboard.md`.

### Air-gap checklist
- [ ] Obsidian opens the vault and Dataview renders `Dashboard.md`
- [ ] `python scripts/dashboard_server.py` serves `http://localhost:8787`
- [ ] `python scripts/transcribe_meetings.py .` runs with no `--remote-url`
- [ ] `opencode` answers `/gtd-status` with the network unplugged
- [ ] Smart Second Brain is disabled or pointed at local Ollama

## Principle
Every automatic behavior is also a skill, so no capability is locked to one harness. Claude-only
extras (e.g. publishing the dashboard as an Artifact) are optional bonuses, never the only path.
