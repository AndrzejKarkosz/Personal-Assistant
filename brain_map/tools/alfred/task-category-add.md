---
type: Tool
title: task_category_add
description: Add a NEW task category. Only when the user clearly wants a category
  that is not in the fixed list; the user is asked for a spoken yes first. Then use
  it in task_create / task_update.
id: task_category_add
server: alfred
kind: builtin
short: task_category_add
capabilities: [tasks.manage]
modules: [tasks]
side_effect: write
requires_confirmation: false
status: online
params: [name, description]
tags: [tool, alfred]
timestamp: '2026-10-01T10:39:19+02:00'
---

# task_category_add

Add a NEW task category. Only when the user clearly wants a category that is not in the fixed list; the user is asked for a spoken yes first. Then use it in task_create / task_update.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `name` | string | yes | Short name, e.g. 'Dom' |
| `description` | string |  | When a task belongs here, in Polish |
