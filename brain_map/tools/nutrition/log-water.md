---
type: Tool
title: log_water
description: 'Log a hydration entry in milliliters. If the user gives a volume in
  another unit (cups, oz, liters), convert it: 1 cup = 240 ml, 1 fl oz = 30 ml, 1
  L = 1000 ml. If only ''a glass'' is mentioned, ask for the size or assume 250 ml
  and confirm.'
id: nutrition__log_water
server: nutrition
kind: mcp
short: log_water
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [amount_ml, logged_at, notes, idempotency_key]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# log_water

Log a hydration entry in milliliters. If the user gives a volume in another unit (cups, oz, liters), convert it: 1 cup = 240 ml, 1 fl oz = 30 ml, 1 L = 1000 ml. If only 'a glass' is mentioned, ask for the size or assume 250 ml and confirm.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `amount_ml` | integer | yes | Amount in milliliters (integer, > 0). |
| `logged_at` | string |  | When this actually happened (defaults to now). Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time (" |
| `notes` | string |  | Optional notes (e.g. 'tea', 'post-workout'). |
| `idempotency_key` | string |  | Optional key that makes a retry safe. Without one, the server derives a key from the entry's content and its resolved logged_at: replaying a call that carries a |
