---
type: Tool
title: create-event
description: Create a new calendar event.
id: google-calendar__create-event
server: google-calendar
kind: mcp
short: create-event
capabilities: [calendar.write]
modules: [calendar]
side_effect: write
requires_confirmation: true
confirm_override: false
status: online
params: [account, calendarId, eventId, summary, description, start, end, timeZone,
  location, attendees, colorId, reminders, recurrence, transparency, visibility, guestsCanInviteOthers,
  guestsCanModify, guestsCanSeeOtherGuests, anyoneCanAddSelf, sendUpdates, conferenceData,
  extendedProperties, attachments, source, calendarsToCheck, duplicateSimilarityThreshold,
  allowDuplicates, eventType, focusTimeProperties, outOfOfficeProperties, workingLocationProperties]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# create-event

Create a new calendar event.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Change the calendar](../../capabilities/calendar.write.md) (`calendar.write`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
| `calendarId` | string | yes | ID of the calendar (use 'primary' for the main calendar) |
| `eventId` | string |  | Optional custom event ID (5-1024 characters, base32hex encoding: lowercase letters a-v and digits 0-9 only). If not provided, Google Calendar will generate one. |
| `summary` | string | yes | Title of the event |
| `description` | string |  | Description/notes for the event |
| `start` | string | yes | Event start time. String format: '2025-01-01T10:00:00' (timed) or '2025-01-01' (all-day). For per-field timezone, use JSON: '{"dateTime": "2025-01-01T10:00:00", |
| `end` | string | yes | Event end time. String format: '2025-01-01T11:00:00' (timed) or '2025-01-02' (all-day, exclusive). For per-field timezone, use JSON: '{"dateTime": "2025-01-01T1 |
| `timeZone` | string |  | Timezone as IANA Time Zone Database name (e.g., America/Los_Angeles). Takes priority over calendar's default timezone. Only used for timezone-naive datetime str |
| `location` | string |  | Location of the event |
| `attendees` | array |  | List of event attendees with their details |
| `colorId` | string |  | Color ID for the event (use list-colors to see available IDs) |
| `reminders` | object |  | Reminder settings for the event |
| `recurrence` | array |  | Recurrence rules in RFC5545 format (e.g., ["RRULE:FREQ=WEEKLY;COUNT=5"]) |
| `transparency` | string |  | Whether the event blocks time on the calendar. 'opaque' means busy, 'transparent' means free. |
| `visibility` | string |  | Visibility of the event. Use 'public' for public events, 'private' for private events visible to attendees. |
| `guestsCanInviteOthers` | boolean |  | Whether attendees can invite others to the event. Default is true. |
| `guestsCanModify` | boolean |  | Whether attendees can modify the event. Default is false. |
| `guestsCanSeeOtherGuests` | boolean |  | Whether attendees can see the list of other attendees. Default is true. |
| `anyoneCanAddSelf` | boolean |  | Whether anyone can add themselves to the event. Default is false. |
| `sendUpdates` | string |  | Whether to send notifications about the event creation. 'all' sends to all guests, 'externalOnly' to non-Google Calendar users only, 'none' sends no notificatio |
| `conferenceData` | object |  | Conference properties for the event. Use createRequest to add a new conference. |
| `extendedProperties` | object |  | Extended properties for storing application-specific data. Max 300 properties totaling 32KB. |
| `attachments` | array |  | File attachments for the event. Requires calendar to support attachments. |
| `source` | object |  | Source of the event, such as a web page or email message. |
| `calendarsToCheck` | array |  | List of calendar IDs to check for conflicts (defaults to just the target calendar) |
| `duplicateSimilarityThreshold` | number |  | Threshold for duplicate detection (0-1, default: 0.7). Events with similarity above this are flagged as potential duplicates |
| `allowDuplicates` | boolean |  | If true, allows creation even when exact duplicates are detected (similarity >= 0.95). Default is false which blocks duplicate creation |
| `eventType` | string |  | Type of the event. 'default' for regular events, 'focusTime' for Focus Time blocks, 'outOfOffice' for Out of Office events, 'workingLocation' for Working Locati |
| `focusTimeProperties` | object |  | Focus Time properties. Only used when eventType is 'focusTime'. Requires Google Workspace. |
| `outOfOfficeProperties` | object |  | Out of Office properties. Only used when eventType is 'outOfOffice'. Requires Google Workspace. |
| `workingLocationProperties` | object |  | Working Location properties. Only used when eventType is 'workingLocation'. Requires Google Workspace. |
