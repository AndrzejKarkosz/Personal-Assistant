---
type: Tool
title: set_weight_unit
description: Set the user's preferred weight unit ('kg' or 'lb'), or pass null to
  clear it. This controls how weights are shown and how a bare number is interpreted
  when logging without an explicit unit. Stored weights are unaffected (they are canonical
id: nutrition__set_weight_unit
server: nutrition
kind: mcp
short: set_weight_unit
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [unit]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_weight_unit

Set the user's preferred weight unit ('kg' or 'lb'), or pass null to clear it. This controls how weights are shown and how a bare number is interpreted when logging without an explicit unit. Stored weights are unaffected (they are canonical) — only display and default parsing change. While unset, logging requires an explicit unit and weights display in kg.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `unit` | any | yes | Preferred weight unit: 'kg' or 'lb'. Pass null to clear the preference. |
