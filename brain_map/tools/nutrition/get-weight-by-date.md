---
type: Tool
title: get_weight_by_date
description: Get weight entries for a specific date, in the user's preferred unit.
id: nutrition__get_weight_by_date
server: nutrition
kind: mcp
short: get_weight_by_date
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_weight_by_date

Get weight entries for a specific date, in the user's preferred unit.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `date` | string | yes | Date in YYYY-MM-DD format |
