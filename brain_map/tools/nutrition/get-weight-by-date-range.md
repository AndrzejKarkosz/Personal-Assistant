---
type: Tool
title: get_weight_by_date_range
description: Get all weight entries between two dates (inclusive), grouped by day
  with each day's average. Use this instead of multiple get_weight_by_date calls.
  The range can span at most 366 days.
id: nutrition__get_weight_by_date_range
server: nutrition
kind: mcp
short: get_weight_by_date_range
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [start_date, end_date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_weight_by_date_range

Get all weight entries between two dates (inclusive), grouped by day with each day's average. Use this instead of multiple get_weight_by_date calls. The range can span at most 366 days.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `start_date` | string | yes | Start date (YYYY-MM-DD) |
| `end_date` | string | yes | End date (YYYY-MM-DD) |
