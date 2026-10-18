# Vendored binaries

Neither binary is committed to this repo. Both are Windows x86-64 only.

## whisper-cpp (optional git submodule) → [adamkopelman/whisper-cpp](https://github.com/adamkopelman/whisper-cpp)
Unmodified whisper.cpp `b4938` CPU build from **[ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)**
(MIT), used by `scripts/transcribe_meetings.py` for fully offline meeting transcription.
- **The model is not in git.** Download it once (~74 MB, SHA-256 verified):
  `powershell -ExecutionPolicy Bypass -File vendor\whisper-cpp\download-model.ps1`
  (or `sh vendor/whisper-cpp/download-model.sh`). It saves `vendor/whisper-cpp/models/ggml-tiny.bin`
  (multilingual) from https://huggingface.co/ggerganov/whisper.cpp — the path
  `transcribe_meetings.py` uses by default; that folder is git-ignored inside the submodule.
- Air-gapped machine: run the script (or download `ggml-tiny.bin` by hand) on a connected machine and
  copy the file to the same path.
- Details, hashes and how to update: the submodule's `README.md`.

## outlook-mcp-rs (downloaded, not a submodule)
`outlook-mcp-rs.exe`, the MCP server that drives classic Outlook on Windows, from the GitHub releases
of **[adamkopelman/outlook-mcp-rs](https://github.com/adamkopelman/outlook-mcp-rs)** (MIT).
- **Get it:** `/gtd-setup` (`python .claude/skills/gtd-setup/apply.py .`) downloads it on Windows, or
  run `powershell -ExecutionPolicy Bypass -File vendor\outlook-mcp-rs\download-outlook-mcp-rs.ps1`
  (or `sh vendor/outlook-mcp-rs/download-outlook-mcp-rs.sh`). Either way it fetches release
  **v0.3.0**, checks SHA-256 `b033325029562cac858551052ce6870010ecf8c9325206cf0233f45212619048` and
  saves `vendor/outlook-mcp-rs/outlook-mcp-rs.exe` (git-ignored). An exe already there is left alone,
  so you can drop in your own build; `-Force` / `--force` replaces it with v0.3.0.
- **Use:** set `OUTLOOK_MCP_BIN` to its absolute path (`download-outlook-mcp-rs.ps1 -SetUserEnv` does
  it, or `setx OUTLOOK_MCP_BIN "<full path>"`); both `.mcp.json` and `opencode.json` launch it, and the
  local dashboard falls back to that path. Requires Outlook running and signed in. See
  `docs/gtd/outlook.md`.
- v0.3.0 is the latest release; its MCP date filters misread dates on day-first Windows locales
  ([issue #1](https://github.com/adamkopelman/outlook-mcp-rs/issues/1), fixed on upstream `main` after
  that release). Build `main` (`cargo build --release`) and put that exe here if you need the fix.
- **Updating** to a newer release: change the version and SHA-256 in both download scripts and in
  `.claude/skills/gtd-setup/apply.py` (a test checks they agree), then re-run with `-Force`.
