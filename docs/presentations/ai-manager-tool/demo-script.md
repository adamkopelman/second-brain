# Live Demo Script — *The AI Chief of Staff*

Exact steps for the five live demos, keyed to this second-brain vault. Everything here uses the vault's real skills (`.claude/skills/`). Run them in **Claude Code**, opencode, or **Claudian** (inside Obsidian). Times match the facilitator guide.

> **Golden rule of a live demo:** rehearse it once end-to-end before the room. If the network is shaky, the screenshots you capture during rehearsal are your fallback — flip to them and keep talking.

---

## Setup (before the talk)

```
# From the vault root
/gtd-status          # warms context; also your Demo 5 opener
```

Pre-stage so the demos have something to act on:

1. **Capture a few items** so the inbox isn't empty for Demo 2:
   ```
   /gtd-capture the website feels slow lately
   /gtd-capture book the offsite venue
   /gtd-capture idea: monthly written update to the team
   ```
2. **Stage a meeting transcript** for Demo 4. Drop a short transcript file under `Meetings/` (a paragraph of realistic sync notes is enough), or use a real one you have. If you have the `record-meeting` Obsidian plugin, you can record 20 seconds live — but a staged transcript is safer for timing.

---

## Demo 1 · Capture — "the two-second inbox"  (slide 7)

**Say:** "Watch how little friction this is." Type a thought you genuinely have right now.

```
/gtd-capture remind me to send Sam the Q3 figures before Friday
```

**Show:** the new checkbox in `00 Inbox/` — tags applied (`#next`, maybe `#agenda [[Sam Rivera]]`), a `[due:: ]` inferred from "Friday."

**Point out:** you didn't choose a folder, didn't switch apps, didn't stop thinking about your actual work. Capture and organise are *separate steps on purpose.*

**Fallback line if it mis-tags:** "And notice — I can see exactly what it did, in plain text, and fix it. Nothing happens in the dark."

---

## Demo 2 · Clarify — "empty the inbox"  (slide 8)

**Say:** "Capturing is easy. The step everyone skips is deciding. Let's let it walk the decision tree."

```
/gtd-process-inbox
```

**Show:** it takes items one at a time and asks the GTD questions:
- Actionable? If no → trash / someday / reference.
- One step or many? Many → a **project** with a first `#next` action.
- Someone else's? → `#waiting` + `[[Person]]` + `[since:: ]`.

Take the "website feels slow" item all the way to a project (`10 Projects/Speed up the site.md`) with a first action like "Profile the homepage `#computer`."

**Point out:** the inbox goes to zero. That "inbox zero for your brain" feeling is the hook.

---

## Demo 3 · Engage — "what do I do right now?"  (slide 9)

**Say:** "The list you need is never *everything*. It's what fits this moment."

```
what can I do at my computer in 15 minutes?
```
(or `/gtd-next-actions` and then narrow by context/time/energy)

**Show:** it returns only the `#next` actions matching `#computer` and a ~15-min budget, and *hides* the rest. Try a second filter live to make it real:

```
I'm on my phone with 5 minutes and low energy — what's easy?
```

**Point out:** context / time / energy is the GTD engage model. The AI is doing the filtering you'd otherwise do in your head (badly, under stress).

---

## Demo 4 · Meetings → follow-through — *the money demo*  (slide 10)

**Say:** "This is the one that pays for the whole system."

```
/gtd-summarize-meetings
```

**Show:** it finds the staged transcript and produces:
- **Notes** — the gist.
- **Decisions** — "we agreed to ship v2 behind a flag first."
- **Action items** — real `#next` tasks *with owners*.
- Delegated items become `#waiting [[Person]] [since:: DATE]`, and the relevant **People** notes get updated.

**Point out:** the meeting is over and the follow-through *already exists* — filed, assigned, and trackable. Next week when you ask "what am I waiting on from Priya?", it's there. This is the single most convincing moment; give it room.

*(If someone asks about recording: the vault ships a `record-meeting` Obsidian plugin — 🎙️/💬 ribbon buttons — that records to WAV and transcribes fully offline with vendored whisper.cpp. Summarising then runs here in Claude Code. See `docs/gtd/meeting-recording.md`.)*

---

## Demo 5 · Review & dashboard — "keep it honest"  (slide 11)

**Say:** "A second brain you don't trust is just another pile. Here's the ritual that keeps trust."

Opener (fast):
```
/gtd-status
```
**Show:** the brief — inbox count, active projects, `#next` ready, who you're waiting on, review recency.

Then describe (or run, if time) the weekly ritual:
```
/gtd-weekly-review
```
**Show:** it walks the checklist — clear the inbox, review each project for a `#next`, check stale `#waiting` items, look at what's due.

Finish on the dashboard:
```
/gtd-dashboard
```
**Show:** it builds a portable `dashboard.html` you can open in any browser or on your phone — KPIs + card grid. (In Obsidian, `Dashboard.md` is the live Dataview version.)

**Point out:** the same data, three surfaces — terminal brief, Obsidian, browser/phone. You engage wherever you are.

---

## Recovery kit (if something breaks)

- **Model/network fails:** flip to your rehearsal screenshots; keep narrating — the story matters more than the pixels.
- **A skill errors:** run `/gtd-status`; it's the most robust and still makes the point.
- **Inbox already empty for Demo 2:** capture two items live first — that just demos Demo 1 again, which is fine.
- **Running long:** skip the live `/gtd-weekly-review` in Demo 5 and just show `/gtd-status` + the dashboard.

## The five commands, at a glance

| Demo | Command | One-line point |
|------|---------|----------------|
| 1 Capture | `/gtd-capture <thought>` | Get it out of your head in 2 seconds |
| 2 Clarify | `/gtd-process-inbox` | Walk the decision tree to inbox zero |
| 3 Engage | `/gtd-next-actions` | What fits *this* context, time, energy |
| 4 Remember | `/gtd-summarize-meetings` | Meeting → filed, assigned follow-through |
| 5 Review | `/gtd-status` · `/gtd-weekly-review` · `/gtd-dashboard` | Keep the system trustworthy |
