---
type: Tool
title: routine_delete
description: Remove a routine by its id.
id: routine_delete
server: alfred
kind: builtin
short: routine_delete
capabilities: [tasks.routines]
modules: [tasks]
side_effect: write
requires_confirmation: true
status: online
params: [id]
tags: [tool, alfred]
timestamp: '2026-09-30T13:14:24+02:00'
---

# routine_delete

Remove a routine by its id.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage routines](../../capabilities/tasks.routines.md) (`tasks.routines`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes |  |
