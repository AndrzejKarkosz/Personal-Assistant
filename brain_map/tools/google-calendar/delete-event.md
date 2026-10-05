---
type: Tool
title: delete-event
description: Delete a calendar event.
id: google-calendar__delete-event
server: google-calendar
kind: mcp
short: delete-event
capabilities: [calendar.write]
modules: [calendar]
side_effect: destructive
requires_confirmation: true
confirm_override: false
status: online
params: [account, calendarId, eventId, sendUpdates]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# delete-event

Delete a calendar event.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Change the calendar](../../capabilities/calendar.write.md) (`calendar.write`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
| `calendarId` | string | yes | ID of the calendar (use 'primary' for the main calendar) |
| `eventId` | string | yes | ID of the event to delete |
| `sendUpdates` | string |  | Whether to send cancellation notifications |
