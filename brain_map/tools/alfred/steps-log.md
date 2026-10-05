---
type: Tool
title: steps_log
description: Save how many steps the user walked on a day (he tells you; a later number
  for the same day replaces it). Returns the day against his daily step goal and the
  last 7 days.
id: steps_log
server: alfred
kind: builtin
short: steps_log
capabilities: [training.steps]
modules: [training]
side_effect: read
requires_confirmation: false
status: online
params: [steps, date]
tags: [tool, alfred]
timestamp: '2026-10-04T21:08:27+02:00'
---

# steps_log

Save how many steps the user walked on a day (he tells you; a later number for the same day replaces it). Returns the day against his daily step goal and the last 7 days.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Steps](../../capabilities/training.steps.md) (`training.steps`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `steps` | integer | yes |  |
| `date` | string |  | YYYY-MM-DD, default today; 'wczoraj' = yesterday |
