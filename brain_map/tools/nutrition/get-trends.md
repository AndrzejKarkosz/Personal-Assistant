---
type: Tool
title: get_trends
description: Rolling 7/14/30-day averages, standard deviation and coefficient of variation
  for calories, protein, carbs, fat, fiber, sugar, added sugar, alcohol (when tracking
  is on), caffeine and water, with days within ±10% of each target or over each
id: nutrition__get_trends
server: nutrition
kind: mcp
short: get_trends
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [days, end_date, group_by]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_trends

Rolling 7/14/30-day averages, standard deviation and coefficient of variation for calories, protein, carbs, fat, fiber, sugar, added sugar, alcohol (when tracking is on), caffeine and water, with days within ±10% of each target or over each limit when goals are set; logging streaks; day-of-week calorie averages; and the best and worst day by calories (closest to and furthest from the calorie target when one is set, otherwise the lowest and highest). Every figure arrives pre-computed. Defaults to the last 30 days ending today. With group_by (week, month, quarter or year) the result also lists calorie, protein, carb and fat averages per calendar period over a fixed span (26 weeks, 24 months, 12 quarters or 5 years), each divided by the days in that period with at least one meal logged rather than by calendar days, beside the targets in effect at the time, the days logged and the days on target. Figures are estimates, not medical or dietary advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `days` | integer |  | Window size in days (default 30, max 365). |
| `end_date` | string |  | Window end date YYYY-MM-DD (default today). |
| `group_by` | string |  | Adds per-period averages per logged day (days with no meals are excluded) against the targets in effect at the time: ISO weeks starting Monday (26 rows), months |
