---
type: Tool
title: task_create
description: Create tasks or reminders Alfred should do or remind about later. Always
  pass a `tasks` list - several tasks go in ONE call, never one call per task. Use
  `due` (ISO 8601 with timezone) for a one-off moment, `schedule` (5-field cron, local
  t
id: task_create
server: alfred
kind: builtin
short: task_create
capabilities: [tasks.manage]
modules: [tasks]
side_effect: write
requires_confirmation: false
status: online
params: [tasks]
tags: [tool, alfred]
timestamp: '2026-09-29T19:36:03+02:00'
---

# task_create

Create tasks or reminders Alfred should do or remind about later. Always pass a `tasks` list - several tasks go in ONE call, never one call per task. Use `due` (ISO 8601 with timezone) for a one-off moment, `schedule` (5-field cron, local time) for recurring ones. The proactive scheduler picks them up automatically.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `tasks` | array | yes |  |
