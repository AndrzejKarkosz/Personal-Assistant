---
type: Tool
title: update-event
description: Update an existing calendar event with recurring event modification scope
  support.
id: google-calendar__update-event
server: google-calendar
kind: mcp
short: update-event
capabilities: [calendar.write]
modules: [calendar]
side_effect: destructive
requires_confirmation: true
status: online
params: [account, calendarId, eventId, summary, description, start, end, timeZone,
  location, attendees, colorId, reminders, recurrence, sendUpdates, modificationScope,
  originalStartTime, futureStartDate, checkConflicts, calendarsToCheck, conferenceData,
  transparency, visibility, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests,
  anyoneCanAddSelf, extendedProperties, attachments]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# update-event

Update an existing calendar event with recurring event modification scope support.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Change the calendar](../../capabilities/calendar.write.md) (`calendar.write`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
| `calendarId` | string | yes | ID of the calendar (use 'primary' for the main calendar) |
| `eventId` | string | yes | ID of the event to update |
| `summary` | string |  | Updated title of the event |
| `description` | string |  | Updated description/notes |
| `start` | string |  | Updated start time. String format: '2025-01-01T10:00:00' (timed) or '2025-01-01' (all-day). For per-field timezone, use JSON: '{"dateTime": "2025-01-01T10:00:00 |
| `end` | string |  | Updated end time. String format: '2025-01-01T11:00:00' (timed) or '2025-01-02' (all-day, exclusive). For per-field timezone, use JSON: '{"dateTime": "2025-01-01 |
| `timeZone` | string |  | Updated timezone as IANA Time Zone Database name. If not provided, uses the calendar's default timezone. |
| `location` | string |  | Updated location |
| `attendees` | array |  | Updated attendee list |
| `colorId` | string |  | Updated color ID |
| `reminders` | object |  | Reminder settings for the event |
| `recurrence` | array |  | Recurrence rules in RFC5545 format (e.g., ["RRULE:FREQ=WEEKLY;COUNT=5"]) |
| `sendUpdates` | string |  | Whether to send update notifications |
| `modificationScope` | string |  | Scope for recurring event modifications |
| `originalStartTime` | string |  | Original start time in the ISO 8601 format '2024-01-01T10:00:00' |
| `futureStartDate` | string |  | Start date for future instances in the ISO 8601 format '2024-01-01T10:00:00' |
| `checkConflicts` | boolean |  | Whether to check for conflicts when updating (default: true when changing time) |
| `calendarsToCheck` | array |  | List of calendar IDs to check for conflicts (defaults to just the target calendar) |
| `conferenceData` | object |  | Conference properties for the event. Used to add or update Google Meet links. |
| `transparency` | string |  | Whether the event blocks time on the calendar. 'opaque' means busy, 'transparent' means available |
| `visibility` | string |  | Visibility of the event |
| `guestsCanInviteOthers` | boolean |  | Whether attendees other than the organizer can invite others |
| `guestsCanModify` | boolean |  | Whether attendees other than the organizer can modify the event |
| `guestsCanSeeOtherGuests` | boolean |  | Whether attendees other than the organizer can see who the event's attendees are |
| `anyoneCanAddSelf` | boolean |  | Whether anyone can add themselves to the event |
| `extendedProperties` | object |  | Extended properties for storing application-specific data. Max 300 properties totaling 32KB. |
| `attachments` | array |  | File attachments for the event |
