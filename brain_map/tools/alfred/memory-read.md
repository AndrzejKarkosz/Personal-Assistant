---
type: Tool
title: memory_read
description: Read one page of Alfred's memory by the path returned from memory_search
  (e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.md', 'index.md', 'log.md').
id: memory_read
server: alfred
kind: builtin
short: memory_read
capabilities: [memory.recall]
modules: [memory]
side_effect: read
requires_confirmation: false
status: online
params: [path]
tags: [tool, alfred]
timestamp: '2026-09-25T14:22:57+02:00'
---

# memory_read

Read one page of Alfred's memory by the path returned from memory_search (e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.md', 'index.md', 'log.md').

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Recall past sessions and facts](../../capabilities/memory.recall.md) (`memory.recall`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `path` | string | yes |  |
