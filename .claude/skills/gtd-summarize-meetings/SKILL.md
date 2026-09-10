---
name: gtd-summarize-meetings
description: Use when checking for or summarizing transcribed meetings that haven't been summarized yet — extracting notes, decisions, and action items from a meeting transcript. Triggers on "summarize meetings", "check for unsummarized meetings", "process meeting transcripts". Designed to also run unattended on a recurring schedule.
---

# GTD Summarize Meetings

Idempotent, unattended-safe: finds every meeting note under `Meetings/` that has been transcribed but
not yet summarized, and writes a real summary into it. No interactive prompts — safe to run on a
schedule (e.g. every 2 hours) with no one watching.

Unlike most GTD skills in this vault, this one's entire job IS generation: reading a transcript,
writing a summary, and inferring which action items exist and what context they belong to. That is
expected here — it is not a violation of "never fabricate."

## Steps
1. List every note directly under `Meetings/` (`README.md` excluded) whose frontmatter has
   `transcription_status: done` and `summary_status` not equal to `done`.
2. If none: report "No unsummarized meetings." and stop.
3. For each note, read its `## Transcript` section:
   - If empty or exactly `_No speech detected._`: set `summary_status: done` in frontmatter, leave
     `## Notes`/`## Decisions`/`## Action items` untouched, note "No speech detected — nothing to
     summarize," and move to the next note.
   - Otherwise, read the whole transcript (it may be in any language — read and respond in that
     language, never translate) and:
     - Append a concise summary to `## Notes`, below any existing non-placeholder content already
       there (never overwrite genuine user notes — this section may already have pre-meeting notes).
     - Append explicit decisions made in the meeting to `## Decisions`.
     - Replace the `_Pending summary — ..._` placeholder in `## Action items` with one
       `- [ ] {text} #next #{context} [[{note_stem}]]` line per real action item, inferring `{context}`
       from what the transcript actually says:
       - a phone call or message to make → `#phone`
       - a document, code, or deck to update → `#computer`
       - an in-person errand → `#errands`
       - something only doable at home → `#home`
       - something only doable at the workplace → `#office`
       - tied to a specific person's next meeting/conversation with them → `#agenda`
       - no clear location/tool signal → `#anywhere`
       - genuinely ambiguous even after reading the whole transcript → `#unknown` (the dashboard's
         "Needs triage" card lets the user resolve these later — never guess just to avoid it)
     - Set `summary_status: done`.
4. Report each note's result concisely (one line per note: summarized with N action items, or "no
   speech detected," etc.).

## Rules
- Idempotent — notes already `summary_status: done` are left untouched, so it's always safe to re-run
  (including on an unattended schedule).
- Never overwrite existing `## Notes`/`## Decisions` content — append below it.
- Never fabricate a transcript — this skill only summarizes what `## Transcript` actually contains;
  that section is filled mechanically by `scripts/transcribe_meetings.py` before this skill ever runs.
- No interactive prompts, no confirmation questions — this must be able to run with nobody watching.
