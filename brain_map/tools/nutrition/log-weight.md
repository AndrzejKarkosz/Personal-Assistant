---
type: Tool
title: log_weight
description: Log a body-weight measurement. Provide the number in `weight` and its
  `unit` ('kg' or 'lb'); if you omit the unit, the user's saved preference is used,
  and if they have no preference set yet the call fails asking you to specify one.
  IMPORTA
id: nutrition__log_weight
server: nutrition
kind: mcp
short: log_weight
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [weight, unit, logged_at, notes, idempotency_key]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# log_weight

Log a body-weight measurement. Provide the number in `weight` and its `unit` ('kg' or 'lb'); if you omit the unit, the user's saved preference is used, and if they have no preference set yet the call fails asking you to specify one. IMPORTANT: do NOT convert units yourself — pass the value in whatever unit the user stated and set `unit` accordingly. The server stores weight canonically and converts as needed. Multiple weigh-ins per day are allowed.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `weight` | number | yes | Body weight value, in `unit` (> 0). |
| `unit` | string |  | Unit of the weight value. Defaults to the user's preferred weight unit. |
| `logged_at` | string |  | When this actually happened (defaults to now). Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time (" |
| `notes` | string |  | Optional notes (e.g. 'morning, fasted', 'after workout'). |
| `idempotency_key` | string |  | Optional key that makes a retry safe. Without one, the server derives a key from the entry's content and its resolved logged_at: replaying a call that carries a |
