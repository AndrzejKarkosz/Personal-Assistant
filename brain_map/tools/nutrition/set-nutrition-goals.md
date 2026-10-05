---
type: Tool
title: set_nutrition_goals
description: 'Set the user''s daily calorie and macro targets, and optionally a target
  body weight. Pass only the fields you want to update — omitted fields keep their
  previous value. Pass null explicitly to clear a target. Calories, protein, carbs,
  fat, '
id: nutrition__set_nutrition_goals
server: nutrition
kind: mcp
short: set_nutrition_goals
capabilities: [weight.goals]
modules: [weight]
side_effect: destructive
requires_confirmation: true
status: online
params: [daily_calories, daily_protein_g, daily_carbs_g, daily_fat_g, daily_fiber_g,
  daily_sugar_g, daily_added_sugar_g, daily_alcohol_g, daily_caffeine_mg, daily_water_ml,
  target_weight, unit]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_nutrition_goals

Set the user's daily calorie and macro targets, and optionally a target body weight. Pass only the fields you want to update — omitted fields keep their previous value. Pass null explicitly to clear a target. Calories, protein, carbs, fat, fiber and water are targets to REACH; total sugar, added sugar, alcohol and caffeine are limits to STAY UNDER, and progress against them is worded accordingly. Every gram target is in grams and the caffeine limit is in MILLIGRAMS. For a limit, 0 is a real value meaning 'none at all' rather than 'unset'. Targets are the user's own choice; this server does not provide medical or dietary advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Weight and nutrition goals](../../capabilities/weight.goals.md) (`weight.goals`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `daily_calories` | any |  | Daily calorie target (kcal). Null to clear. |
| `daily_protein_g` | any |  | Daily protein target (grams). Null to clear. |
| `daily_carbs_g` | any |  | Daily carbs target (grams). Null to clear. |
| `daily_fat_g` | any |  | Daily fat target (grams). Null to clear. |
| `daily_fiber_g` | any |  | Daily fiber target (grams), treated as a minimum to reach. Null to clear. |
| `daily_sugar_g` | any |  | Daily TOTAL sugar limit (grams), treated as a maximum to stay under. Total sugars include sugar naturally present in fruit and milk as well as added sugar, so a |
| `daily_added_sugar_g` | any |  | Daily added-sugar limit (grams), a maximum to stay under. Counts only added sugars, not sugar naturally present in fruit and milk; public guidance figures for s |
| `daily_alcohol_g` | any |  | Daily alcohol limit in grams of pure ethanol, treated as a maximum to stay under. One US standard drink is 14 g, one UK unit is 7.9 g. Null to clear. |
| `daily_caffeine_mg` | any |  | Daily caffeine limit in MILLIGRAMS, treated as a maximum to stay under. Reference points to offer when the user has no figure in mind: the EFSA and FDA ceiling  |
| `daily_water_ml` | ['number', 'null'] |  | Daily water target (milliliters). Null to clear. |
| `target_weight` | any |  | Target body weight in `unit` (defaults to the user's preferred weight unit). Null to clear. |
| `unit` | string |  | Unit for target_weight. Defaults to the user's preferred weight unit. |
