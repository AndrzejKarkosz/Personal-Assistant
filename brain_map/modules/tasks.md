---
type: Module
title: Tasks, reminders and follow-ups
description: Remember to do something, remind me later, recurring routines, what is
  still open, mark something done, what did we agree to pick up.
id: tasks
capabilities: [tasks.manage, tasks.routines]
uses: [memory.recall]
skills: []
servers: [alfred]
examples: [przypomnij mi jutro o 9 żeby zadzwonić do mamy, 'co mam jeszcze otwarte?',
  every weekday at 8 give me a morning brief, oznacz fakturę jako zrobioną]
enabled: true
model: null
effort: null
tags: [module]
timestamp: '2026-09-30T17:50:37+02:00'
---

# Tasks, reminders and follow-ups

Remember to do something, remind me later, recurring routines, what is still open, mark something done, what did we agree to pick up.

## Capabilities
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)
- [Manage routines](../capabilities/tasks.routines.md) (`tasks.routines`)

## Borrowed capabilities
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)

## Connected servers
- [alfred](../servers/alfred.md)

## Example requests
- przypomnij mi jutro o 9 żeby zadzwonić do mamy
- co mam jeszcze otwarte?
- every weekday at 8 give me a morning brief
- oznacz fakturę jako zrobioną
