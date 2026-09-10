# Meeting recording + transcription

Two buttons, both added by the vendored `record-meeting` Obsidian plugin
(`.obsidian/plugins/record-meeting/`, enabled by default via `community-plugins.json`):

- 🎙️ **mic ribbon icon** ("Toggle meeting recording") — click once to start recording your
  microphone; click again to stop. Saves `Meetings/recordings/<timestamp>.wav` and opens a new
  `Meetings/<timestamp> Meeting.md` note with `recording: "[[...]]"` pointing at it and
  `transcription_status: pending`.
- 💬 **captions ribbon icon** ("Transcribe pending meeting recordings") — transcribes every pending
  recording and writes the result into that note's `## Transcript` section, extracting `#next`
  action items (each linked back to the note, e.g. `- [ ] Send the report. #next [[2026-09-10_...]]`)
  into `## Action items`. Action items flow into `Dashboard.md` like any other `#next` task.

Both are also in the command palette (`Ctrl+P` → "Record Meeting: ...") if you'd rather use a
hotkey, and the same transcription step is reachable from Claude Code/opencode via the
`gtd-transcribe-meeting` skill ("transcribe my meeting") if you'd rather not click anything.

## How it works offline
Recording uses the browser's own microphone + Web Audio APIs (`getUserMedia`/`AudioContext`) built
into Obsidian's desktop app and encodes straight to a `.wav` file itself — no external encoder, no
network. Transcription shells out to `vendor/whisper-cpp/whisper-cli.exe`, a vendored, fully offline
`whisper.cpp` build, against the vendored `ggml-tiny.en.bin` model — see
`vendor/whisper-cpp/README.md` for exactly what's in there and how to upgrade it. Nothing in this
feature requires internet access, `pip install`, or `npm install` — it works immediately on a fresh,
air-gapped clone of this repo.

## Optional: a remote Whisper API instead
If you'd rather use a remote/hosted Whisper endpoint (e.g. OpenAI's), run
`python scripts/transcribe_meetings.py . --remote-url https://api.openai.com/v1/audio/transcriptions
--api-key sk-...` yourself, or pass `--remote-url`/`--api-key` through to the
`gtd-transcribe-meeting` skill. This is opt-in only — the plugin's captions button always uses the
local vendored model.

## Privacy note
`Meetings/recordings/*.wav` is gitignored — your recordings stay on your machine and are never
committed, even though the code that makes and processes them is.

## Troubleshooting
If the "Transcribe pending meeting recordings" button fails immediately with an unclear
Python-related error, check that `python` (or `python3`/`py`) on your PATH actually resolves to a
real Python installation. On Windows, this usually means installing Python from python.org with
"Add python.exe to PATH" checked during setup, rather than relying on the Microsoft Store's Python
listing — its `python` command can silently no-op (a stub app-execution alias) instead of running
your code, which produces a confusing failure rather than a clear "Python not found" message.
