---
name: gtd-transcribe-meeting
description: Use when the user wants to transcribe a recorded meeting, process pending meeting recordings, or get a full summary (notes, decisions, action items) out of a meeting recording. Triggers on "transcribe my meeting", "process the recording", "what came out of that meeting".
---

# GTD Transcribe Meeting

Runs the full pipeline for recorded meetings, on demand: mechanical transcription, then summarization.
For scheduled/unattended summarization alone, see `gtd-summarize-meetings`, which this skill delegates
to for step 2 — that skill is the one source of truth for how summarization works.

## Steps
1. Run: `python scripts/transcribe_meetings.py .` — transcribes every meeting note under `Meetings/`
   whose frontmatter has `transcription_status: pending` (created by the `record-meeting` Obsidian
   plugin's recording button, or manually by setting `recording: "[[path/to/file.wav]]"` and
   `transcription_status: pending` on a note yourself). This writes the transcript into `## Transcript`
   and sets `summary_status: pending` — it does not summarize anything itself.
2. Invoke the `gtd-summarize-meetings` skill. This catches both the notes just transcribed in step 1
   and any older ones that were transcribed via the Obsidian captions button but never summarized.
3. Report both stages together: transcription results from step 1
   (`OK (transcribed): <note>` / `FAILED (<reason>): <note>` / "No pending meeting recordings."), then
   summarization results from step 2.
4. If any note failed transcription, open it — a `> [!fail] Transcription failed: ...` callout was
   added explaining why (commonly: the `.wav` was moved/deleted, or the vendored
   `vendor/whisper-cpp/whisper-cli.exe` is missing). Tell the user what it says; don't guess.

## Rules
- Transcription (step 1) is fully mechanical and must never be fabricated — it's the vendored
  `vendor/whisper-cpp/` binary + model doing the work (offline by default; only pass
  `--remote-url <endpoint>`/`--api-key` if the user explicitly wants a remote/OpenAI-compatible
  Whisper API instead, which requires network access).
- Summarization (step 2) IS real generation, by design — see `gtd-summarize-meetings` for why that's
  expected there and not a "never fabricate" violation.
- Idempotent — notes already `transcription_status: done` are skipped in step 1, and notes already
  `summary_status: done` are skipped in step 2, so it's always safe to re-run.
