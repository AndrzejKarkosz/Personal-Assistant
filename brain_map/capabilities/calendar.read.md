---
type: Capability
title: Read the calendar
description: List, search and open events, check free/busy time and the current time.
id: calendar.read
module: calendar
tools: []
tool_patterns: [google-calendar__list-*, google-calendar__search-*, google-calendar__get-*]
available: 0
confirm: false
always: false
examples: ['co mam jutro?', 'kiedy mam wolne w czwartek?', what's my next meeting]
used_by: ['skill:calendar.daily-brief']
tags: [capability, calendar]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Read the calendar

List, search and open events, check free/busy time and the current time.

Module: [calendar](../modules/calendar.md)

## Tools
- no tool connected yet (expects google-calendar__list-*, google-calendar__search-*, google-calendar__get-*)

## Used by
- skill:calendar.daily-brief

## Example requests
- co mam jutro?
- kiedy mam wolne w czwartek?
- what's my next meeting
