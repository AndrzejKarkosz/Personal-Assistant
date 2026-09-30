---
type: MCP Server
title: google-calendar
description: Google Calendar. Needs an OAuth client JSON - see README.
id: google-calendar
status: ready
tools: [google-calendar__list-calendars, google-calendar__list-events, google-calendar__search-events,
  google-calendar__get-event, google-calendar__list-colors, google-calendar__create-event,
  google-calendar__create-events, google-calendar__update-event, google-calendar__delete-event,
  google-calendar__get-freebusy, google-calendar__get-current-time, google-calendar__respond-to-event,
  google-calendar__manage-accounts]
tags: [server, mcp]
timestamp: '2026-09-29T10:16:23+02:00'
---

# google-calendar

Google Calendar. Needs an OAuth client JSON - see README.

Status: **ready**

Runs: `npx -y @cocal/google-calendar-mcp`

## Tools
- [list-calendars](../tools/google-calendar/list-calendars.md) - read
- [list-events](../tools/google-calendar/list-events.md) - read
- [search-events](../tools/google-calendar/search-events.md) - read
- [get-event](../tools/google-calendar/get-event.md) - read
- [list-colors](../tools/google-calendar/list-colors.md) - read
- [create-event](../tools/google-calendar/create-event.md) - write
- [create-events](../tools/google-calendar/create-events.md) - write
- [update-event](../tools/google-calendar/update-event.md) - destructive
- [delete-event](../tools/google-calendar/delete-event.md) - destructive
- [get-freebusy](../tools/google-calendar/get-freebusy.md) - read
- [get-current-time](../tools/google-calendar/get-current-time.md) - read
- [respond-to-event](../tools/google-calendar/respond-to-event.md) - write
- [manage-accounts](../tools/google-calendar/manage-accounts.md) - destructive
