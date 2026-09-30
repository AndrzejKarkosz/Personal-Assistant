---
type: Tool
title: get-event
description: Get details of a specific event by ID.
id: google-calendar__get-event
server: google-calendar
kind: mcp
short: get-event
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account, calendarId, eventId, fields]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# get-event

Get details of a specific event by ID.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
| `calendarId` | string | yes | ID of the calendar (use 'primary' for the main calendar) |
| `eventId` | string | yes | ID of the event to retrieve |
| `fields` | array |  | Optional array of additional event fields to retrieve. Available fields are strictly validated. Default fields (id, summary, start, end, status, htmlLink, locat |
