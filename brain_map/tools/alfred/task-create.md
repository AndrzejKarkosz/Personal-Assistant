---
type: Tool
title: task_create
description: Create a task or reminder Alfred should do or remind about later. Use
  `due` (ISO 8601 with timezone) for a one-off moment, `schedule` (5-field cron, local
  time) for recurring ones. The proactive scheduler picks them up automatically.
id: task_create
server: alfred
kind: builtin
short: task_create
capabilities: [tasks.manage]
modules: [tasks]
side_effect: write
requires_confirmation: false
status: online
params: [title, description, due, schedule, priority, module]
tags: [tool, alfred]
timestamp: '2026-09-25T14:22:57+02:00'
---

# task_create

Create a task or reminder Alfred should do or remind about later. Use `due` (ISO 8601 with timezone) for a one-off moment, `schedule` (5-field cron, local time) for recurring ones. The proactive scheduler picks them up automatically.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `title` | string | yes |  |
| `description` | string |  |  |
| `due` | string |  | ISO 8601, e.g. 2026-09-26T09:00:00+02:00 |
| `schedule` | string |  | cron, e.g. '0 8 * * 1-5' |
| `priority` | string |  |  |
| `module` | string |  | Module that should handle it when it fires |
