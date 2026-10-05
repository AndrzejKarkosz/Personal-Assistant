---
type: Tool
title: get_weight_trends
description: 'Weight trend over a window: latest reading, overall change, a smoothed
  trend weight with its weekly rate over the last 2 weeks (which filters out day-to-day
  water swings), min/max, and progress toward the target weight if one is set. Aggreg'
id: nutrition__get_weight_trends
server: nutrition
kind: mcp
short: get_weight_trends
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [days, end_date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_weight_trends

Weight trend over a window: latest reading, overall change, a smoothed trend weight with its weekly rate over the last 2 weeks (which filters out day-to-day water swings), min/max, and progress toward the target weight if one is set. Aggregates multiple weigh-ins per day by averaging. Defaults to the last 30 days ending today.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `days` | integer |  | Window size in days (default 30, max 365). |
| `end_date` | string |  | Window end date YYYY-MM-DD (default today). |
