---
type: Capability
title: Change the calendar
description: Create, move, update, cancel events and answer invitations.
id: calendar.write
module: calendar
tools: [google-calendar__create-event, google-calendar__create-events, google-calendar__delete-event,
  google-calendar__respond-to-event, google-calendar__update-event]
tool_patterns: [google-calendar__create-*, google-calendar__update-*, google-calendar__delete-*,
  google-calendar__respond-*]
available: 5
confirm: true
always: false
examples: [dodaj spotkanie w poniedziałek o 10, przesuń spotkanie na piątek, cancel
    tomorrow's call]
used_by: ['module:bookings', 'skill:bookings.restaurant-table']
tags: [capability, calendar]
timestamp: '2026-09-29T10:16:23+02:00'
---

# Change the calendar

Create, move, update, cancel events and answer invitations.

Module: [calendar](../modules/calendar.md)

## Tools
- [create-event](../tools/google-calendar/create-event.md) - google-calendar, write
- [create-events](../tools/google-calendar/create-events.md) - google-calendar, write
- [delete-event](../tools/google-calendar/delete-event.md) - google-calendar, destructive
- [respond-to-event](../tools/google-calendar/respond-to-event.md) - google-calendar, write
- [update-event](../tools/google-calendar/update-event.md) - google-calendar, destructive

## Used by
- module:bookings
- skill:bookings.restaurant-table

## Example requests
- dodaj spotkanie w poniedziałek o 10
- przesuń spotkanie na piątek
- cancel tomorrow's call
