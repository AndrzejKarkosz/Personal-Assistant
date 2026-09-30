---
type: Tool
title: get-freebusy
description: 'Query free/busy information for calendars. Note: Time range is limited
  to a maximum of 3 months between timeMin and timeMax.'
id: google-calendar__get-freebusy
server: google-calendar
kind: mcp
short: get-freebusy
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account, calendars, timeMin, timeMax, timeZone, groupExpansionMax, calendarExpansionMax]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# get-freebusy

Query free/busy information for calendars. Note: Time range is limited to a maximum of 3 months between timeMin and timeMax.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | any |  | Account nickname(s) to query (e.g., 'work' or ['work', 'personal']). Omit to query all accounts. |
| `calendars` | array | yes | List of calendars and/or groups to query for free/busy information |
| `timeMin` | string | yes | Start of time range (ISO 8601, e.g., '2024-01-01T00:00:00'). |
| `timeMax` | string | yes | End of time range (ISO 8601, e.g., '2024-01-31T23:59:59'). |
| `timeZone` | string |  | IANA timezone for the query. |
| `groupExpansionMax` | integer |  | Maximum number of calendars to expand per group (max 100) |
| `calendarExpansionMax` | integer |  | Maximum number of calendars to expand (max 50) |
