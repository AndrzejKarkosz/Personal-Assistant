---
type: Tool
title: update_body_measurement
description: Update an existing body measurement's value, unit, time or notes. The
  site (kind) cannot be changed; a measurement of a different site is a new entry.
  A new `value` is read in `unit`, which defaults to the unit the entry was originally
  ente
id: nutrition__update_body_measurement
server: nutrition
kind: mcp
short: update_body_measurement
capabilities: []
modules: []
side_effect: destructive
requires_confirmation: true
status: online
params: [id, value, unit, logged_at, notes]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# update_body_measurement

Update an existing body measurement's value, unit, time or notes. The site (kind) cannot be changed; a measurement of a different site is a new entry. A new `value` is read in `unit`, which defaults to the unit the entry was originally entered in, not the saved preference. Passing `unit` without `value` re-reads the stored number in that unit, which corrects an entry logged with the wrong unit. A value far outside a realistic range for the site is refused.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the body measurement to update, from get_body_measurements. |
| `value` | number |  | New circumference value, in `unit`. |
| `unit` | string |  | Unit of the value. Defaults to the unit this entry was entered in. |
| `logged_at` | string |  | When the measurement was taken. Accepts a full ISO 8601 timestamp with an offset or Z ("2026-01-05T08:30:00+02:00"), an offset-less local time ("2026-01-05T08:3 |
| `notes` | string |  |  |
