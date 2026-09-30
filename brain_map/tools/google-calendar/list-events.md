---
type: Tool
title: list-events
description: List events from one or more calendars. Supports both calendar IDs and
  calendar names.
id: google-calendar__list-events
server: google-calendar
kind: mcp
short: list-events
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account, calendarId, timeMin, timeMax, timeZone, fields, privateExtendedProperty,
  sharedExtendedProperty]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# list-events

List events from one or more calendars. Supports both calendar IDs and calendar names.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | any |  | Account nickname(s) to query (e.g., 'work' or ['work', 'personal']). Omit to query all accounts. |
| `calendarId` | any | yes |  |
| `timeMin` | string |  | Start of time range (ISO 8601, e.g., '2024-01-01T00:00:00'). |
| `timeMax` | string |  | End of time range (ISO 8601, e.g., '2024-01-31T23:59:59'). |
| `timeZone` | string |  | IANA timezone (e.g., 'America/Los_Angeles'). Defaults to calendar's timezone. |
| `fields` | array |  | Additional fields to include beyond defaults (id, summary, start, end, status, htmlLink, location, attendees). |
| `privateExtendedProperty` | array |  | Filter by private extended properties (key=value). Matches events that have all specified properties. |
| `sharedExtendedProperty` | array |  | Filter by shared extended properties (key=value). Matches events that have all specified properties. |
