---
type: Tool
title: kb_graph
description: 'Structure rather than content. With an id: inbound links (the blast
  radius of changing that page), outbound links by relationship type, and the full
  `# Requires` chain. Without an id: the most-cited pages, which is what the bundle
  is really'
id: knowledge-base__kb_graph
server: knowledge-base
kind: mcp
short: kb_graph
capabilities: [knowledge.search]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: [id, top]
tags: [tool, knowledge-base]
timestamp: '2026-09-28T18:45:56+02:00'
---

# kb_graph

Structure rather than content. With an id: inbound links (the blast radius of changing that page), outbound links by relationship type, and the full `# Requires` chain. Without an id: the most-cited pages, which is what the bundle is really about.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Search and read the library](../../capabilities/knowledge.search.md) (`knowledge.search`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `id` | string |  | Omit to get hubs instead. |
| `top` | integer |  |  |
