---
type: Tool
title: update_weight
description: Update fields of an existing weight entry. Provide `unit` alongside `weight`
  (defaults to the user's preferred unit); do NOT convert units yourself.
id: nutrition__update_weight
server: nutrition
kind: mcp
short: update_weight
capabilities: [weight.fix]
modules: [weight]
side_effect: destructive
requires_confirmation: true
status: online
params: [id, weight, unit, logged_at, notes]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# update_weight

Update fields of an existing weight entry. Provide `unit` alongside `weight` (defaults to the user's preferred unit); do NOT convert units yourself.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Correct or delete entries](../../capabilities/weight.fix.md) (`weight.fix`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the weight entry to update, from get_weight_today, get_weight_by_date or get_weight_by_date_range. |
| `weight` | number |  | New weight value, in `unit`. |
| `unit` | string |  | Unit of the weight value. Defaults to the user's preferred weight unit. |
| `logged_at` | string |  | When the weight was measured. Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time ("2026-01-05T08:30" |
| `notes` | string |  |  |
