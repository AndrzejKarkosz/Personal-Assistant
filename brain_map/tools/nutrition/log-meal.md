---
type: Tool
title: log_meal
description: 'Log a meal entry with nutritional information. It needs the quantity
  or portion eaten; if the user has not given it, ask before estimating calories and
  macros. For a barcode — typed, or the digits printed under it in a photo of the
  package '
id: nutrition__log_meal
server: nutrition
kind: mcp
short: log_meal
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [description, meal_type, calories, protein_g, carbs_g, fat_g, fiber_g, sugar_g,
  added_sugar_g, alcohol_g, caffeine_mg, logged_at, notes, idempotency_key]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# log_meal

Log a meal entry with nutritional information. It needs the quantity or portion eaten; if the user has not given it, ask before estimating calories and macros. For a barcode — typed, or the digits printed under it in a photo of the package — lookup_barcode returns the product's label data to scale to the amount eaten; if no product is found, estimate. For a branded product or chain item without a barcode, use the label or the published per-item nutrition where available; otherwise estimate from the ingredients and portion. For a photo of a plated or prepared meal, whether it is from a restaurant (and which one, if the user says) or homemade determines the evidence: a chain's published nutrition, a menu or ingredient list if the user shares it or it is available to you, and past logs via search_meals, which surface variations and ingredients the photo cannot show. For a meal logged from a photo, call this tool only after the meal is confirmed: which variation each dish is, how much was eaten (in household meas

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `description` | string | yes | What was eaten |
| `meal_type` | string | yes | Type of meal (breakfast, lunch, dinner, or snack). Always ask the user if not provided. |
| `calories` | number |  | Total calories |
| `protein_g` | number |  | Protein in grams |
| `carbs_g` | number |  | Carbohydrates in grams |
| `fat_g` | number |  | Fat in grams |
| `fiber_g` | number |  | Dietary fiber in grams. Expected on every meal alongside protein, carbs and fat: a missing value is stored as not measured rather than as zero and leaves the wh |
| `sugar_g` | number |  | TOTAL sugars in grams — the figure a nutrition label or database gives for 'Sugars', which includes sugar naturally present in fruit, milk and juice as well as  |
| `added_sugar_g` | number |  | Added sugars in grams: sugars added during processing or preparation (table sugar, syrups, honey, sugar in sweetened drinks and foods). Part of sugar_g, never m |
| `alcohol_g` | number |  | Grams of pure ethanol — NOT the volume of the drink and NOT its ABV. Do not estimate this: compute it from the volume and strength, which the user can read off  |
| `caffeine_mg` | number |  | Caffeine in MILLIGRAMS (mg) — this field is the one that is not in grams, and a value under 1 almost certainly means grams were sent by mistake. Typical amounts |
| `logged_at` | string |  | When this actually happened (defaults to now). Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time (" |
| `notes` | string |  | Additional notes |
| `idempotency_key` | string |  | Optional key that makes a retry safe. Without one, the server derives a key from the meal's content and its resolved logged_at: replaying a call that carries an |
