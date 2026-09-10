---
name: gtd-transcribe-meeting
description: Use when the user wants to transcribe a recorded meeting, process pending meeting recordings, or extract action items from a meeting recording. Triggers on "transcribe my meeting", "process the recording", "what came out of that meeting".
---

# GTD Transcribe Meeting

Transcribes every meeting note under `Meetings/` whose frontmatter has
`transcription_status: pending` (created by the `record-meeting` Obsidian plugin's recording
button, or manually by setting `recording: "[[path/to/file.wav]]"` and
`transcription_status: pending` on a note yourself), writes the transcript into that note's
`## Transcript` section, and extracts `#next` action items — linked back to the note (which itself
links to the recording) — into `## Action items`.

## Steps
1. Run: `python scripts/transcribe_meetings.py .`
2. Report each result line back to the user (`OK (N action item(s)): <note>` or
   `FAILED (<reason>): <note>`, or "No pending meeting recordings.").
3. If any note failed, open it — a `> [!fail] Transcription failed: ...` callout was added explaining
   why (commonly: the `.wav` was moved/deleted, or the vendored `vendor/whisper-cpp/whisper-cli.exe`
   is missing). Tell the user what it says; don't guess.

## Rules
- Fully offline by default — transcription runs against the vendored `vendor/whisper-cpp/` binary +
  model. Only pass `--remote-url <endpoint>` (and optionally `--api-key`) if the user explicitly
  wants a remote/OpenAI-compatible Whisper API instead; that requires network access.
- Idempotent — notes already `transcription_status: done` are left untouched, so it's always safe to
  re-run.
- Never invent a transcript or action items yourself — this skill's job is to run the script and
  relay its output, not to transcribe or summarize the meeting from the note title alone.
