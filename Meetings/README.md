# 🤝 Meetings
Meeting notes. Capture action items as `#next` tasks so they flow to the dashboard. Use
`_templates/Meeting.md`.

## Recording + transcription
Click the mic icon in the left ribbon (or run "Toggle meeting recording" from the command palette)
to record a meeting straight to `Meetings/recordings/*.wav` and open a linked note for it. When
you're ready, click the captions icon (or run "Transcribe pending meeting recordings") to transcribe
every pending recording locally (vendored `whisper.cpp`, fully offline) and extract `#next` action
items into the note — see `docs/gtd/meeting-recording.md`.
