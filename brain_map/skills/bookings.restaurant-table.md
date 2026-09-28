---
type: Skill
title: Book a restaurant table
description: Reserve a table in a restaurant for a given day, time and number of people
id: bookings.restaurant-table
module: bookings
uses: [memory.recall, research.web, bookings.browse, bookings.confirm, calendar.write,
  memory.remember, tasks.manage]
tags: [skill, bookings]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Book a restaurant table

Reserve a table in a restaurant for a given day, time and number of people

Module: [bookings](../modules/bookings.md)

## Uses
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Search and read the web](../capabilities/research.web.md) (`research.web`)
- [Operate a web browser](../capabilities/bookings.browse.md) (`bookings.browse`)
- [Ask the user before an irreversible step](../capabilities/bookings.confirm.md) (`bookings.confirm`)
- [Change the calendar](../capabilities/calendar.write.md) (`calendar.write`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)

## Procedure

1. Collect: restaurant (or cuisine + area), day, time, number of people. Ask one short question for anything missing.
2. Look up memory (memory_search "restaurant") for preferences and favourite places.
3. Find the restaurant's online booking page (web_search), open it in the browser, check availability.
4. If the exact slot is taken, offer the two nearest slots.
5. Call confirm_action with the full summary. Only after "approved" press the final booking button.
6. Add the reservation to the calendar (it will be confirmed too) and remember the place with memory_remember.
7. If a confirmation is expected later (SMS/email), create a task "Check the booking confirmation" due in 2 hours.
