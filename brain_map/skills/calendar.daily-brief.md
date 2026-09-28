---
type: Skill
title: Daily brief
description: Summarise the day - meetings, due tasks, open threads - morning brief
  or "what's my day like"
id: calendar.daily-brief
module: calendar
uses: [calendar.read, tasks.manage, memory.recall]
tags: [skill, calendar]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Daily brief

Summarise the day - meetings, due tasks, open threads - morning brief or "what's my day like"

Module: [calendar](../modules/calendar.md)

## Uses
- [Read the calendar](../capabilities/calendar.read.md) (`calendar.read`)
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)

## Procedure

1. Read today's events from the calendar.
2. Read open tasks (task_list) and pick the ones due today or overdue.
3. Speak at most four sentences: first commitment and time, number of meetings, the most important task,
   and one open thread from the briefing if relevant.
