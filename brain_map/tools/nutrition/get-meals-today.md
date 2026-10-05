---
type: Tool
title: get_meals_today
description: 'Get all meals logged today, one compact line each with ids (detail:
  "full" adds notes).'
id: nutrition__get_meals_today
server: nutrition
kind: mcp
short: get_meals_today
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [detail]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_meals_today

Get all meals logged today, one compact line each with ids (detail: "full" adds notes).

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `detail` | string |  | How much to return per meal. "compact" (default): one line each — local time, type, description, calories and nutrients, and the id update_meal/delete_meal take |
