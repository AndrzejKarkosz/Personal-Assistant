---
type: Tool
title: get_meals_by_date_range
description: 'Get all meals between two dates (inclusive), grouped by day, one compact
  line each with ids (detail: "full" adds notes). Use this instead of multiple get_meals_by_date
  calls when you need meals for more than one day. The range can span at m'
id: nutrition__get_meals_by_date_range
server: nutrition
kind: mcp
short: get_meals_by_date_range
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [start_date, end_date, detail]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_meals_by_date_range

Get all meals between two dates (inclusive), grouped by day, one compact line each with ids (detail: "full" adds notes). Use this instead of multiple get_meals_by_date calls when you need meals for more than one day. The range can span at most 31 days; get_trends covers longer periods with daily totals instead of individual meals. A long result is truncated at a day boundary with a note naming the start_date to call again with for the rest.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `start_date` | string | yes | Start date (YYYY-MM-DD) |
| `end_date` | string | yes | End date (YYYY-MM-DD). The range spans at most 31 days, both ends included. |
| `detail` | string |  | How much to return per meal. "compact" (default): one line each — local time, type, description, calories and nutrients, and the id update_meal/delete_meal take |
