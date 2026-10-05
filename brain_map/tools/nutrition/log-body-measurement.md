---
type: Tool
title: log_body_measurement
description: Log one body circumference measurement — waist, hips, neck, chest, shoulders,
  upper arm, forearm, thigh or calf — in centimetres or inches. Without `unit`, the
  user's saved length unit (set_length_unit) applies; with neither, the call fails
id: nutrition__log_body_measurement
server: nutrition
kind: mcp
short: log_body_measurement
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [kind, value, unit, logged_at, notes, idempotency_key]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# log_body_measurement

Log one body circumference measurement — waist, hips, neck, chest, shoulders, upper arm, forearm, thigh or calf — in centimetres or inches. Without `unit`, the user's saved length unit (set_length_unit) applies; with neither, the call fails and says a unit is needed. The server stores the number and unit exactly as given and does any cm/in conversion itself. Each entry is one site with no left/right field; a side or other detail goes in notes. A site can be measured several times a day. A number far outside a realistic range for the site is refused as a likely typo. Measurements are recorded as given, without targets or interpretation, and this server does not provide medical advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `kind` | string | yes | Body site measured: waist, hips, neck, chest, shoulders, upper_arm (upper arm / biceps), forearm, thigh or calf. |
| `value` | number | yes | Circumference in `unit` (> 0), as the user stated it. |
| `unit` | string |  | Unit of the value: 'cm' or 'in'. Defaults to the user's saved length unit; with neither, the call fails. |
| `logged_at` | string |  | When the measurement was taken (defaults to now). Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time |
| `notes` | string |  | Optional notes (e.g. 'left side', 'at the navel', 'morning, relaxed'). |
| `idempotency_key` | string |  | Optional key that makes a retry safe. Without one, the server derives a key from the measurement's content and its resolved logged_at: replaying a call that car |
