---
type: Tool
title: training_status
description: 'The user''s triathlon plan and how it goes: the race and days to it,
  the season phase (base, build, peak, taper, recovery), per week target vs done hours
  and sessions for swim / bike / run from Strava, the easy (80/20) share and the activiti'
id: training_status
server: alfred
kind: builtin
short: training_status
capabilities: [training.status]
modules: [training]
side_effect: read
requires_confirmation: false
status: online
params: [weeks]
tags: [tool, alfred]
timestamp: '2026-10-04T21:08:27+02:00'
---

# training_status

The user's triathlon plan and how it goes: the race and days to it, the season phase (base, build, peak, taper, recovery), per week target vs done hours and sessions for swim / bike / run from Strava, the easy (80/20) share and the activities of the last 14 days with estimated kcal (today_kcal = burnt today).

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Training plan and Strava](../../capabilities/training.status.md) (`training.status`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `weeks` | integer |  | How many weeks back, this one included (default 4) |
