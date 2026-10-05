---
type: Tool
title: get_nutrition_summary
description: Get daily nutrition totals for a date range. Renders an interactive dashboard
  (macro tiles vs. goals and a per-day breakdown) in clients that support MCP Apps
  UI, and returns the same data as text elsewhere. The range can span at most 92 da
id: nutrition__get_nutrition_summary
server: nutrition
kind: mcp
short: get_nutrition_summary
capabilities: [weight.read]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [start_date, end_date]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_nutrition_summary

Get daily nutrition totals for a date range. Renders an interactive dashboard (macro tiles vs. goals and a per-day breakdown) in clients that support MCP Apps UI, and returns the same data as text elsewhere. The range can span at most 92 days; get_trends covers longer periods. Figures are estimates, not medical or dietary advice.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Diet and weight progress](../../capabilities/weight.read.md) (`weight.read`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `start_date` | string | yes | Start date (YYYY-MM-DD) |
| `end_date` | string | yes | End date (YYYY-MM-DD). The range spans at most 92 days, both ends included. |
