---
type: Tool
title: delete_body_measurement
description: Delete a body measurement by ID.
id: nutrition__delete_body_measurement
server: nutrition
kind: mcp
short: delete_body_measurement
capabilities: []
modules: []
side_effect: destructive
requires_confirmation: true
status: online
params: [id]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# delete_body_measurement

Delete a body measurement by ID.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | UUID of the body measurement to delete, from get_body_measurements. |
