# Vendored: whisper.cpp (Windows x64 CPU build)

Local, fully-offline speech-to-text used by `scripts/transcribe_meetings.py` (and, through it, the
`record-meeting` Obsidian plugin and the `gtd-transcribe-meeting` skill). Committed so the vault is
self-contained for air-gapped machines — no `pip install openai-whisper`, no network, no ffmpeg.

- **Source:** https://github.com/ggml-org/whisper.cpp (release `b4938`, CPU-only Windows x64 build:
  `whisper-bin-x64.zip`)
- **Model:** https://huggingface.co/ggerganov/whisper.cpp `ggml-tiny.bin` (~74MB, **multilingual** —
  swapped in for `ggml-tiny.en.bin` because the vault's real meetings are usually in Hebrew, which an
  English-only model architecturally cannot transcribe; still well under GitHub's 100MB hard
  file-size limit, so no Git LFS needed).
- **Files:** `whisper-cli.exe` + `whisper.dll`, `ggml.dll`, `ggml-base.dll`, and all `ggml-cpu-*.dll`
  variants (the exe auto-detects the running CPU's feature set and loads the matching one — keep all
  of them since the machine this runs on may differ from the machine that vendored these files).
  `SDL2.dll`/`llama.dll`/`parakeet*` from the same release zip are unrelated demo-tool dependencies
  and were intentionally **not** vendored.
- **Platform:** Windows x86-64 only. `scripts/transcribe_meetings.py` fails clearly (not silently) if
  `--remote-url` isn't given and this binary isn't present/runnable — see that script's `main()`.
- **sha256 (whisper-cli.exe):** `800a0fd754afa75e109c7248286ad735670fb6b23d92ca5d12604647ef638a65`
- **sha256 (ggml-tiny.bin):** `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`
- **Usage:** `whisper-cli.exe -m models/ggml-tiny.bin -f <audio> -oj -of <out> -np -l auto` —
  `-l auto` asks whisper.cpp to detect each recording's language itself, rather than assuming
  English — see `scripts/transcribe_meetings.py::transcribe_local` for the exact invocation.
- **Updating:** download a newer `whisper-bin-x64.zip` from
  https://github.com/ggml-org/whisper.cpp/releases and repeat the file list above; swap the model for
  a different `ggml-*.bin` from https://huggingface.co/ggerganov/whisper.cpp if you want better
  accuracy and don't mind a bigger repo (anything ≤~95MB is still LFS-free) — keep it a multilingual
  variant (not an `.en` one) unless every meeting recorded in this vault is guaranteed English.
