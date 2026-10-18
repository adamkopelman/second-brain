# Meeting recording, transcription, and summarization

Recording and transcription are Obsidian-plugin/script-driven and fully mechanical; summarizing what
was said (notes, decisions, action items) is a separate, Claude-Code-only step — a transcript can be
in any language and largely unstructured, so pattern-matching a summary out of it needs real reading
comprehension, not a regex.

## The two stages

1. **Transcription (mechanical).** Turns audio into `## Transcript` text. Tracked by the note's
   `transcription_status` frontmatter field (`pending` → `done`/`failed`). Never guesses at meaning —
   just runs the local, offline Whisper model (whisper.cpp) against the recording.
2. **Summarization (Claude Code, real generation).** Reads `## Transcript` and writes `## Notes`,
   `## Decisions`, and `## Action items` — with each action item tagged with a real context guess
   (`#computer`, `#phone`, ... or `#unknown` when genuinely ambiguous). Tracked by `summary_status`
   (`pending` → `done`). Handled by the `gtd-summarize-meetings` skill, in whatever language the
   transcript is in — nothing gets translated.

## Setup (once, Windows)

1. Check out the two submodules this uses — already there if you cloned with
   `--recurse-submodules`:
   `git submodule update --init vendor/whisper-cpp .obsidian/plugins/record-meeting`
2. Download the Whisper model (~74 MB; too big for git, so it isn't committed):
   `powershell -ExecutionPolicy Bypass -File vendor\whisper-cpp\download-model.ps1`
   (or `sh vendor/whisper-cpp/download-model.sh`). It fetches the multilingual `ggml-tiny.bin` from
   https://huggingface.co/ggerganov/whisper.cpp, checks its SHA-256 and saves it as
   `vendor/whisper-cpp/models/ggml-tiny.bin` (git-ignored). Re-running it is harmless.

## Recording and transcribing (buttons)

Two buttons, both added by the `record-meeting` Obsidian plugin (`.obsidian/plugins/record-meeting/`,
a submodule — [adamkopelman/obsidian-record-meeting](https://github.com/adamkopelman/obsidian-record-meeting) —
enabled by default via `community-plugins.json`):

- 🎙️ **mic ribbon icon** ("Toggle meeting recording") — click once to start recording your
  microphone; click again to stop. Saves `Meetings/recordings/<timestamp>.wav` and opens a new
  `Meetings/<timestamp> Meeting.md` note with `recording: "[[...]]"` pointing at it and
  `transcription_status: pending`. `summary_status: pending` is added once transcription finishes
  (see below), not by this button.
- 💬 **captions ribbon icon** ("Transcribe pending meeting recordings") — transcribes every pending
  recording and writes the result into that note's `## Transcript` section. It does **not** summarize
  — `## Action items` is left with a `_Pending summary — run /gtd-transcribe-meeting or
  /gtd-summarize-meetings in Claude Code._` placeholder until the summarization step runs.

Both are also in the command palette (`Ctrl+P` → "Record Meeting: ...") if you'd rather use a hotkey.

**Or record from the local dashboard** (`docs/gtd/local-dashboard.md`): press `r` or click
**Record** in the bottom bar — or press `Enter` on one of the Outlook meetings listed on Today or
Upcoming to record it under that meeting's name, with its attendees. It writes the same WAV + note as
the mic icon and transcribes it automatically in the background, so there's nothing else to click.
For recordings made with the Obsidian mic icon, Today shows "N meetings to transcribe" (press `Enter`
on it to run the same transcription), and "N to-dos from meetings need a tag" for any action item
whose context came back `#unknown` — it opens Anytime filtered to them, so you can open each one and
pick a real tag.

## Summarizing (Claude Code)

- **On demand, right now:** ask for "transcribe my meeting" (or run `/gtd-transcribe-meeting`) — it
  runs the transcription script, then summarizes anything pending (both what it just transcribed and
  anything transcribed earlier via the Obsidian button but never summarized).
- **Unattended, on a schedule:** `/gtd-summarize-meetings` does the summarization step alone, with no
  prompts — safe to run on a recurring schedule (e.g. every 2 hours) once you've configured one
  yourself, since it just finds transcribed-but-unsummarized notes and processes them.

## How it works offline

Recording uses the browser's own microphone + Web Audio APIs (`getUserMedia`/`AudioContext`) built
into Obsidian's desktop app and encodes straight to a `.wav` file itself — no external encoder, no
network. Transcription shells out to `vendor/whisper-cpp/whisper-cli.exe`, an unmodified, fully
offline `whisper.cpp` build (the `vendor/whisper-cpp` submodule,
[adamkopelman/whisper-cpp](https://github.com/adamkopelman/whisper-cpp), from
[ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)), against the **multilingual**
`ggml-tiny.bin` model with automatic per-recording language detection (`-l auto`) — see
`vendor/whisper-cpp/README.md` for exactly what's in there and how to upgrade it. Once the model is
downloaded (Setup above), nothing in the transcription stage needs internet access, `pip install`, or
`npm install`. For an air-gapped machine, download `ggml-tiny.bin` on a connected one and copy it to
`vendor/whisper-cpp/models/ggml-tiny.bin`. Summarization, by contrast, always runs through Claude
Code (it's the reading-comprehension step).

## Optional: a remote Whisper API instead

If you'd rather use a remote/hosted Whisper endpoint (e.g. OpenAI's), run
`python scripts/transcribe_meetings.py . --remote-url https://api.openai.com/v1/audio/transcriptions
--api-key sk-...` yourself, or pass `--remote-url`/`--api-key` through to the
`gtd-transcribe-meeting` skill. This is opt-in only — the plugin's captions button always uses the
local model.

## Privacy note

`Meetings/recordings/*.wav` is gitignored — your recordings stay on your machine and are never
committed, even though the code that makes and processes them is.

## Troubleshooting

- `error: whisper model not found at …\vendor\whisper-cpp\models\ggml-tiny.bin` — download the model
  (Setup step 2). Pending notes stay pending, so just transcribe again afterwards.
- `error: whisper binary not found at …\vendor\whisper-cpp\whisper-cli.exe` — the `vendor/whisper-cpp`
  submodule isn't checked out: `git submodule update --init vendor/whisper-cpp`.

If the "Transcribe pending meeting recordings" button (or the dashboard's "Transcribe pending" button)
fails immediately with an unclear Python-related error, check that `python` (or `python3`/`py`) on
your PATH actually resolves to a real Python installation. On Windows, this usually means installing
Python from python.org with "Add python.exe to PATH" checked during setup, rather than relying on the
Microsoft Store's Python listing — its `python` command can silently no-op (a stub app-execution
alias) instead of running your code, which produces a confusing failure rather than a clear "Python
not found" message.
