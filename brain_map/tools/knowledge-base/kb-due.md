---
type: Tool
title: kb_due
description: Spaced-review queue, computed from the `covered:` field on Training Session
  pages and the bundle's interval table. Present only for bundles that record training
  sessions; returns an empty queue otherwise.
id: knowledge-base__kb_due
server: knowledge-base
kind: mcp
short: kb_due
capabilities: [knowledge.learning]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, knowledge-base]
timestamp: '2026-09-28T18:45:56+02:00'
---

# kb_due

Spaced-review queue, computed from the `covered:` field on Training Session pages and the bundle's interval table. Present only for bundles that record training sessions; returns an empty queue otherwise.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Learning progress](../../capabilities/knowledge.learning.md) (`knowledge.learning`)
