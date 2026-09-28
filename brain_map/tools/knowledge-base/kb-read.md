---
type: Tool
title: kb_read
description: 'Read one page in full: frontmatter, body, trust fields, its `# Requires`
  chain in learning order, and any recorded contradiction. Carry the trust state into
  your answer -- a flat claim sourced from an unverified draft is what those fields
  e'
id: knowledge-base__kb_read
server: knowledge-base
kind: mcp
short: kb_read
capabilities: [knowledge.search]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: [id]
tags: [tool, knowledge-base]
timestamp: '2026-09-28T18:45:56+02:00'
---

# kb_read

Read one page in full: frontmatter, body, trust fields, its `# Requires` chain in learning order, and any recorded contradiction. Carry the trust state into your answer -- a flat claim sourced from an unverified draft is what those fields exist to prevent.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Search and read the library](../../capabilities/knowledge.search.md) (`knowledge.search`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `id` | string | yes | Page id, e.g. concepts/star-schema. |
