---
type: Tool
title: kb_pending
description: 'The ingest work queue: raw sources that no Source Summary covers yet,
  and summaries whose source file has gone missing. Derived from the bundle, not stored,
  so it cannot go stale. A pending source is work to do, never an error -- and never '
id: knowledge-base__kb_pending
server: knowledge-base
kind: mcp
short: kb_pending
capabilities: [knowledge.learning]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, knowledge-base]
timestamp: '2026-09-25T14:22:57+02:00'
---

# kb_pending

The ingest work queue: raw sources that no Source Summary covers yet, and summaries whose source file has gone missing. Derived from the bundle, not stored, so it cannot go stale. A pending source is work to do, never an error -- and never clear it with a placeholder page, which would hide the gap without the knowledge entering the bundle.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Learning progress](../../capabilities/knowledge.learning.md) (`knowledge.learning`)
