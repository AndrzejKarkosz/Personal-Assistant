---
type: Tool
title: task_update
description: 'Update a task: change status (todo, in_progress, done, cancelled), due
  date, schedule, category, title, or add a progress note.'
id: task_update
server: alfred
kind: builtin
short: task_update
capabilities: [tasks.manage]
modules: [tasks]
side_effect: write
requires_confirmation: false
status: online
params: [task_id, title, status, note, due, schedule, category, goal, alfred]
tags: [tool, alfred]
timestamp: '2026-10-02T15:40:08+02:00'
---

# task_update

Update a task: change status (todo, in_progress, done, cancelled), due date, schedule, category, title, or add a progress note.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage tasks and reminders](../../capabilities/tasks.manage.md) (`tasks.manage`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `task_id` | string | yes | Exact id from task_list |
| `title` | string |  | New title |
| `status` | string |  |  |
| `note` | string |  |  |
| `due` | string |  |  |
| `schedule` | string |  |  |
| `category` | string |  | Set it (any value) when the user wants the task moved - Jev picks the category |
| `goal` | string |  | How the task brings him closer to his goal - what he told you when you asked |
| `alfred` | boolean |  | Move to Alfred's board (true) or the user's (false) |
