---
type: Tool
title: delete_weight
description: Delete a weight log entry by ID.
id: nutrition__delete_weight
server: nutrition
kind: mcp
short: delete_weight
capabilities: [weight.fix]
modules: [weight]
side_effect: destructive
requires_confirmation: true
status: online
params: [id]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# delete_weight

Delete a weight log entry by ID.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Correct or delete entries](../../capabilities/weight.fix.md) (`weight.fix`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the weight entry to delete, from get_weight_today, get_weight_by_date or get_weight_by_date_range. |
