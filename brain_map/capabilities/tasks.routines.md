---
type: Capability
title: Manage routines
description: Create, change or remove Alfred's routines - prompts he runs by himself
  on a schedule (cron) or when the app starts (@start).
id: tasks.routines
module: tasks
tools: [routine_delete, routine_save]
tool_patterns: [routine_save, routine_delete]
confirm: true
always: false
available: 2
examples: ['dodaj rutynę: w dni robocze o 7:30 poranny brief', 'przesuń rutynę na
    8:00', usuń rutynę powitanie]
used_by: []
tags: [capability, tasks]
timestamp: '2026-09-30T13:14:24+02:00'
---

# Manage routines

Create, change or remove Alfred's routines - prompts he runs by himself on a schedule (cron) or when the app starts (@start).

Module: [tasks](../modules/tasks.md)

## Tools
- [routine_delete](../tools/alfred/routine-delete.md) - alfred, write
- [routine_save](../tools/alfred/routine-save.md) - alfred, write

## Example requests
- dodaj rutynę: w dni robocze o 7:30 poranny brief
- przesuń rutynę na 8:00
- usuń rutynę powitanie
