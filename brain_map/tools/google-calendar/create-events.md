---
type: Tool
title: create-events
description: Create multiple calendar events in bulk. Accepts shared defaults (account,
  calendarId, timeZone) that apply to all events, with per-event overrides. Skips
  conflict and duplicate detection for speed.
id: google-calendar__create-events
server: google-calendar
kind: mcp
short: create-events
capabilities: [calendar.write]
modules: [calendar]
side_effect: write
requires_confirmation: true
confirm_override: false
status: online
params: [account, calendarId, timeZone, sendUpdates, events]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# create-events

Create multiple calendar events in bulk. Accepts shared defaults (account, calendarId, timeZone) that apply to all events, with per-event overrides. Skips conflict and duplicate detection for speed.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Change the calendar](../../capabilities/calendar.write.md) (`calendar.write`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Default account for all events. Individual events can override this. |
| `calendarId` | string |  | Default calendar ID for all events (use 'primary' for the main calendar). Individual events can override this. Defaults to 'primary' if not specified. |
| `timeZone` | string |  | Default IANA timezone for all events (e.g., 'America/Los_Angeles'). Individual events can override this. |
| `sendUpdates` | string |  | Default notification setting for all events. Individual events can override this. |
| `events` | array | yes | Array of events to create (1-50 events) |
