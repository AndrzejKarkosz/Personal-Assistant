---
type: Capability
title: Read the calendar
description: List, search and open events, check free/busy time and the current time.
id: calendar.read
module: calendar
tools: [google-calendar__get-current-time, google-calendar__get-event, google-calendar__get-freebusy,
  google-calendar__list-calendars, google-calendar__list-colors, google-calendar__list-events,
  google-calendar__search-events]
tool_patterns: [google-calendar__list-*, google-calendar__search-*, google-calendar__get-*]
confirm: false
always: false
available: 7
examples: ['co mam jutro?', 'kiedy mam wolne w czwartek?', what's my next meeting]
used_by: ['skill:calendar.daily-brief', 'module:training', 'skill:training.training-week']
tags: [capability, calendar]
timestamp: '2026-10-04T19:05:26+02:00'
---

# Read the calendar

List, search and open events, check free/busy time and the current time.

Module: [calendar](../modules/calendar.md)

## Tools
- [get-current-time](../tools/google-calendar/get-current-time.md) - google-calendar, read
- [get-event](../tools/google-calendar/get-event.md) - google-calendar, read
- [get-freebusy](../tools/google-calendar/get-freebusy.md) - google-calendar, read
- [list-calendars](../tools/google-calendar/list-calendars.md) - google-calendar, read
- [list-colors](../tools/google-calendar/list-colors.md) - google-calendar, read
- [list-events](../tools/google-calendar/list-events.md) - google-calendar, read
- [search-events](../tools/google-calendar/search-events.md) - google-calendar, read

## Used by
- skill:calendar.daily-brief
- module:training
- skill:training.training-week

## Example requests
- co mam jutro?
- kiedy mam wolne w czwartek?
- what's my next meeting
