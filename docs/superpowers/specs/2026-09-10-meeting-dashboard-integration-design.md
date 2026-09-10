# Meeting Feature ↔ Dashboard Integration — Design

**Status:** Approved by user (via conversation this session), ready for implementation plan.
**Date:** 2026-09-10

## Problem

A separate Claude Code session added a `record-meeting` Obsidian plugin (recording + mechanical
transcription via a vendored offline Whisper build) earlier today. It isn't wired into the local
dashboard server built in this session, and investigation surfaced two real defects, one of which
is load-bearing for the user's actual use case:

1. **Transcription itself is broken for the user's real meetings.** `transcribe_meetings.py`
   hardcodes `-l en` to whisper-cli, and the vendored model is `ggml-tiny.en.bin` — an
   **English-only** model (confirmed via `vendor/whisper-cpp/README.md`: "chosen over base.en/
   small.en because it's under GitHub's 100MB hard file-size limit"). The user's meetings are
   "usually in Hebrew" — this model architecturally cannot transcribe Hebrew at all, independent of
   any flag.
2. **Action-item extraction is also broken for the same reason**, one layer up:
   `extract_action_items`'s `ACTION_CUES` regex only matches English commitment phrases ("I'll",
   "need to", "by Friday", ...) against `transcript` text — meaningless against Hebrew, and weak
   even in English against real unstructured speech (any sentence containing "should"/"let's"
   qualifies whether or not it's really a commitment).
3. Even where it works, an extracted action item carries no context tag (lands in the dashboard's
   catch-all "anywhere" bucket) and no visible link back to which meeting produced it.

## Goals

1. **Fix transcription itself**: vendor a multilingual Whisper model, drop the hardcoded English
   language flag, so Hebrew (or any language) transcribes correctly.
2. **Split the pipeline** into two independent, idempotent stages tracked by two separate
   frontmatter fields: mechanical transcription (`transcription_status`, unchanged mechanism, script/
   button-driven, no language-specific guessing) and LLM-driven summarization (`summary_status`, new,
   Claude-Code-only — real reading comprehension handles any language and produces a real context
   guess per action item, falling back to an explicit `#unknown` only when genuinely ambiguous).
3. **New skill `gtd-summarize-meetings`**: an idempotent, no-prompt, scheduler-safe command that
   finds transcribed-but-unsummarized meetings and summarizes them. Designed to be run unattended on
   a recurring schedule (the user will configure that separately, e.g. every 2 hours).
4. **Existing skill `gtd-transcribe-meeting`** becomes the on-demand "do it all now" command: runs
   the (now purely mechanical) script, then delegates to `gtd-summarize-meetings` for anything
   pending — one source of truth for the summarization logic.
5. **Wire meetings into the dashboard**: a Meetings card (recent meetings, pending-transcription/
   pending-summary counts, a "Transcribe pending" button hitting a new `/api/transcribe` endpoint
   that shells out to the same script the Obsidian plugin already uses), tasks show which meeting
   they came from, `#unknown` becomes a real distinct context bucket with its own "Needs triage"
   card, and the task detail overlay gets an editable context dropdown to resolve them.
6. Keep the `gtd-setup` scaffold in sync with every vault-facing template change (and, incidentally,
   restore its `_templates/Meeting.md`, which had already drifted out of sync with root before this
   work — the earlier meeting-recording feature never mirrored its template changes there).

## Non-goals

- Not setting up the actual recurring 2-hour schedule — the user will configure that separately
  (possibly with help via the `/schedule` skill) once `gtd-summarize-meetings` exists to point it at.
- Not adding dashboard-side audio recording — recording stays Obsidian-plugin-only.
- Not modifying the `record-meeting` Obsidian plugin itself.
- Not translating transcripts or summaries — everything stays in the meeting's own language.
- Not building a dedicated "meeting detail" overlay on the dashboard — a meeting pill/link opens the
  note directly in Obsidian, same pattern as project links; scope stays tight.
- Not grading Whisper's actual Hebrew transcription *accuracy* — this plan fixes the plumbing (right
  model, right language flag) but only the user, with real Hebrew audio, can judge output quality.

## Design

### 1. Multilingual transcription

- Vendor `ggml-tiny.bin` (multilingual tiny model) into `vendor/whisper-cpp/models/`, **replacing**
  `ggml-tiny.en.bin` — verified this session: downloads from
  `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin`, 77,691,713 bytes
  (~74 MiB), sha256 `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`, well under
  GitHub's 100 MB no-LFS limit, valid `ggml` file header confirmed.
- `transcribe_meetings.py`: default `--model` path becomes `vendor/whisper-cpp/models/ggml-tiny.bin`;
  `transcribe_local`'s whisper-cli invocation changes `-l en` → `-l auto` (per-recording language
  auto-detection — correct for a vault where meetings are "usually" Hebrew but not exclusively).
- `vendor/whisper-cpp/README.md` updated to document the new model (source, sha256, size, why
  multilingual, and that `ggml-tiny.en.bin` was removed in favor of it).

### 2. `transcribe_meetings.py` becomes mechanical-only

- Remove `ACTION_CUES` and `extract_action_items` entirely — they don't work for the vault's real
  content and shouldn't pretend to.
- `apply_transcript(note_text, transcript, note_stem)` drops its `action_items` parameter.
  `## Transcript` is filled exactly as today. `## Action items` gets a clear placeholder:
  `_Pending summary — run /gtd-transcribe-meeting or /gtd-summarize-meetings in Claude Code._`
  Frontmatter gains `summary_status: pending` alongside the existing `transcription_status: done`.
- `process()`'s per-note result string changes from `"OK ({N} action item(s)): {name}"` to
  `"OK (transcribed): {name}"` (action-item counting no longer happens at this stage).
- Existing tests updated to match (see plan for exact diffs); the two action-item-extraction tests
  are removed since the function they test no longer exists.

### 3. New skill: `gtd-summarize-meetings`

Idempotent, unattended-safe, no interactive prompts (designed to run standalone on a schedule):

1. Find every note under `Meetings/` (excluding `README.md`) with `transcription_status: done` and
   `summary_status` not `done`.
2. If none: report "No unsummarized meetings." and stop.
3. For each: read `## Transcript`.
   - Empty or the `_No speech detected._` placeholder → set `summary_status: done`, note "No speech
     detected — nothing to summarize," move on. Never fabricate content for a note with nothing to
     summarize.
   - Otherwise → write a real summary into `## Notes` (append below any existing non-placeholder
     content — never overwrite genuine user notes), explicit decisions into `## Decisions`, and
     action items into `## Action items` as `- [ ] {text} #next #{context} [[{note_stem}]]`,
     inferring context from what the transcript actually says (a phone call/message → `#phone`, a
     document/code/deck update → `#computer`, an in-person errand → `#errands`, home-only →
     `#home`, workplace-only → `#office`, no clear signal → `#anywhere`, tied to a specific person's
     next meeting → `#agenda`), falling back to `#unknown` only when genuinely ambiguous even after
     reading the whole transcript. Set `summary_status: done`.
4. Report each note's result concisely.

Works in any language — reads and writes in the transcript's own language, no translation step.
This is the one skill in this vault whose entire job is genuine LLM generation (summarizing,
inferring context) — unlike `gtd-capture` etc., that's expected and intentional here, not a
violation of "never fabricate."

### 4. Updated skill: `gtd-transcribe-meeting`

Step 1 (unchanged): run `scripts/transcribe_meetings.py .`. Step 2 (new): invoke the
`gtd-summarize-meetings` skill — this catches both notes just transcribed in step 1 and any older
ones transcribed via the Obsidian button but never summarized. Report both stages together. The
"Rules" section is reworded: transcription still must never be fabricated (mechanical script's job,
unchanged); summarization is real generation, explicitly delegated to `gtd-summarize-meetings`.

### 5. Dashboard backend

- **`dashboard_parser.py`**: add `"#unknown"` to `build_dashboard.CONTEXTS`. Add a `meeting` field
  to task dicts (parallel to `project`, but sourced from the `Meetings/` folder instead of
  `10 Projects/`) in `iter_tasks_with_location`, threaded into every task entry `collect_state`
  builds. Add a `meetings` key to `collect_state`'s return value: recent `Meetings/*.md` notes
  (excluding README), each `{name, file, date, transcription_status, summary_status}`, newest-first
  by the `date` frontmatter field, capped at 8.
- **`dashboard_writer.py`**: `edit_task` gains `new_context: str | None = None` — when given,
  strips any existing context-tag (a tag that's a member of `BD.CONTEXTS`) from the rebuilt line and
  adds the new one. New `run_transcription(vault) -> str`: runs
  `scripts/transcribe_meetings.py <vault>` as a subprocess (via `sys.executable`, matching how the
  Obsidian plugin already shells out to the same script) and returns its output, raising on a
  nonzero exit or timeout.
- **`dashboard_server.py`**: `/api/edit-task` reads and passes through `new_context`. New
  `POST /api/transcribe` calls `run_transcription` and returns its output as JSON, mapping failures
  to a clear error status.

### 6. Dashboard frontend

- **`logic.js`**: the task detail overlay's context field becomes an editable `<select>` (same
  option list as quick-add's, plus "unknown"); if a task has a `meeting`, show a meeting pill
  (parallel to the project pill) instead of "none." New `renderNeedsTriage` (every `#unknown`-context
  task, one place) and `renderMeetings` (the meetings list with status pills, each linking to its
  note) pure functions, wired into `render()`'s returned object.
- **`index.html`**: two new cards — "Needs triage" and "Meetings" (the 4×2 grid now holds exactly 8
  single/double-span sections with no empty cells) — with a "Transcribe pending" button inside the
  Meetings card.
- **`app.js`**: wires the transcribe button (POST, disable + "Transcribing…" while in flight, since
  this can take a while, refresh on completion) and the detail overlay's new context `<select>` into
  the existing Save flow.
- **`style.css`**: a `.meeting` pill (parallel to `.proj`), a "Needs triage" card accent, and
  transcribe-button states.

### 7. Templates & scaffold sync

- `_templates/Meeting.md` gains `summary_status: ` in frontmatter.
- Mirrored into `.claude/skills/gtd-setup/scaffold/vault/_templates/Meeting.md` — a full replace,
  since that copy currently lacks even the pre-existing `recording`/`transcription_status` fields
  (drifted out of sync with root before this session's work; this restores the scaffold==root
  convention documented elsewhere in this repo).
- No other scaffold changes — `scripts/dashboard_static/*` and `scripts/*.py` are repo-level tooling,
  not vault content, and were never part of the scaffold's tracked set (consistent with how the
  local dashboard server itself was handled earlier this session).

### 8. Docs

- `docs/gtd/meeting-recording.md` rewritten to describe the two-stage pipeline, the new skill, the
  multilingual model fix, and the dashboard integration.
- `docs/gtd/local-dashboard.md` gets a short addition on the Meetings/Needs-triage cards and the
  transcribe button.

## Testing approach

- **Python (pytest)**: `dashboard_parser` (the `meeting` field, the `meetings` list),
  `dashboard_writer` (`new_context`, `run_transcription`), `dashboard_server` (the new endpoint),
  `transcribe_meetings` (updated behavior; the two obsolete action-item tests removed).
- **Frontend (`node --test`)**: the new pure `logic.js` functions (`renderNeedsTriage`,
  `renderMeetings`), and the context-`<select>` shape in `taskDetailHtml`.
- **Manual, by a human** (same limitation as prior work this session — no agent has GUI/audio
  access): the two skills (`gtd-summarize-meetings`, updated `gtd-transcribe-meeting`) are
  prompt-based and can't be unit tested — verify by hand against a real or synthetic transcribed
  meeting note. Whisper's actual **Hebrew transcription accuracy** can only be judged by the user
  with real Hebrew audio — the plan verifies the model loads and runs (extending the existing
  vendored-binary smoke test), not transcription quality.

## Open risks

- The model swap is a real binary replacement in the repo (`ggml-tiny.en.bin` → `ggml-tiny.bin`) —
  fully reversible via git, but a meaningful, deliberate change worth naming plainly, not burying in
  a diff.
- Hebrew transcription accuracy is unverifiable by any agent in this session — flagged above, not
  silently assumed to be "fixed" just because the plumbing is now correct.
