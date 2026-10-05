---
type: Tool
title: activities
description: 'The user''s Strava activities between two dates (YYYY-MM-DD, both included),
  oldest first, as JSON. Each has

  sport (swim / bike / run / strength / other), name, start_date_local, moving_time
  (s), distance (m),

  average_heartrate, kilojoules ('
id: strava__activities
server: strava
kind: mcp
short: activities
capabilities: [training.status]
modules: [training]
side_effect: read
requires_confirmation: false
status: online
params: [start_date, end_date]
tags: [tool, strava]
timestamp: '2026-10-04T21:08:27+02:00'
---

# activities

The user's Strava activities between two dates (YYYY-MM-DD, both included), oldest first, as JSON. Each has
sport (swim / bike / run / strength / other), name, start_date_local, moving_time (s), distance (m),
average_heartrate, kilojoules (rides with power), suffer_score (relative effort) and more.

Server: [strava](../../servers/strava.md)

## Capabilities
- [Training plan and Strava](../../capabilities/training.status.md) (`training.status`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `start_date` | string | yes |  |
| `end_date` | string | yes |  |
