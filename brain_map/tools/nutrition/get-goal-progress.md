---
type: Tool
title: get_goal_progress
description: Get progress against daily nutrition goals for a specific date (defaults
  to today). Renders intake-vs-goal rings plus body-weight progress in clients that
  support MCP Apps UI, and returns the same data as text elsewhere. Figures are estimat
id: nutrition__get_goal_progress
server: nutrition
kind: mcp
short: get_goal_progress
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_goal_progress

Get progress against daily nutrition goals for a specific date (defaults to today). Renders intake-vs-goal rings plus body-weight progress in clients that support MCP Apps UI, and returns the same data as text elsewhere. Figures are estimates, not medical or dietary advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `date` | string |  | Date in YYYY-MM-DD format. Defaults to today. |
