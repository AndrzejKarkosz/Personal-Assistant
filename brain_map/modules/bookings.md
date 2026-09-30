---
type: Module
title: Reservations and bookings
description: Booking a table in a restaurant, an appointment, tickets or a service;
  checking availability.
id: bookings
capabilities: [bookings.browse, bookings.confirm]
uses: [research.web, calendar.write, memory.recall, memory.remember, tasks.manage]
skills: [bookings.restaurant-table]
servers: [alfred, anthropic, google-calendar]
examples: [zarezerwuj stolik dla dwóch na piątek na 19, book a haircut next week,
  sprawdź czy są bilety do kina na sobotę]
enabled: true
model: null
effort: medium
tags: [module]
timestamp: '2026-09-29T10:16:23+02:00'
---

# Reservations and bookings

Booking a table in a restaurant, an appointment, tickets or a service; checking availability.

## Capabilities
- [Operate a web browser](../capabilities/bookings.browse.md) (`bookings.browse`)
- [Ask the user before an irreversible step](../capabilities/bookings.confirm.md) (`bookings.confirm`)

## Borrowed capabilities
- [Search and read the web](../capabilities/research.web.md) (`research.web`)
- [Change the calendar](../capabilities/calendar.write.md) (`calendar.write`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)

## Skills
- [Book a restaurant table](../skills/bookings.restaurant-table.md)

## Connected servers
- [alfred](../servers/alfred.md)
- [anthropic](../servers/anthropic.md)
- [google-calendar](../servers/google-calendar.md)

## Example requests
- zarezerwuj stolik dla dwóch na piątek na 19
- book a haircut next week
- sprawdź czy są bilety do kina na sobotę
