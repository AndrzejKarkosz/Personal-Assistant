---
type: Tool
title: get_meal_patterns
description: 'Pre-aggregated behavioural patterns across the logged window: meal-type
  presence rates, breakfast effect (days with vs without), high-calorie-lunch effect,
  late-dinner effect, weekday vs weekend, and outlier days. Defaults to the last 30
  da'
id: nutrition__get_meal_patterns
server: nutrition
kind: mcp
short: get_meal_patterns
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [days, end_date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_meal_patterns

Pre-aggregated behavioural patterns across the logged window: meal-type presence rates, breakfast effect (days with vs without), high-calorie-lunch effect, late-dinner effect, weekday vs weekend, and outlier days. Defaults to the last 30 days. Patterns are descriptive estimates, not medical or dietary advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `days` | integer |  | Window size in days (default 30, min 7, max 365). |
| `end_date` | string |  | Window end date YYYY-MM-DD (default today). |
