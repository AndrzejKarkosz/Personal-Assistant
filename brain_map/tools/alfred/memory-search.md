---
type: Tool
title: memory_search
description: Search Alfred's own memory (past sessions, tasks, facts about the user)
  by keywords. Returns titles, descriptions and paths; open a page with memory_read.
id: memory_search
server: alfred
kind: builtin
short: memory_search
capabilities: [memory.recall]
modules: [memory]
side_effect: read
requires_confirmation: false
status: online
params: [query, limit]
tags: [tool, alfred]
timestamp: '2026-09-30T13:14:24+02:00'
---

# memory_search

Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. Returns titles, descriptions and paths; open a page with memory_read.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Recall past sessions and facts](../../capabilities/memory.recall.md) (`memory.recall`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `query` | string | yes |  |
| `limit` | integer |  |  |
