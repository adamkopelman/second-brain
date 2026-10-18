# Vendored binaries (git submodules)

Both folders are **optional git submodules** (`git submodule update --init vendor/<name>`), so the
vault repo itself carries no executables. Both are Windows x86-64 only.

## whisper-cpp → [adamkopelman/whisper-cpp](https://github.com/adamkopelman/whisper-cpp)
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

## outlook-mcp-rs → [adamkopelman/outlook-mcp-rs-bin](https://github.com/adamkopelman/outlook-mcp-rs-bin)
The `outlook-mcp-rs.exe` release binary (v0.3.0) of
**[adamkopelman/outlook-mcp-rs](https://github.com/adamkopelman/outlook-mcp-rs)** (MIT), an MCP server
that drives classic Outlook on Windows.
- **Use:** set `OUTLOOK_MCP_BIN` to `vendor\outlook-mcp-rs\outlook-mcp-rs.exe`'s absolute path; both
  `.mcp.json` and `opencode.json` launch it, and the local dashboard falls back to that path. Requires
  Outlook running and signed in. See `docs/gtd/outlook.md`.
- v0.3.0's MCP date filters misread dates on day-first Windows locales (fixed on upstream `main`, not
  yet released) — the submodule's README says how to use a newer build.
