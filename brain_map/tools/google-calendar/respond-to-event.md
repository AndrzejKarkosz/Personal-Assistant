---
type: Tool
title: respond-to-event
description: Respond to a calendar event invitation with Accept, Decline, Maybe (Tentative),
  or No Response.
id: google-calendar__respond-to-event
server: google-calendar
kind: mcp
short: respond-to-event
capabilities: [calendar.write]
modules: [calendar]
side_effect: write
requires_confirmation: true
confirm_override: false
status: online
params: [calendarId, eventId, account, response, comment, modificationScope, originalStartTime,
  sendUpdates]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# respond-to-event

Respond to a calendar event invitation with Accept, Decline, Maybe (Tentative), or No Response.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Change the calendar](../../capabilities/calendar.write.md) (`calendar.write`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `calendarId` | string | yes | ID of the calendar (use 'primary' for the main calendar) |
| `eventId` | string | yes | ID of the event to respond to |
| `account` | string |  | Account nickname to use for this operation (e.g., 'work', 'personal'). Optional when only one account is connected - will auto-select the account with appropria |
| `response` | string | yes | Your response to the event invitation: 'accepted' (accept), 'declined' (decline), 'tentative' (maybe), 'needsAction' (no response) |
| `comment` | string |  | Optional message/note to include with your response (e.g., 'I have a conflict' when declining) |
| `modificationScope` | string |  | For recurring events: 'thisEventOnly' responds to just this instance, 'all' responds to all instances. Default is 'all'. |
| `originalStartTime` | string |  | Original start time of the specific instance (required when modificationScope is 'thisEventOnly') |
| `sendUpdates` | string |  | Whether to send response notifications. 'all' sends to all guests, 'externalOnly' to non-Google Calendar users only, 'none' sends no notifications. Default is ' |
