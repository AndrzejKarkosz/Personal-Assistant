---
type: Module
title: Treningi (triathlon)
description: Triathlon training - swimming, cycling, running; the training plan and
  how it goes, workouts from Strava, planning the training week around work, recovery,
  the race and the taper.
id: training
capabilities: [training.status, training.plan, training.steps]
uses: [calendar.read, calendar.write, tasks.manage, weight.read, research.web, memory.recall,
  memory.remember]
skills: [training.training-week]
servers: [alfred, anthropic, google-calendar, nutrition, strava]
examples: ['jak mi idzie plan treningowy w tym tygodniu?', 'co dziś trenuję?', 'ile
    przepłynąłem w tym miesiącu?', zaplanuj mi treningi na przyszły tydzień, 'mam
    ciężki tydzień w pracy, co z treningami?', zrobiłem dziś 9 tysięcy kroków, 'chciałbym
    dodać crossfit raz w tygodniu, co proponujesz?', 'co mam dziś na siłowni?', how
    far am I from my weekly training target]
enabled: true
model: null
effort: null
tags: [module]
timestamp: '2026-10-05T10:16:01+02:00'
---

# Treningi (triathlon)

Triathlon training - swimming, cycling, running; the training plan and how it goes, workouts from Strava, planning the training week around work, recovery, the race and the taper.

## Capabilities
- [Training plan and Strava](../capabilities/training.status.md) (`training.status`)
- [Change the training plan](../capabilities/training.plan.md) (`training.plan`)
- [Steps](../capabilities/training.steps.md) (`training.steps`)

## Borrowed capabilities
- [Read the calendar](../capabilities/calendar.read.md) (`calendar.read`)
- [Change the calendar](../capabilities/calendar.write.md) (`calendar.write`)
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)
- [Diet and weight progress](../capabilities/weight.read.md) (`weight.read`)
- [Search and read the web](../capabilities/research.web.md) (`research.web`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)

## Skills
- [Plan the training week](../skills/training.training-week.md)

## Connected servers
- [alfred](../servers/alfred.md)
- [anthropic](../servers/anthropic.md)
- [google-calendar](../servers/google-calendar.md)
- [nutrition](../servers/nutrition.md)
- [strava](../servers/strava.md)

## Example requests
- jak mi idzie plan treningowy w tym tygodniu?
- co dziś trenuję?
- ile przepłynąłem w tym miesiącu?
- zaplanuj mi treningi na przyszły tydzień
- mam ciężki tydzień w pracy, co z treningami?
- zrobiłem dziś 9 tysięcy kroków
- chciałbym dodać crossfit raz w tygodniu, co proponujesz?
- co mam dziś na siłowni?
- how far am I from my weekly training target
