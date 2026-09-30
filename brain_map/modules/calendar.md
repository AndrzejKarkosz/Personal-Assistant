---
type: Module
title: Calendar and schedule
description: Meetings, events, appointments, free time, what is planned for a day
  or week; creating, moving or cancelling events.
id: calendar
capabilities: [calendar.read, calendar.write]
uses: [tasks.manage, memory.recall, bookings.confirm]
skills: [calendar.daily-brief]
servers: [alfred, google-calendar]
examples: ['co mam jutro w kalendarzu?', przesuń spotkanie z Tomkiem na piątek, what's
    on my schedule this week, add a dentist appointment on Monday at 10]
enabled: true
model: null
effort: null
tags: [module]
timestamp: '2026-09-30T17:50:37+02:00'
---

# Calendar and schedule

Meetings, events, appointments, free time, what is planned for a day or week; creating, moving or cancelling events.

## Capabilities
- [Read the calendar](../capabilities/calendar.read.md) (`calendar.read`)
- [Change the calendar](../capabilities/calendar.write.md) (`calendar.write`)

## Borrowed capabilities
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Ask the user before an irreversible step](../capabilities/bookings.confirm.md) (`bookings.confirm`)

## Skills
- [Daily brief](../skills/calendar.daily-brief.md)

## Connected servers
- [alfred](../servers/alfred.md)
- [google-calendar](../servers/google-calendar.md)

## Example requests
- co mam jutro w kalendarzu?
- przesuń spotkanie z Tomkiem na piątek
- what's on my schedule this week
- add a dentist appointment on Monday at 10
