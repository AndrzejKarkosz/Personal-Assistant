---
type: Tool
title: list-calendars
description: List all available calendars
id: google-calendar__list-calendars
server: google-calendar
kind: mcp
short: list-calendars
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# list-calendars

List all available calendars

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | any |  | Account nickname(s) to query (e.g., 'work' or ['work', 'personal']). Omit to query all accounts. |
