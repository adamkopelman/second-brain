# Demo Script — *The AI Chief of Staff*

Five stops in one Tuesday. **Two run live, three are shown as output.** Being clear with yourself about which is which is what keeps the session honest and stress-free.

| Stop | Mode | Why |
|------|------|-----|
| 08:40 Inbox | **shown** | Mail connector needs setup; not worth the live risk |
| 09:30 Standup → actions | **LIVE** | Works out of the box (`gtd-summarize-meetings`) |
| 11:00 Prep from last time | **LIVE** | Pure vault query — the most reliable demo you have |
| 14:00 Sprint review | **shown** | No tracker connector in the vault today |
| 16:30 It drafts, you send | **shown** | Sending mail isn't implemented — deliberately |

> **Rehearse once, end to end, and screenshot every result.** Those screenshots are your fallback if the network dies mid-session, and they're what you'll paste into the slides.

---

## Before the session

### 1. Stage the meeting history — *don't skip this*

The 11:00 demo is the best thing in the session and it **needs a prior meeting to read**. If `Meetings/` is empty it has nothing to say and the moment dies.

Put at least one older meeting record in `Meetings/` — dated a week or two back, with an unresolved decision and someone who owes something. For example: an architecture sync where a datastore decision got deferred and a teammate owed a spike.

### 2. Stage today's transcript

Drop a short, realistic standup transcript into `Meetings/` for the 09:30 demo. A paragraph is plenty — mention a release decision, someone blocked on a review, and something you're waiting on.

### 3. Warm the session

```
/gtd-status
```

### 4. Swap in your real output (optional, high value)

Run the inbox triage, sprint review and end-of-day list against your own data, screenshot the results, and drop them into slides 4, 7 and 8. *"Here's what mine said this morning"* beats any example — just check nothing on screen is sensitive.

---

## 08:40 · Inbox — **shown** (slide 4)

**Say:** "I don't need it writing my email. I need it telling me which four of forty I can't ignore."

**The ask on the slide:**
> "Go through this morning's mail. What needs a decision from me, what's FYI, and who's waiting on me?"

**Point at:** the split — 4 need you, 12 FYI, 25 noise. Then the lesson: **its attention for your judgment.** Say it here; slides 5–8 are all variations of it.

**If asked "is that live?"** — be straight. "That's this morning's output. The mail connector needs setting up; the meeting flows I'm about to run are live."

---

## 09:30 · Standup → action items — **LIVE** (slide 5)

**Say:** "The worst thing you can do with a meeting is remember it."

```
/gtd-summarize-meetings
```

**Show:** decisions, action items **with owners**, and the `#waiting` item with a person and a date attached.

**Narrate the ask as you run it** — that's the teaching. "Notice I'm not asking for a summary. I'm asking for decisions, owners, and anything I'm now waiting on."

**Point out:** the `#waiting [[Roi]]` line. For a new team lead, an automatic record of who owes them what is worth the whole session.

---

## 11:00 · Prep from last time — **LIVE** · *the money demo* (slide 6)

**Say:** "This is the one that changed the job for me."

```
I have the architecture sync in 10 minutes. What's still open from last time?
```

**Show:** still-open items, what's changed since, and a suggested agenda — all assembled from records that already existed. **Nothing new was typed.**

**Let this line land:** *"deferred twice."* Every new lead in the room has a decision that's been quietly deferred twice.

**Then be rigorous:** "This only works because of the 09:30 step. If I hadn't summarised that meeting, this screen is empty." That honesty is what makes Monday's ask credible.

---

## 14:00 · Sprint review — **shown** (slide 7)

**Do the contrast out loud before revealing the output:**

- Weak: *"Summarise the sprint."* → a list of tickets you could have read yourself.
- Strong: *"Compare this sprint to the last three. What's going wrong, and what should I raise with the team?"*

**Show:** the carry-over trend, the epic swallowing it, the review-load imbalance, the reopen rate.

**Land on the Dana bullet:** "*Dana reviewed 3× anyone else* is a people problem your board will never raise." Then hand off explicitly to the rest of the day — that's the session earning its place in a soft-skills programme.

---

## 16:30 · It drafts, you send — **shown** (slide 8)

**Say:** "Two of these it can write. Two it shouldn't touch."

**The ask:**
> "What's still on me today? Draft what you can."

**Show:** two drafts ready, two marked *only you* (the code review and the escalation decision), and the waiting-on list with ages.

**The line to deliver slowly:** **"Nothing sent. Pressing send is a promise from you to another person — that never gets delegated."**

This is the judgment beat of the whole session. Don't rush it, and don't undercut it by joking about letting it send anyway.

---

## Recovery kit

- **Network dies:** switch to rehearsal screenshots and keep narrating. The story carries it — nobody came for the pixels.
- **A skill errors:** fall back to `/gtd-status`; it's the most robust command and still makes the point.
- **`Meetings/` turns out empty:** run the 09:30 demo first, then use *its* output as the history for 11:00. Weaker, but it works.
- **Running long:** cut the 08:40 stop and compress 14:00. Never cut 11:00.
- **Someone asks for a live JIRA or email demo:** "Not today — those need connectors wired to your own accounts. Happy to show you the setup afterwards."

## The two commands you actually type

| Stop | Command |
|------|---------|
| 09:30 | `/gtd-summarize-meetings` |
| 11:00 | `"[meeting] in 10 minutes. What's still open from last time?"` |

Everything else is output you're showing. Two live commands is a feature — it's very hard for the demo to go wrong.
