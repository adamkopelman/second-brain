---
name: gtd-weekly-review
description: Use when the user wants to do their GTD weekly review — the recurring ritual to get clear, current, and creative. Triggers on "weekly review", "review my week", "gtd review", "do my review".
---

# GTD Weekly Review (Reflect)

Guide the user through the review interactively, updating the vault as you go. Full checklist in
`Weekly Review.md`. Read `30 Resources/GTD System.md`.

## Process
### Get Clear
- Process `00 Inbox/` to empty (`/gtd-process-inbox`); prompt a brain-dump and process it.
### Get Current
- Projects: each `status: active` note in `10 Projects/` has a concrete `#next`; bump `review:` +7d.
- Waiting For: list `#waiting`; flag stale `[since::]`; offer follow-ups.
- Calendar/Journal: past week + next two weeks. If Outlook is configured, `/gtd-outlook` can pull
  the calendar. People: skim `People/` agendas.
### Get Creative
- Promote ready `#someday`/`status: someday` items. Review `20 Areas/`. Archive done projects
  (`status: done` → `40 Archive/`).

## Finish
- Create a `Journal/` note from `_templates/Weekly Review.md`, tagged `#weekly-review`, summarizing
  changes and carry-overs. Offer to refresh the dashboard (`/gtd-dashboard`).

## Rules
- Confirm before deleting/archiving. Done = inbox empty, every active project has a next action,
  review note written.
