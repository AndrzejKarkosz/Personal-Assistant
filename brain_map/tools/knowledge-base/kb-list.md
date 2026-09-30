---
type: Tool
title: kb_list
description: 'Frontmatter query across the bundle -- use when the question cuts across
  pages rather than pointing at one: everything of a type, everything with a tag,
  everything still draft, everything past stale_after. Returns ids, titles and descriptio'
id: knowledge-base__kb_list
server: knowledge-base
kind: mcp
short: kb_list
capabilities: [knowledge.search]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: [type, tag, status, stale_only]
tags: [tool, knowledge-base]
timestamp: '2026-09-30T13:14:24+02:00'
---

# kb_list

Frontmatter query across the bundle -- use when the question cuts across pages rather than pointing at one: everything of a type, everything with a tag, everything still draft, everything past stale_after. Returns ids, titles and descriptions, never bodies.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Search and read the library](../../capabilities/knowledge.search.md) (`knowledge.search`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `type` | string |  |  |
| `tag` | string |  |  |
| `status` | string |  |  |
| `stale_only` | boolean |  | Only pages past their stale_after. |
