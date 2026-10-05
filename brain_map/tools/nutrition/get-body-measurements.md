---
type: Tool
title: get_body_measurements
description: Get body measurements between two dates (inclusive), optionally for one
  site, oldest first and grouped by local day, each with the id that update_body_measurement
  and delete_body_measurement take. Defaults to the 30 days ending today; a ran
id: nutrition__get_body_measurements
server: nutrition
kind: mcp
short: get_body_measurements
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [kind, start_date, end_date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_body_measurements

Get body measurements between two dates (inclusive), optionally for one site, oldest first and grouped by local day, each with the id that update_body_measurement and delete_body_measurement take. Defaults to the 30 days ending today; a range spans at most 366 days, and a long listing stops at a whole day and names the date to continue from. Values are shown in the user's saved length unit, or in the unit each was entered in when none is saved.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `kind` | string |  | Only this site. Omitted: every site. |
| `start_date` | string |  | Start date YYYY-MM-DD (default: 29 days before end_date). |
| `end_date` | string |  | End date YYYY-MM-DD (default: today in the user's timezone). |
