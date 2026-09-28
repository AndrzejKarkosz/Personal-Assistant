---
type: Capability
title: Change the calendar
description: Create, move, update, cancel events and answer invitations.
id: calendar.write
module: calendar
tools: []
tool_patterns: [google-calendar__create-*, google-calendar__update-*, google-calendar__delete-*,
  google-calendar__respond-*]
available: 0
confirm: true
always: false
examples: [dodaj spotkanie w poniedziałek o 10, przesuń spotkanie na piątek, cancel
    tomorrow's call]
used_by: ['module:bookings', 'skill:bookings.restaurant-table']
tags: [capability, calendar]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Change the calendar

Create, move, update, cancel events and answer invitations.

Module: [calendar](../modules/calendar.md)

## Tools
- no tool connected yet (expects google-calendar__create-*, google-calendar__update-*, google-calendar__delete-*, google-calendar__respond-*)

## Used by
- module:bookings
- skill:bookings.restaurant-table

## Example requests
- dodaj spotkanie w poniedziałek o 10
- przesuń spotkanie na piątek
- cancel tomorrow's call
