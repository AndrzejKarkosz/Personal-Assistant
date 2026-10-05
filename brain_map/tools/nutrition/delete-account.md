---
type: Tool
title: delete_account
description: Permanently delete the user's Nutrition MCP account and all data this
  service stores about them (meals, water, weight, body measurements, goals, settings,
  exports, usage records, sign-in tokens, and the Apple Health sync connection with
  its
id: nutrition__delete_account
server: nutrition
kind: mcp
short: delete_account
capabilities: []
modules: []
side_effect: destructive
requires_confirmation: true
status: online
params: [confirm]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# delete_account

Permanently delete the user's Nutrition MCP account and all data this service stores about them (meals, water, weight, body measurements, goals, settings, exports, usage records, sign-in tokens, and the Apple Health sync connection with its record of values sent). Totals already written to Apple Health stay on the user's iPhone. Irreversible. Always confirm with the user before calling this tool.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `confirm` | boolean | yes | Must be true to confirm deletion. Always ask the user for explicit confirmation before setting this to true. |
