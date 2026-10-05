---
type: Capability
title: Diet and weight progress
description: Meals and totals of a day or range, progress against nutrition goals,
  weight trend, measurements.
id: weight.read
module: weight
tools: [nutrition__get_body_measurements, nutrition__get_goal_progress, nutrition__get_meals_by_date,
  nutrition__get_meals_by_date_range, nutrition__get_meals_today, nutrition__get_nutrition_summary,
  nutrition__get_trends, nutrition__get_weight_by_date_range, nutrition__get_weight_trends]
tool_patterns: [nutrition__get_meals_today, nutrition__get_meals_by_date, nutrition__get_meals_by_date_range,
  nutrition__get_nutrition_summary, nutrition__get_goal_progress, nutrition__get_trends,
  nutrition__get_weight_by_date_range, nutrition__get_weight_trends, nutrition__get_body_measurements]
confirm: false
always: false
available: 9
examples: ['ile kalorii dziś?', 'jak spada waga?', 'co jadłem wczoraj?']
used_by: ['module:training', 'skill:training.training-week', 'skill:weight.weight-goal']
tags: [capability, weight]
timestamp: '2026-10-04T21:08:27+02:00'
---

# Diet and weight progress

Meals and totals of a day or range, progress against nutrition goals, weight trend, measurements.

Module: [weight](../modules/weight.md)

## Tools
- [get_body_measurements](../tools/nutrition/get-body-measurements.md) - nutrition, read
- [get_goal_progress](../tools/nutrition/get-goal-progress.md) - nutrition, read
- [get_meals_by_date](../tools/nutrition/get-meals-by-date.md) - nutrition, read
- [get_meals_by_date_range](../tools/nutrition/get-meals-by-date-range.md) - nutrition, read
- [get_meals_today](../tools/nutrition/get-meals-today.md) - nutrition, read
- [get_nutrition_summary](../tools/nutrition/get-nutrition-summary.md) - nutrition, read
- [get_trends](../tools/nutrition/get-trends.md) - nutrition, read
- [get_weight_by_date_range](../tools/nutrition/get-weight-by-date-range.md) - nutrition, read
- [get_weight_trends](../tools/nutrition/get-weight-trends.md) - nutrition, read

## Used by
- module:training
- skill:training.training-week
- skill:weight.weight-goal

## Example requests
- ile kalorii dziś?
- jak spada waga?
- co jadłem wczoraj?
