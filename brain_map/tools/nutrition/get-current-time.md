---
type: Tool
title: get_current_time
description: Get the current date and time in the user's timezone as saved in this
  nutrition tracker, plus the UTC instant. Use it to resolve 'today', 'this morning',
  'an hour ago' or 'last Monday' into a timestamp for entries logged here, instead
  of as
id: nutrition__get_current_time
server: nutrition
kind: mcp
short: get_current_time
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_current_time

Get the current date and time in the user's timezone as saved in this nutrition tracker, plus the UTC instant. Use it to resolve 'today', 'this morning', 'an hour ago' or 'last Monday' into a timestamp for entries logged here, instead of asking the user or guessing. Not needed to log something that is happening now: omit logged_at and the server stamps the current time itself.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities
