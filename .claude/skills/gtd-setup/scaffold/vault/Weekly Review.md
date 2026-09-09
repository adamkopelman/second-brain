---
type: reference
tags: [system, gtd, review]
---

# 🔄 Weekly Review

Run weekly (`/gtd-weekly-review` walks you through it).

## Get Clear
- [ ] Empty the inbox (`/gtd-process-inbox`)
- [ ] Collect loose notes; empty your head

## Get Current
- [ ] Review `Dashboard.md`; clear stale next actions
- [ ] Each active project has a `#next`?
- [ ] Chase stale `#waiting` (`[since::]`)
- [ ] Calendar: past week + next two weeks (Outlook via `/gtd-outlook`)
- [ ] `People/` agendas; bump `review:` dates

## Get Creative
- [ ] Promote ready Someday/Maybe
- [ ] Review `20 Areas/`; archive done projects to `40 Archive/`

---

## Review log
```dataview
TABLE file.ctime AS "Reviewed" FROM "Journal" WHERE contains(tags, "weekly-review") SORT file.ctime DESC LIMIT 8
```
