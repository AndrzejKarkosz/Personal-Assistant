---
type: Tool
title: routine_save
description: 'Create a routine or change an existing one (same id): a prompt Alfred
  runs by himself on a schedule. Only for routines - one-off reminders are tasks.'
id: routine_save
server: alfred
kind: builtin
short: routine_save
capabilities: [tasks.routines]
modules: [tasks]
side_effect: write
requires_confirmation: true
status: online
params: [id, schedule, prompt, module]
tags: [tool, alfred]
timestamp: '2026-09-30T13:14:24+02:00'
---

# routine_save

Create a routine or change an existing one (same id): a prompt Alfred runs by himself on a schedule. Only for routines - one-off reminders are tasks.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Manage routines](../../capabilities/tasks.routines.md) (`tasks.routines`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `id` | string | yes | Short slug, e.g. 'poranny-brief'; an existing id is replaced |
| `schedule` | string | yes | 5-field cron in local time ('30 7 * * 1-5') or '@start' |
| `prompt` | string | yes | What Alfred should do when it runs, as the user would say it |
| `module` | string |  | Module that should run it, e.g. calendar, tasks |
