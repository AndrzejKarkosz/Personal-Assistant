---
type: Tool
title: list-colors
description: List available color IDs and their meanings for calendar events
id: google-calendar__list-colors
server: google-calendar
kind: mcp
short: list-colors
capabilities: [calendar.read]
modules: [calendar]
side_effect: read
requires_confirmation: false
status: online
params: [account]
tags: [tool, google-calendar]
timestamp: '2026-09-29T10:16:23+02:00'
---

# list-colors

List available color IDs and their meanings for calendar events

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- [Read the calendar](../../capabilities/calendar.read.md) (`calendar.read`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `account` | string |  | Account nickname (e.g., 'work'). Optional if only one account connected. |
