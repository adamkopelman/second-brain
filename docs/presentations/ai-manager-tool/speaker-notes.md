# Facilitator Guide — *The AI Chief of Staff*

A 30-minute talk + live demo on using AI as a management tool, demoed on this GTD second brain.

**Audience:** managers / knowledge workers new to using AI as more than a chatbot.
**Goal they leave with:** one concrete loop they can run on their own inbox this week.
**Format:** ~18 min talk, ~10 min live demo woven in, ~2 min Q&A buffer.

Open `slides.html` in a browser. Navigate with **← / →** (or click), **F** for fullscreen, number shows bottom-right. Each slide below lists its target time and what to say. Keep the demo terminal (Claude Code) open in a second window so you can flip to it on the demo slides.

---

## Timing map (30:00)

| # | Slide | Cum. time | Budget |
|---|-------|-----------|--------|
| 1 | Title | 0:00 | 0:45 |
| 2 | The premise | 0:45 | 2:00 |
| 3 | Chatbot → operator | 2:45 | 2:00 |
| 4 | The five jobs | 4:45 | 1:45 |
| 5 | The demo system | 6:30 | 2:00 |
| 6 | Mental model | 8:30 | 1:45 |
| 7 | **Demo 1 — Capture** | 10:15 | 2:30 |
| 8 | **Demo 2 — Clarify** | 12:45 | 2:30 |
| 9 | **Demo 3 — Engage** | 15:15 | 2:30 |
| 10 | **Demo 4 — Meetings** | 17:45 | 3:00 |
| 11 | **Demo 5 — Review** | 20:45 | 2:30 |
| 12 | Six more plays | 23:15 | 2:00 |
| 13 | Why it works | 25:15 | 1:30 |
| 14 | Pitfalls | 26:45 | 1:30 |
| 15 | Set it up | 28:15 | 1:15 |
| 16 | Recap + CTA | 29:30 | 0:30 → **30:00** |

If you're running long, the compressible slides are 3, 13, and 14. Never cut the meeting demo (10) — it's the one that sells it.

---

## Slide-by-slide

### 1 — Title (0:45)
Set the frame in one line: *"For the next half hour I want to change one habit — how you use AI. Most people use it like a smarter Google. I'm going to show you how to use it like a chief of staff that never sleeps and never drops a ball."* Name that there's a live demo on a real system.

### 2 — The premise (2:00)
Land the reframe: managers don't fail because they don't *know* things — they fail because they can't *hold* everything at once. Ask for a show of hands: *"Who's dropped a follow-up in the last week?"* Everyone. That dropped ball is the enemy. AI's job here isn't to be clever — it's to hold the state.

### 3 — Chatbot → operator (2:00)
The core distinction of the whole talk. Chatbot = ask, answer, gone. Operator = a named routine that reads and writes a store you own, and files the result. Point at the two `/gtd-*` commands at the bottom — *"these are verbs you delegate, and you'll see them run in a minute."*

### 4 — The five jobs (1:45)
Walk the row left to right: Capture → Clarify → Prioritise → Remember → Review. This is GTD. Key line: *"AI doesn't replace the method — it removes the friction that makes people quit the method."* Everyone's tried a to-do system and quit; the quitting is a friction problem.

### 5 — The demo system (2:00)
Introduce the vault. Emphasise: **it's just markdown files in folders.** No app to learn, no database. State lives in tags (`#next`, `#waiting`, contexts). Point at the folder tree. Say: *"This is the entire 'database.' You could read it in Notepad."*

### 6 — Mental model (1:45)
The four-node flow: You say it → skill runs → vault gets a markdown line → you see it anywhere. Then the three cards: plain text (you own it), skills+MCP (verbs + real tools), human-in-loop (you confirm). This is the conceptual anchor before the live demo.

### 7 — Demo 1 · Capture (2:30) → **FLIP TO TERMINAL**
Run it live (see `demo-script.md`, Demo 1). Type a *real* thought you actually have. Show it land in `00 Inbox`. The point to say out loud: *"I didn't decide where it goes, didn't switch apps, didn't break my train of thought. Two seconds."*

### 8 — Demo 2 · Clarify (2:30) → **TERMINAL**
Run `/gtd-process-inbox`. Let it walk one item through the decision tree. Narrate the questions: actionable? one step or many? whose is it? Show it turn a vague note into a project with a first action. *"This is the step everyone skips — and it's why their to-do list becomes a graveyard."*

### 9 — Demo 3 · Engage (2:30) → **TERMINAL**
Ask in plain English: *"what can I do at my computer in 15 minutes?"* Show it filter. The insight: *"The useful list isn't everything — it's what fits this moment. Context, time, energy."*

### 10 — Demo 4 · Meetings (3:00) → **TERMINAL** — *the money slide*
Run `/gtd-summarize-meetings` on a sample transcript. Show it produce notes + decisions + action items, with owners, and turn delegated items into `#waiting`. Say: *"This is the one that pays for the whole system. The meeting is over and the follow-through already exists — filed, assigned, tracked."* If you only nail one demo, nail this one.

### 11 — Demo 5 · Review (2:30) → **TERMINAL**
Run `/gtd-status` for the 10-second brief, then talk through `/gtd-weekly-review` and show the `Dashboard`. Message: *"A second brain you don't trust is just another pile. The weekly review is what keeps the trust."*

### 12 — Six more plays (2:00) → back to slides
Rapid fire — don't demo these, just plant seeds. Email triage, 1:1 prep, waiting-for tracker, decision log, draft-from-notes, priority brief. *"Same pattern, different verb. Once you see it, you'll spot these everywhere in your week."*

### 13 — Why it works (1:30)
The four principles: you own the data, small verbs not one big brain, human in the loop, context compounds. This is the "why this and not the last productivity app" slide.

### 14 — Pitfalls (1:30)
Be honest — earns credibility. Don't automate a broken process; verify before you trust; mind what you feed it (secrets, HR, anything you can't own); don't over-automate away the thinking.

### 15 — Set it up (1:15)
The 5-step on-ramp + the modest stack (Claude Code / Obsidian / optional MCP). *"No new SaaS bill. You could do step one on the train home."*

### 16 — Recap + CTA (0:30)
Land the one action: **pick one loop, run it for a week.** Capture, or meetings, then add the weekly review. Close on the one-liner: *"Don't ask AI to be smart. Ask it to hold the state — so you can be."* Then open Q&A and offer to run any loop live on an audience member's real inbox.

---

## Q&A — likely questions & crisp answers

- **"Is my data safe / where does it live?"** It's markdown on your machine (or your org's git). You choose what an AI session can see. Nothing proprietary; export is just copying files.
- **"Do I need to be technical?"** No. You talk in plain English; the skills are the technical part and they're pre-built. Obsidian is a free note app.
- **"Won't it hallucinate my tasks?"** It can. That's why every step is human-in-the-loop and every file is readable. You glance and confirm — you don't act blind.
- **"How is this different from [Notion AI / Copilot / etc.]?"** Those are features bolted onto an app you don't own. This is plain text + named routines you understand, portable across any AI harness.
- **"What does it cost?"** An AI subscription you likely already have + free Obsidian. The MCP connectors (Outlook/Gmail/Drive) are optional.
- **"Where do I start?"** One loop. Capture for a week, or summarise every meeting. Don't build the whole thing on day one.

## Pre-flight checklist (do this 10 min before)
- [ ] `slides.html` open, fullscreen tested, on the right monitor.
- [ ] Claude Code open in the vault with `/gtd-status` already run once (warms context).
- [ ] A sample meeting transcript staged for Demo 4 (see `demo-script.md`).
- [ ] A couple of inbox items pre-captured so `/gtd-process-inbox` has something to chew.
- [ ] Font size in the terminal bumped up so the back row can read it.
- [ ] Wi-Fi / model access confirmed. Have screenshots as a fallback if the network dies.
