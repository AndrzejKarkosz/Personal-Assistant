---
type: Capability
title: Correct or delete entries
description: Change or delete a logged meal or weigh-in.
id: weight.fix
module: weight
tools: [nutrition__delete_meal, nutrition__delete_weight, nutrition__update_meal,
  nutrition__update_weight]
tool_patterns: [nutrition__update_meal, nutrition__delete_meal, nutrition__update_weight,
  nutrition__delete_weight]
confirm: true
always: false
available: 4
examples: [popraw ostatni posiłek, usuń dzisiejszą wagę]
used_by: []
tags: [capability, weight]
timestamp: '2026-10-04T21:08:27+02:00'
---

# Correct or delete entries

Change or delete a logged meal or weigh-in.

Module: [weight](../modules/weight.md)

## Tools
- [delete_meal](../tools/nutrition/delete-meal.md) - nutrition, destructive
- [delete_weight](../tools/nutrition/delete-weight.md) - nutrition, destructive
- [update_meal](../tools/nutrition/update-meal.md) - nutrition, destructive
- [update_weight](../tools/nutrition/update-weight.md) - nutrition, destructive

## Example requests
- popraw ostatni posiłek
- usuń dzisiejszą wagę
