---
type: Capability
title: Manage tasks and reminders
description: Create a task or reminder (one-off due time or recurring cron), list
  open tasks, change status, add notes.
id: tasks.manage
module: tasks
tools: [task_category_add, task_create, task_list, task_update]
tool_patterns: [task_create, task_update, task_list, task_category_add]
confirm: false
always: false
available: 4
examples: [przypomnij mi za godzinę, 'co mam otwarte?', oznacz jako zrobione]
used_by: ['module:bookings', 'skill:bookings.restaurant-table', 'module:calendar',
  'skill:calendar.daily-brief', 'module:memory', 'module:research']
tags: [capability, tasks]
timestamp: '2026-10-01T10:39:19+02:00'
---

# Manage tasks and reminders

Create a task or reminder (one-off due time or recurring cron), list open tasks, change status, add notes.

Module: [tasks](../modules/tasks.md)

## Tools
- [task_category_add](../tools/alfred/task-category-add.md) - alfred, write
- [task_create](../tools/alfred/task-create.md) - alfred, write
- [task_list](../tools/alfred/task-list.md) - alfred, read
- [task_update](../tools/alfred/task-update.md) - alfred, write

## Used by
- module:bookings
- skill:bookings.restaurant-table
- module:calendar
- skill:calendar.daily-brief
- module:memory
- module:research

## Example requests
- przypomnij mi za godzinę
- co mam otwarte?
- oznacz jako zrobione
