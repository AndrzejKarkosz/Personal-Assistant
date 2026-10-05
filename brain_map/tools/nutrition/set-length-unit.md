---
type: Tool
title: set_length_unit
description: Set the user's preferred length unit for body measurements ('cm' or 'in'),
  or pass null to clear it. It decides how measurements are shown and which unit a
  number logged without `unit` is read in. Stored measurements keep the number and
  uni
id: nutrition__set_length_unit
server: nutrition
kind: mcp
short: set_length_unit
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [unit]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_length_unit

Set the user's preferred length unit for body measurements ('cm' or 'in'), or pass null to clear it. It decides how measurements are shown and which unit a number logged without `unit` is read in. Stored measurements keep the number and unit they were entered with; only display and default parsing change. It is independent of the weight unit. While unset, logging a measurement needs an explicit unit and each one is shown in the unit it was entered in.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `unit` | any | yes | Preferred length unit: 'cm' or 'in'. null clears the preference. |
