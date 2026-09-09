---
type: dashboard
cssclasses: [dashboard]
---

# 🧠 Second Brain — Dashboard

> Live view. Requires the Dataview plugin. Portable snapshot: `/gtd-dashboard`.

## 📥 Inbox
```dataview
LIST FROM "00 Inbox" SORT file.ctime ASC
```

## ⚡ Next Actions — by context
```dataview
TASK
WHERE !completed AND contains(tags, "#next") AND !contains(tags, "#waiting")
WHERE !scheduled OR scheduled <= date(today)
GROUP BY filter(tags, (t) => t = "#computer" OR t = "#phone" OR t = "#errands" OR t = "#home" OR t = "#office" OR t = "#anywhere" OR t = "#agenda")[0] AS "Context"
SORT due ASC
```

## 🔥 Due soon (7 days)
```dataview
TASK WHERE !completed AND due AND due <= date(today) + dur(7 days) SORT due ASC
```

## ⏳ Waiting For
```dataview
TASK WHERE !completed AND contains(tags, "#waiting") SORT since ASC
```

## 📋 Active Projects
```dataview
TABLE status, area, review AS "Next review"
FROM "10 Projects" WHERE type = "project" AND status = "active" SORT review ASC
```

## 🗓️ Projects needing review
```dataview
TABLE review AS "Review due"
FROM "10 Projects" WHERE type = "project" AND status = "active" AND review <= date(today) SORT review ASC
```

## 💤 Someday / Maybe
```dataview
LIST FROM "10 Projects" WHERE type = "project" AND status = "someday"
```
