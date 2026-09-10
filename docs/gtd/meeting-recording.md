# Meeting recording, transcription, and summarization

Recording and transcription are Obsidian-plugin/script-driven and fully mechanical; summarizing what
was said (notes, decisions, action items) is a separate, Claude-Code-only step — a transcript can be
in any language and largely unstructured, so pattern-matching a summary out of it needs real reading
comprehension, not a regex.

## The two stages

1. **Transcription (mechanical).** Turns audio into `## Transcript` text. Tracked by the note's
   `transcription_status` frontmatter field (`pending` → `done`/`failed`). Never guesses at meaning —
   just runs the vendored offline Whisper model against the recording.
2. **Summarization (Claude Code, real generation).** Reads `## Transcript` and writes `## Notes`,
   `## Decisions`, and `## Action items` — with each action item tagged with a real context guess
   (`#computer`, `#phone`, ... or `#unknown` when genuinely ambiguous). Tracked by `summary_status`
   (`pending` → `done`). Handled by the `gtd-summarize-meetings` skill, in whatever language the
   transcript is in — nothing gets translated.

## Recording and transcribing (buttons)

Two buttons, both added by the vendored `record-meeting` Obsidian plugin
(`.obsidian/plugins/record-meeting/`, enabled by default via `community-plugins.json`):

- 🎙️ **mic ribbon icon** ("Toggle meeting recording") — click once to start recording your
  microphone; click again to stop. Saves `Meetings/recordings/<timestamp>.wav` and opens a new
  `Meetings/<timestamp> Meeting.md` note with `recording: "[[...]]"` pointing at it,
  `transcription_status: pending`, and `summary_status: pending`.
- 💬 **captions ribbon icon** ("Transcribe pending meeting recordings") — transcribes every pending
  recording and writes the result into that note's `## Transcript` section. It does **not** summarize
  — `## Action items` is left with a `_Pending summary — run /gtd-transcribe-meeting or
  /gtd-summarize-meetings in Claude Code._` placeholder until the summarization step runs.

Both are also in the command palette (`Ctrl+P` → "Record Meeting: ...") if you'd rather use a hotkey.
The local dashboard server's Meetings card has the same "Transcribe pending" action as a button, and
the dashboard's "Needs triage" card surfaces any action item whose context came back `#unknown` so you
can resolve it with a couple of clicks.

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
network. Transcription shells out to `vendor/whisper-cpp/whisper-cli.exe`, a vendored, fully offline
`whisper.cpp` build, against the vendored **multilingual** `ggml-tiny.bin` model with automatic
per-recording language detection (`-l auto`) — see `vendor/whisper-cpp/README.md` for exactly what's
in there and how to upgrade it. Nothing in the transcription stage requires internet access,
`pip install`, or `npm install` — it works immediately on a fresh, air-gapped clone of this repo.
Summarization, by contrast, always runs through Claude Code (it's the reading-comprehension step).

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

If the "Transcribe pending meeting recordings" button (or the dashboard's "Transcribe pending" button)
fails immediately with an unclear Python-related error, check that `python` (or `python3`/`py`) on
your PATH actually resolves to a real Python installation. On Windows, this usually means installing
Python from python.org with "Add python.exe to PATH" checked during setup, rather than relying on the
Microsoft Store's Python listing — its `python` command can silently no-op (a stub app-execution
alias) instead of running your code, which produces a confusing failure rather than a clear "Python
not found" message.
