# Vendored: whisper.cpp (Windows x64 CPU build)

Local, fully-offline speech-to-text used by `scripts/transcribe_meetings.py` (and, through it, the
`record-meeting` Obsidian plugin and the `gtd-transcribe-meeting` skill). Committed so the vault is
self-contained for air-gapped machines — no `pip install openai-whisper`, no network, no ffmpeg.

- **Source:** https://github.com/ggml-org/whisper.cpp (release `b4938`, CPU-only Windows x64 build:
  `whisper-bin-x64.zip`)
- **Model:** https://huggingface.co/ggerganov/whisper.cpp `ggml-tiny.en.bin` (~74MB, English-only —
  chosen over `base.en`/`small.en` because it's under GitHub's 100MB hard file-size limit, so it can
  be committed directly with no Git LFS; LFS would defeat the air-gapped "clone and go" requirement).
- **Files:** `whisper-cli.exe` + `whisper.dll`, `ggml.dll`, `ggml-base.dll`, and all `ggml-cpu-*.dll`
  variants (the exe auto-detects the running CPU's feature set and loads the matching one — keep all
  of them since the machine this runs on may differ from the machine that vendored these files).
  `SDL2.dll`/`llama.dll`/`parakeet*` from the same release zip are unrelated demo-tool dependencies
  and were intentionally **not** vendored.
- **Platform:** Windows x86-64 only. `scripts/transcribe_meetings.py` fails clearly (not silently) if
  `--remote-url` isn't given and this binary isn't present/runnable — see that script's `main()`.
- **sha256 (whisper-cli.exe):** `800a0fd754afa75e109c7248286ad735670fb6b23d92ca5d12604647ef638a65`
- **sha256 (ggml-tiny.en.bin):** `921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f`
- **Usage:** `whisper-cli.exe -m models/ggml-tiny.en.bin -f <audio> -oj -of <out> -np -l en` — see
  `scripts/transcribe_meetings.py::transcribe_local` for the exact invocation.
- **Updating:** download a newer `whisper-bin-x64.zip` from
  https://github.com/ggml-org/whisper.cpp/releases and repeat the file list above; swap the model for
  a different `ggml-*.bin` from https://huggingface.co/ggerganov/whisper.cpp if you want better
  accuracy and don't mind a bigger repo (anything ≤~95MB is still LFS-free).
