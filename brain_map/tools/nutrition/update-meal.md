---
type: Tool
title: update_meal
description: 'Update fields of an existing meal entry. Only the fields you pass are
  changed, which also makes this the way to backfill nutrition a meal was logged without:
  when a past meal has no fiber_g, sugar_g, added_sugar_g or (where it applies) caff'
id: nutrition__update_meal
server: nutrition
kind: mcp
short: update_meal
capabilities: [weight.fix]
modules: [weight]
side_effect: destructive
requires_confirmation: true
status: online
params: [id, description, meal_type, calories, protein_g, carbs_g, fat_g, fiber_g,
  sugar_g, added_sugar_g, alcohol_g, caffeine_mg, logged_at, notes]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# update_meal

Update fields of an existing meal entry. Only the fields you pass are changed, which also makes this the way to backfill nutrition a meal was logged without: when a past meal has no fiber_g, sugar_g, added_sugar_g or (where it applies) caffeine_mg and the user asks or agrees to fill it in, estimate the value and pass just that field. Meal ids come from get_meals_today, get_meals_by_date, get_meals_by_date_range or search_meals.

Fiber, sugar, added sugar and caffeine are tracked alongside the headline macros.
- fiber_g and sugar_g are read on every meal, like protein, carbs and fat. A missing value is stored as "not measured", not as zero, and leaves that whole day out of the user's fiber and sugar averages, goal lines and charts; an estimate keeps the day in. In order of accuracy, a figure comes from a nutrition label, a barcode lookup, the chain's or product's published per-item nutrition, or an estimate from the ingredients and the portion — an exact figure is no more required here than it is for protein. 

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Correct or delete entries](../../capabilities/weight.fix.md) (`weight.fix`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the meal to update, from get_meals_today, get_meals_by_date, get_meals_by_date_range or search_meals. |
| `description` | string |  |  |
| `meal_type` | string |  |  |
| `calories` | number |  |  |
| `protein_g` | number |  |  |
| `carbs_g` | number |  |  |
| `fat_g` | number |  |  |
| `fiber_g` | number |  | Dietary fiber in grams. Only the fields passed are written, so this fills in the figure for a meal logged without one; 0 is the correct value for a food that ha |
| `sugar_g` | number |  | TOTAL sugars in grams, including sugar naturally present in fruit and milk as well as added sugar. Only the fields passed are written, so this fills in the figu |
| `added_sugar_g` | number |  | Added sugars in grams: sugars added during processing or preparation (table sugar, syrups, honey, sugar in sweetened drinks and foods), part of sugar_g and neve |
| `alcohol_g` | number |  | Grams of pure ethanol — NOT the drink's volume and NOT its ABV. Compute it rather than estimating: grams = millilitres x (ABV% / 100) x 0.789 (a 330 ml 5% beer  |
| `caffeine_mg` | number |  | Caffeine in MILLIGRAMS, not grams (a 240 ml brewed coffee is 95 mg, a single espresso 63 mg, black tea 47 mg, a 250 ml energy drink 80 mg). Adds no calories. Pa |
| `logged_at` | string |  | When the meal was eaten. Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time ("2026-01-05T08:30"), or |
| `notes` | string |  |  |
