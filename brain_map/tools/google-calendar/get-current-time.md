---
type: Tool
title: get-current-time
description: Get the current date and time. Call this FIRST before creating, updating,
  or searching for events to ensure you have accurate date context for scheduling.
id: google-calendar__get-current-time
server: google-calendar
kind: mcp
short: get-current-time
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account, timeZone]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# get-current-time

Get the current date and time. Call this FIRST before creating, updating, or searching for events to ensure you have accurate date context for scheduling.

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
| `timeZone` | string |  | IANA timezone (e.g., 'America/Los_Angeles'). Defaults to calendar's timezone. |
