---
type: Tool
title: training_plan_update
description: 'Change the user''s training plan after he agreed to a proposal: the
  race, weekly sessions and hours per sport (swim, bike, run, strength), the easy
  heart-rate limit, the daily step goal. Pass only what changes; `why` is kept with
  the change.'
id: training_plan_update
server: alfred
kind: builtin
short: training_plan_update
capabilities: [training.plan]
modules: [training]
side_effect: write
requires_confirmation: true
status: online
params: [why, race, weekly, easy_hr_max, steps_goal]
tags: [tool, alfred]
timestamp: '2026-10-05T10:16:01+02:00'
---

# training_plan_update

Change the user's training plan after he agreed to a proposal: the race, weekly sessions and hours per sport (swim, bike, run, strength), the easy heart-rate limit, the daily step goal. Pass only what changes; `why` is kept with the change.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Change the training plan](../../capabilities/training.plan.md) (`training.plan`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `why` | string | yes | One sentence: what changes and why |
| `race` | object |  |  |
| `weekly` | object |  | sport -> {sessions, hours} |
| `easy_hr_max` | integer |  |  |
| `steps_goal` | integer |  |  |
