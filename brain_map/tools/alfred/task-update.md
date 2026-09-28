---
type: Tool
title: task_update
description: 'Update a task: change status (todo, in_progress, waiting, done, cancelled),
  due date, schedule, or add a progress note.'
id: task_update
server: alfred
kind: builtin
short: task_update
capabilities: [tasks.manage]
modules: [tasks]
side_effect: write
requires_confirmation: false
status: online
params: [task_id, status, note, due, schedule]
tags: [tool, alfred]
timestamp: '2026-09-25T14:22:57+02:00'
---

# task_update

Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, schedule, or add a progress note.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `task_id` | string | yes |  |
| `status` | string |  |  |
| `note` | string |  |  |
| `due` | string |  |  |
| `schedule` | string |  |  |
