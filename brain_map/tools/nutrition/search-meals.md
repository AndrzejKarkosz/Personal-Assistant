---
type: Tool
title: search_meals
description: 'Search the user''s past logged meals by keyword (case-insensitive match
  on description and notes), newest first, grouped into recurring variations with
  counts, last-logged date, and typical macros. Useful before logging a meal from
  a photo: '
id: nutrition__search_meals
server: nutrition
kind: mcp
short: search_meals
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [queries, days, limit]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# search_meals

Search the user's past logged meals by keyword (case-insensitive match on description and notes), newest first, grouped into recurring variations with counts, last-logged date, and typical macros. Useful before logging a meal from a photo: past variations reveal ingredients that aren't visible in the picture (raisins vs banana, milk vs water, added honey or oil), and each difference between variations is a question for the user rather than something to pick silently. Also serves requests like 'log my usual breakfast': search, confirm the variation and the amount with the user, then log_meal. When the user has named the restaurant, search its name as well as the dish — a past visit to the same venue is stronger evidence than a generic estimate. Pass short food keywords, not full sentences, and include the food name in every language the user may have logged in — always add an English alternative alongside the conversation language, e.g. ["вівсянка", "oatmeal"].

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `queries` | array | yes | Keyword alternatives, each a short food name like 'oatmeal' or 'chicken salad' (all words of one alternative must match; alternatives are OR'd). Include the foo |
| `days` | integer |  | How far back to search, in days (default 365). |
| `limit` | integer |  | Max matching entries to analyze (default 50). |
