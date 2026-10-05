---
type: Skill
title: Plan the training week
description: Plan next week's triathlon sessions around work, the calendar and the
  productivity routine
id: training.training-week
module: training
uses: [training.status, calendar.read, tasks.manage, weight.read, memory.recall]
tags: [skill, training]
timestamp: '2026-10-04T19:05:26+02:00'
---

# Plan the training week

Plan next week's triathlon sessions around work, the calendar and the productivity routine

Module: [training](../modules/training.md)

## Uses
- [Training plan and Strava](../capabilities/training.status.md) (`training.status`)
- [Read the calendar](../capabilities/calendar.read.md) (`calendar.read`)
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)
- [Diet and weight progress](../capabilities/weight.read.md) (`weight.read`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)

## Procedure

1. training_status (weeks 4): the phase, next week's volume, what was missed last week, the easy share.
2. Read next week in the calendar and his open work tasks (SmartMeet, Praca) with a due date. A heavy week (many
   meetings, several work deadlines) -> 20-30% less volume, one quality session kept.
3. Propose the week in at most four sentences: per day sport, duration, easy or quality; the long ride and long run on
   the weekend; nothing during the deep-work peak; no hard session after a brick or a late work day.
4. For each risky session one "if X, then Y" and one cue (e.g. "buty przy drzwiach").
5. After his yes, create the sessions as tasks (one task_create call, due at the session time, category Reszta,
   goal "przygotowanie do 1/2 Ironmana") or as calendar events if he prefers.
