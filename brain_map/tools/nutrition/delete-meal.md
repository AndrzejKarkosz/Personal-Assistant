---
type: Tool
title: delete_meal
description: Delete a meal entry by ID (ids come from get_meals_today, get_meals_by_date,
  get_meals_by_date_range or search_meals).
id: nutrition__delete_meal
server: nutrition
kind: mcp
short: delete_meal
capabilities: [weight.fix]
modules: [weight]
side_effect: destructive
requires_confirmation: true
status: online
params: [id]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# delete_meal

Delete a meal entry by ID (ids come from get_meals_today, get_meals_by_date, get_meals_by_date_range or search_meals).

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Correct or delete entries](../../capabilities/weight.fix.md) (`weight.fix`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the meal to delete, from get_meals_today, get_meals_by_date, get_meals_by_date_range or search_meals. |
