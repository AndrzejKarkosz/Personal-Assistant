---
type: Tool
title: delete_water
description: Delete a water log entry by ID.
id: nutrition__delete_water
server: nutrition
kind: mcp
short: delete_water
capabilities: []
modules: []
side_effect: destructive
requires_confirmation: true
status: online
params: [id]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# delete_water

Delete a water log entry by ID.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the water entry to delete, from get_water_today or get_water_by_date. |
