---
type: Tool
title: kb_source
description: 'The immutable raw sources beside the bundle. With no id: list them.
  With an id: read one, if it is a text format. Exposed so an agent needs no filesystem
  access to the bundle''s repository at all. Read-only: raw sources are never modified.'
id: knowledge-base__kb_source
server: knowledge-base
kind: mcp
short: kb_source
capabilities: [knowledge.learning]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: [id, max_bytes]
tags: [tool, knowledge-base]
timestamp: '2026-09-25T14:22:57+02:00'
---

# kb_source

The immutable raw sources beside the bundle. With no id: list them. With an id: read one, if it is a text format. Exposed so an agent needs no filesystem access to the bundle's repository at all. Read-only: raw sources are never modified.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Learning progress](../../capabilities/knowledge.learning.md) (`knowledge.learning`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `id` | string |  | Omit to list all sources. |
| `max_bytes` | integer |  |  |
