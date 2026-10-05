---
type: Tool
title: get_meals_by_date
description: 'Get all meals for a specific date, one compact line each with ids (detail:
  "full" adds notes).'
id: nutrition__get_meals_by_date
server: nutrition
kind: mcp
short: get_meals_by_date
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [date, detail]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_meals_by_date

Get all meals for a specific date, one compact line each with ids (detail: "full" adds notes).

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `date` | string | yes | Date in YYYY-MM-DD format |
| `detail` | string |  | How much to return per meal. "compact" (default): one line each — local time, type, description, calories and nutrients, and the id update_meal/delete_meal take |
