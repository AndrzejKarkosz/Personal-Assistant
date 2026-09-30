---
type: Tool
title: memory_remember
description: Store a durable fact about the user (a person, place, preference or project)
  for future sessions.
id: memory_remember
server: alfred
kind: builtin
short: memory_remember
capabilities: [memory.remember]
modules: [memory]
side_effect: write
requires_confirmation: false
status: online
params: [category, title, content]
tags: [tool, alfred]
timestamp: '2026-09-30T13:14:24+02:00'
---

# memory_remember

Store a durable fact about the user (a person, place, preference or project) for future sessions.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Remember a fact about the user](../../capabilities/memory.remember.md) (`memory.remember`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `category` | string | yes |  |
| `title` | string | yes | Short name, e.g. 'Favourite restaurant' |
| `content` | string | yes |  |
