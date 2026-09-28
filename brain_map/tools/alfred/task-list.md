---
type: Tool
title: task_list
description: 'List tasks Alfred tracks for the user. status: open (default), all,
  or one status.'
id: task_list
server: alfred
kind: builtin
short: task_list
capabilities: [tasks.manage]
modules: [tasks]
side_effect: read
requires_confirmation: false
status: online
params: [status]
tags: [tool, alfred]
timestamp: '2026-09-25T14:22:57+02:00'
---

# task_list

List tasks Alfred tracks for the user. status: open (default), all, or one status.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `status` | string |  |  |
