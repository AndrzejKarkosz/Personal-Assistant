---
type: Capability
title: Log meals, weight and measurements
description: Log a meal with calories and macros, a weigh-in, a body measurement or
  water; find a product by barcode, look up past meals.
id: weight.log
module: weight
tools: [nutrition__log_body_measurement, nutrition__log_meal, nutrition__log_water,
  nutrition__log_weight, nutrition__lookup_barcode, nutrition__search_meals]
tool_patterns: [nutrition__log_meal, nutrition__log_weight, nutrition__log_body_measurement,
  nutrition__log_water, nutrition__lookup_barcode, nutrition__search_meals]
confirm: false
always: false
available: 6
examples: [zjadłem kanapkę z serem, ważę 82 kg, wypiłem pół litra wody]
used_by: []
tags: [capability, weight]
timestamp: '2026-10-04T21:08:27+02:00'
---

# Log meals, weight and measurements

Log a meal with calories and macros, a weigh-in, a body measurement or water; find a product by barcode, look up past meals.

Module: [weight](../modules/weight.md)

## Tools
- [log_body_measurement](../tools/nutrition/log-body-measurement.md) - nutrition, read
- [log_meal](../tools/nutrition/log-meal.md) - nutrition, read
- [log_water](../tools/nutrition/log-water.md) - nutrition, read
- [log_weight](../tools/nutrition/log-weight.md) - nutrition, read
- [lookup_barcode](../tools/nutrition/lookup-barcode.md) - nutrition, read
- [search_meals](../tools/nutrition/search-meals.md) - nutrition, read

## Example requests
- zjadłem kanapkę z serem
- ważę 82 kg
- wypiłem pół litra wody
