---
type: Tool
title: set_widget_display
description: 'Enable or disable the in-chat visual widgets (nutrition dashboard, goal
  progress, meal-logged rings, trends, weight charts). When disabled, the same tools
  still return their full text and data — just no rendered widget. Widgets are enabled '
id: nutrition__set_widget_display
server: nutrition
kind: mcp
short: set_widget_display
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [enabled]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_widget_display

Enable or disable the in-chat visual widgets (nutrition dashboard, goal progress, meal-logged rings, trends, weight charts). When disabled, the same tools still return their full text and data — just no rendered widget. Widgets are enabled by default. Note: hosts read the widget list when a session connects, so the change takes effect in new conversations; an already-open chat may keep showing widgets until it reconnects.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `enabled` | boolean | yes | true to show widgets (default), false for text-only responses with no widget. |
