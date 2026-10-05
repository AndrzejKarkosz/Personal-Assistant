---
type: Capability
title: Weight and nutrition goals
description: Read and set the daily calorie and macro goals and the target weight;
  the profile (timezone, units).
id: weight.goals
module: weight
tools: [nutrition__get_nutrition_goals, nutrition__get_profile, nutrition__set_nutrition_goals,
  nutrition__set_timezone]
tool_patterns: [nutrition__get_nutrition_goals, nutrition__set_nutrition_goals, nutrition__get_profile,
  nutrition__set_timezone]
confirm: false
always: false
available: 4
examples: [ustaw cel 2300 kcal, 'jaki mam cel wagowy?']
used_by: ['skill:weight.weight-goal']
tags: [capability, weight]
timestamp: '2026-10-04T21:08:27+02:00'
---

# Weight and nutrition goals

Read and set the daily calorie and macro goals and the target weight; the profile (timezone, units).

Module: [weight](../modules/weight.md)

## Tools
- [get_nutrition_goals](../tools/nutrition/get-nutrition-goals.md) - nutrition, read
- [get_profile](../tools/nutrition/get-profile.md) - nutrition, read
- [set_nutrition_goals](../tools/nutrition/set-nutrition-goals.md) - nutrition, destructive
- [set_timezone](../tools/nutrition/set-timezone.md) - nutrition, read

## Used by
- skill:weight.weight-goal

## Example requests
- ustaw cel 2300 kcal
- jaki mam cel wagowy?
