---
type: Capability
title: Training plan and Strava
description: The plan, the season phase, target vs done per sport and week, the 80/20
  share, activities from Strava.
id: training.status
module: training
tools: [strava__activities, training_status]
tool_patterns: [training_status, strava__activities]
confirm: false
always: false
available: 2
examples: ['jak idzie plan?', 'co dziś trenowałem?', 'ile godzin roweru w tym tygodniu?']
used_by: ['skill:training.training-week', 'module:weight', 'skill:weight.weight-goal']
tags: [capability, training]
timestamp: '2026-10-04T19:05:26+02:00'
---

# Training plan and Strava

The plan, the season phase, target vs done per sport and week, the 80/20 share, activities from Strava.

Module: [training](../modules/training.md)

## Tools
- [activities](../tools/strava/activities.md) - strava, read
- [training_status](../tools/alfred/training-status.md) - alfred, read

## Used by
- skill:training.training-week
- module:weight
- skill:weight.weight-goal

## Example requests
- jak idzie plan?
- co dziś trenowałem?
- ile godzin roweru w tym tygodniu?
